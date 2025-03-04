"""
ResponseCategorizer: Final Email Categorization Service

Implements the final stage of the email analysis pipeline, determining
appropriate handling categories based on Deepseek's detailed analysis
and generating appropriate response templates.

Design Considerations:
- Integration with enhanced structured DeepseekAnalyzer output
- Prioritization of pre-generated responses from structured analysis
- Fallback to AI-generated responses when needed
- Comprehensive parameter extraction from structured data
- Robust error handling with detailed logging
- Backward compatibility with previous pipeline versions
"""

import logging
import re
import traceback
from typing import Dict, Tuple, List, Optional, Any
from datetime import datetime
import json

from src.integrations.groq.client_wrapper import EnhancedGroqClient
from src.config.analyzer_config import ANALYZER_CONFIG

logger = logging.getLogger(__name__)

class ResponseCategorizer:
    """
    Final stage analyzer for determining email handling categories and responses.
    
    Implements the third stage of the three-stage email analysis pipeline, making
    final determinations about email handling and response generation. This component
    processes structured analysis data from DeepseekAnalyzer, extracts pre-generated
    responses, and finalizes categorization decisions.
    
    Key responsibilities:
    - Process structured analysis data from DeepseekAnalyzer
    - Prioritize pre-generated responses from structured output
    - Generate responses when needed for missing parameters
    - Make final categorization decisions for email handling
    - Implement comprehensive logging and error handling
    
    The categorizer maintains backward compatibility with previous pipeline versions
    while leveraging enhanced structured output from the updated DeepseekAnalyzer.
    """
    
    def __init__(self):
        """
        Initialize categorizer with required components.
        
        Sets up the GroqClient for fallback response generation and loads configuration
        parameters from the centralized analyzer configuration.
        """
        self.client = EnhancedGroqClient()
        self.model_config = ANALYZER_CONFIG["default_analyzer"]["model"]
        logger.debug(f"ResponseCategorizer initialized with model configuration: {self.model_config['name']}")
    
    async def categorize_email(
        self,
        analysis_data: Dict[str, Any],
        response_text: str,
        deepseek_recommendation: str,
        deepseek_summary: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Determine final handling category and process or generate response.
        
        Processes structured analysis data from DeepseekAnalyzer to make final
        categorization decisions and handle response generation. Prioritizes
        pre-generated responses when available and falls back to generating
        responses when needed.
        
        Args:
            analysis_data: Structured analysis data from DeepseekAnalyzer
            response_text: Pre-generated response text from DeepseekAnalyzer
            deepseek_recommendation: Recommended handling category from DeepseekAnalyzer
            deepseek_summary: Optional legacy summary text for backward compatibility
            
        Returns:
            Tuple of (category: str, response_template: Optional[str])
        """
        request_id = f"respond-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            logger.info(f"[{request_id}] Processing categorization with recommendation: {deepseek_recommendation}")
            logger.debug(f"[{request_id}] Analysis data: {json.dumps(analysis_data)}")
            logger.debug(f"[{request_id}] Pre-generated response text length: {len(response_text)}")
            
            # Extract missing parameters from structured analysis when available
            missing_params = self._extract_missing_parameters_structured(analysis_data)
            
            # Fall back to extracting from summary if needed
            if not missing_params and deepseek_summary:
                missing_params = self._extract_missing_parameters(deepseek_summary)
                
            logger.debug(f"[{request_id}] Extracted missing parameters: {missing_params}")
            
            # Priority logic for categorization
            if deepseek_recommendation == "ignore":
                logger.info(f"[{request_id}] Categorizing email for ignoring based on DeepseekAnalyzer recommendation")
                return "ignore", None
                
            # For meeting emails requiring review
            if deepseek_recommendation == "needs_review":
                logger.info(f"[{request_id}] Categorizing email for manual review based on DeepseekAnalyzer recommendation")
                return "needs_review", None
                
            # For standard responses
            if deepseek_recommendation == "standard_response":
                # Use pre-generated response if available
                if response_text:
                    logger.info(f"[{request_id}] Using pre-generated response from DeepseekAnalyzer")
                    return "standard_response", response_text
                
                # Handle missing parameters even if recommendation is standard_response
                if missing_params:
                    logger.info(f"[{request_id}] Found missing parameters: {missing_params}, generating parameter request")
                    response_template = await self._generate_parameter_request(
                        analysis_data, 
                        missing_params, 
                        deepseek_summary
                    )
                    return "standard_response", response_template
                
                # Fallback to generating response template
                logger.info(f"[{request_id}] Generating standard response template")
                response_template = await self._generate_response_template(analysis_data, deepseek_summary)
                return "standard_response", response_template
                
            # Default handling - treat as needs_review for safety
            logger.warning(f"[{request_id}] Unrecognized recommendation: {deepseek_recommendation}, treating as needs_review")
            return "needs_review", None
                
        except Exception as e:
            # Comprehensive error logging with stack trace
            logger.error(f"[{request_id}] Categorization failed: {str(e)}")
            logger.error(f"[{request_id}] Stack trace: {traceback.format_exc()}")
            return "needs_review", None
    
    def _extract_missing_parameters_structured(self, analysis_data: Dict[str, Any]) -> List[str]:
        """
        Extract missing parameters from structured analysis data.
        
        Processes structured analysis data to identify missing parameters that 
        can be requested from the sender. Handles various formats of structured
        data to ensure consistent parameter extraction.
        
        Args:
            analysis_data: Structured analysis data from DeepseekAnalyzer
            
        Returns:
            List of missing parameter names
        """
        missing_params = []
        
        # Check for direct missing_elements field in structured data
        if "missing_elements" in analysis_data:
            missing_elements = analysis_data["missing_elements"]
            
            # Convert to lowercase for case-insensitive matching
            missing_elements_lower = missing_elements.lower()
            
            # Map missing elements to parameter names
            param_patterns = {
                "date": ["date", "day", "when"],
                "time": ["time", "hour", "when"],
                "location": ["location", "place", "where", "venue", "meeting link", "zoom"],
                "agenda": ["agenda", "purpose", "topic", "objective"]
            }
            
            # Extract missing parameters based on patterns
            for param, patterns in param_patterns.items():
                if any(pattern in missing_elements_lower for pattern in patterns):
                    missing_params.append(param)
                    
        # Check for completeness score to infer missing elements
        elif "completeness" in analysis_data:
            try:
                # Extract completeness value and convert to int
                completeness_str = analysis_data["completeness"]
                if "/" in completeness_str:
                    completeness = int(completeness_str.split("/")[0])
                else:
                    completeness = int(completeness_str)
                    
                # If completeness is less than total, infer missing elements
                if completeness < 4:  # We expect 4 total parameters
                    # Default to requesting the most critical params if we can't determine specifics
                    missing_params = ["date", "time", "location"]
            except (ValueError, TypeError):
                logger.warning(f"Invalid completeness value in analysis_data: {analysis_data.get('completeness')}")
        
        return missing_params
            
    def _extract_missing_parameters(self, summary: str) -> List[str]:
        """
        Extract missing parameters from text summary (legacy method).
        
        Analyzes the summary text to identify parameters that can be requested
        from the sender, such as date, time, location, or agenda. Used as a
        fallback when structured data is unavailable.
        
        Args:
            summary: Detailed summary from DeepseekAnalyzer
            
        Returns:
            List of missing parameter names
        """
        if not summary:
            return []
            
        missing_params = []
        
        # Common patterns for missing parameter detection
        missing_patterns = {
            "date": ["missing date", "date is missing", "no date", "without date", "date absent", "date: absent"],
            "time": ["missing time", "time is missing", "am/pm unclear", "am/pm unspecified", "unclear time", "time: absent"],
            "location": ["missing location", "location is missing", "vague location", "unclear location", "location: absent"],
            "agenda": ["missing agenda", "purpose unclear", "no purpose", "unclear purpose", "agenda: absent"]
        }
        
        summary_lower = summary.lower()
        
        for param, patterns in missing_patterns.items():
            if any(pattern in summary_lower for pattern in patterns):
                missing_params.append(param)
                
        return missing_params

    async def _generate_response_template(self, analysis_data: Dict[str, Any], summary: Optional[str] = None) -> str:
        """
        Generate appropriate response template based on analysis data and summary.
        
        Creates either an information request for missing details or a meeting
        confirmation template based on available analysis data. Uses either
        structured data or text summary depending on availability.
        
        Args:
            analysis_data: Structured analysis data from DeepseekAnalyzer
            summary: Optional text summary for backward compatibility
            
        Returns:
            Formatted response template
        """
        try:
            # Extract sender name for personalization
            sender_name = analysis_data.get("sender_name", self._extract_sender_name(summary))
            
            # Determine tone for response
            tone = analysis_data.get("tone", "formal").lower()
            
            # Check if missing elements are specified
            missing_elements = analysis_data.get("missing_elements")
            
            # Generate appropriate greeting based on tone
            greeting = self._generate_greeting(sender_name, tone)
            
            # Generate response body based on available data
            if missing_elements:
                # Generate request for missing information
                body = (
                    f"Thank you for your meeting request. To help me properly schedule our meeting, "
                    f"could you please provide the following information: {missing_elements}?"
                )
            else:
                # Generate confirmation response
                body = (
                    "Thank you for your meeting request. I am reviewing the details "
                    "and will confirm our meeting arrangements shortly."
                )
            
            # Generate appropriate closing based on tone
            closing = "Thanks!" if tone == "friendly" else "Best regards,"
            signature = "Ivaylo's AI Assistant"
            
            # Assemble complete response
            response = f"{greeting}\n\n{body}\n\n{closing}\n{signature}"
            
            logger.debug(f"Generated response template of length: {len(response)}")
            return response
            
        except Exception as e:
            logger.error(f"Response template generation failed: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return self._get_default_response_template()

    async def _generate_parameter_request(
        self, 
        analysis_data: Dict[str, Any], 
        missing_params: List[str],
        summary: Optional[str] = None
    ) -> str:
        """
        Generate a response requesting missing parameters.
        
        Creates a polite, structured response requesting specific
        missing information needed to process the meeting.
        
        Args:
            analysis_data: Structured analysis data from DeepseekAnalyzer
            missing_params: List of parameters to request
            summary: Optional text summary for backward compatibility
            
        Returns:
            Formatted response template requesting information
        """
        # Parameter descriptions for user-friendly requests
        param_descriptions = {
            "date": "the meeting date",
            "time": "the specific time (including AM/PM)",
            "location": "the exact meeting location or virtual meeting link",
            "agenda": "the meeting purpose or agenda"
        }
        
        # Format parameters for natural language inclusion
        formatted_params = [param_descriptions[param] for param in missing_params if param in param_descriptions]
        
        if len(formatted_params) == 1:
            param_text = formatted_params[0]
        elif len(formatted_params) == 2:
            param_text = f"{formatted_params[0]} and {formatted_params[1]}"
        else:
            param_text = ", ".join(formatted_params[:-1]) + f", and {formatted_params[-1]}"
        
        # Extract sender name from analysis data or summary
        sender_name = analysis_data.get("sender_name", self._extract_sender_name(summary))
        
        # Determine tone for response
        tone = analysis_data.get("tone", "formal").lower()
        
        # Generate greeting based on tone and sender information
        greeting = self._generate_greeting(sender_name, tone)
        
        # Generate appropriate closing based on tone
        closing = "Thanks!" if tone == "friendly" else "Best regards,"
        
        # Create complete response
        response_template = f"""{greeting}

Thank you for your meeting request. To help me properly schedule our meeting, could you please provide {param_text}?

{closing}
Ivaylo's AI Assistant"""

        logger.debug(f"Generated parameter request for: {missing_params}")
        return response_template

    def _generate_greeting(self, sender_name: Optional[str], tone: str) -> str:
        """
        Generate appropriate greeting based on sender name and tone.
        
        Creates a personalized greeting that matches the specified tone
        and includes the sender's name when available.
        
        Args:
            sender_name: Sender's name for personalization, if available
            tone: Communication tone (friendly or formal)
            
        Returns:
            Formatted greeting
        """
        sender_name = sender_name or "[Sender]"
        
        if tone == "friendly":
            return f"Hi {sender_name},"
        else:
            return f"Dear {sender_name},"

    def _extract_sender_name(self, summary: Optional[str]) -> Optional[str]:
        """
        Extract sender name from summary text.
        
        Attempts to identify sender information from text summary
        for personalization in responses.
        
        Args:
            summary: Text summary that might contain sender information
            
        Returns:
            Sender name if found, None otherwise
        """
        if not summary:
            return None
            
        # Look for common sender information patterns
        patterns = [
            r"sender(?:'s)?\s*(?:name|is)?:\s*([^,\n]+)",
            r"from\s*:\s*([^,\n]+)",
            r"email from\s+([^,\n.]+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, summary, re.IGNORECASE)
            if match:
                return match.group(1).strip()
                
        return None

    def _get_default_response_template(self) -> str:
        """
        Provide a safe default response template for error cases.
        
        Returns a generalized response that can safely be used when
        specific template generation fails.
        
        Returns:
            Default response template
        """
        return """Dear Sender,

Thank you for your meeting request. To help me properly schedule our meeting, could you please provide additional details about the proposed meeting?

Best regards,
Ivaylo's AI Assistant"""

    # Legacy method signature for backward compatibility
    async def categorize_email_legacy(
        self,
        deepseek_summary: str,
        deepseek_recommendation: str
    ) -> Tuple[str, Optional[str]]:
        """
        Legacy method signature for backward compatibility.
        
        Implements the previous interface for categorizing emails
        to maintain compatibility with older code.
        
        Args:
            deepseek_summary: Detailed analysis from DeepseekAnalyzer
            deepseek_recommendation: Recommended handling category
            
        Returns:
            Tuple of (category: str, response_template: Optional[str])
        """
        # Extract minimal analysis data from summary
        analysis_data = {}
        
        # Call the new implementation with empty structured data
        return await self.categorize_email(
            analysis_data=analysis_data,
            response_text="",
            deepseek_recommendation=deepseek_recommendation,
            deepseek_summary=deepseek_summary
        )
