"""
DeepseekAnalyzer: Comprehensive Email Content Analysis Service

Implements detailed analysis of meeting-related emails, providing natural
language summaries and handling recommendations for the final categorization
stage of the pipeline.

Design Considerations:
- Comprehensive DEBUG level logging throughout all operations
- Complete input/output capturing for model interactions
- Detailed error state documentation with full context preservation
- Processing flow monitoring with decision point tracking
- Performance metrics tracking for system monitoring
- Enhanced timeout handling for reliable API communication
"""

import logging
import os
import json
import traceback
import asyncio
import hashlib
import re
from typing import Dict, Tuple, Optional, Any, List
from datetime import datetime
import aiohttp
from src.config.analyzer_config import ANALYZER_CONFIG

# Configure logger with proper naming
logger = logging.getLogger(__name__)

class DeepseekAnalyzer:
    """
    Detailed content analyzer using Deepseek model for comprehensive email understanding.
    
    Implements the second stage of the three-stage email analysis pipeline, providing
    rich natural language analysis of email content that has been identified as
    meeting-related in the first stage. Focuses on meeting characteristics, completeness,
    risk factors, and appropriate response generation.
    
    Features:
    - Comprehensive DEBUG level logging throughout all operations
    - Complete input/output tracking for API interactions
    - Detailed error state documentation with context preservation
    - Processing flow monitoring with decision tracking
    - Performance metrics collection for system monitoring
    - Enhanced timeout configurations for reliable API communication
    - Structured output format for downstream component integration
    """
    
    def __init__(self):
        """
        Initialize analyzer with configuration and API setup.
        
        Loads configuration from the centralized analyzer configuration,
        sets up API endpoints, and verifies API key availability.
        
        Raises:
            ValueError: If the required DEEPSEEK_API_KEY environment variable is not set
        """
        self.config = ANALYZER_CONFIG["deepseek_analyzer"]
        self.api_endpoint = self.config["model"]["api_endpoint"]
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        
        # Load timeout settings from config or use defaults
        self.timeout_seconds = self.config.get("timeout", 120)
        
        # Log initialization with configuration details (excluding sensitive data)
        logger.debug(
            f"DeepseekAnalyzer initialized with configuration: "
            f"model={self.config['model']['name']}, "
            f"endpoint={self.api_endpoint}, "
            f"temperature={self.config['model'].get('temperature', 0.7)}, "
            f"timeout={self.timeout_seconds}s"
        )
        
        if not self.api_key:
            logger.error("DEEPSEEK_API_KEY environment variable not set")
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")
    
    async def analyze_email(self, email_content: str) -> Tuple[Dict[str, Any], str, str, Optional[str]]:
        """
        Perform comprehensive analysis of email content with structured output.
        
        Implements detailed analysis of meeting-related email content, evaluating
        completeness, risk factors, and generating appropriate responses based
        on a structured analysis workflow. Returns rich structured data that can
        be used by downstream components.
        
        Args:
            email_content: Raw email content to analyze
            
        Returns:
            Tuple of (analysis_data, response_text, recommendation, error)
            - analysis_data: Dictionary containing structured analysis information
            - response_text: Pre-generated response text extracted from analysis
            - recommendation: Handling recommendation (standard_response, needs_review, ignore)
            - error: Error message if analysis failed, None otherwise
        """
        start_time = datetime.now()
        
        # Generate a request ID using hash of content and timestamp
        content_hash = hashlib.md5(email_content.encode()).hexdigest()[:6]
        request_id = f"deepseek-{start_time.strftime('%Y%m%d%H%M%S')}-{content_hash}"
        
        try:
            logger.info(f"[{request_id}] Starting detailed email content analysis")
            
            # Log input details at debug level
            logger.debug(
                f"[{request_id}] Analyzing content of length: {len(email_content)} characters\n"
                f"Content preview: {email_content[:100]}..." if len(email_content) > 100 else email_content
            )
            
            # Construct analysis prompt
            prompt = self._construct_analysis_prompt(email_content)
            logger.debug(f"[{request_id}] Analysis prompt generated with length: {len(prompt)}")
            
            # Prepare API request
            request_payload = {
                "model": self.config["model"]["name"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.config["model"].get("temperature", 0.7)
            }
            
            # Log API request configuration
            logger.debug(
                f"[{request_id}] Sending API request with configuration:\n"
                f"Model: {request_payload['model']}\n"
                f"Temperature: {request_payload['temperature']}\n"
                f"Message length: {len(prompt)}"
            )
            
            # Check if development fallback mode is enabled
            use_fallback = self.config.get("use_fallback", False)
            
            if use_fallback:
                # Development/testing mode with mock response
                logger.warning(f"[{request_id}] Using fallback mode for development/testing")
                await asyncio.sleep(0.5)  # Simulate processing time
                response = self._generate_mock_response(email_content)
            else:
                # Process with Deepseek API with detailed timing
                api_start_time = datetime.now()
                response = await self._make_api_request(request_id, request_payload)
                api_duration = (datetime.now() - api_start_time).total_seconds()
                logger.debug(f"[{request_id}] API request completed in {api_duration:.3f} seconds")
            
            # Extract analysis content
            analysis = response["choices"][0]["message"]["content"]
            
            # Log raw analysis result at DEBUG level
            logger.debug(f"[{request_id}] Raw analysis result:\n{analysis}")
            
            # Process analysis results
            processing_start = datetime.now()
            analysis_data, response_text, recommendation = self._process_analysis(analysis, request_id)
            processing_duration = (datetime.now() - processing_start).total_seconds()
            
            # Calculate total processing time
            total_duration = (datetime.now() - start_time).total_seconds()
            
            # Log results and timing information
            logger.info(
                f"[{request_id}] Successfully completed detailed analysis in {total_duration:.3f} seconds"
            )
            logger.debug(
                f"[{request_id}] Analysis results:\n"
                f"Analysis data: {json.dumps(analysis_data)}\n"
                f"Response text length: {len(response_text)}\n"
                f"Recommendation: {recommendation}"
            )
            
            return analysis_data, response_text, recommendation, None
            
        except Exception as e:
            # Capture full error context
            error_msg = f"Analysis failed: {str(e)}"
            stack_trace = traceback.format_exc()
            
            # Calculate error timing
            error_duration = (datetime.now() - start_time).total_seconds()
            
            # Log comprehensive error information
            logger.error(
                f"[{request_id}] {error_msg} after {error_duration:.3f} seconds\n"
                f"Stack trace:\n{stack_trace}"
            )
            
            # Use fallback for development or return error
            if self.config.get("use_fallback_on_error", True):
                logger.warning(f"[{request_id}] Using fallback analysis due to error")
                summary = self._generate_fallback_summary(email_content)
                return {"summary": summary}, "", "needs_review", error_msg
            else:
                return {}, "", "needs_review", error_msg

    async def _make_api_request(self, request_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API request to Deepseek API with comprehensive error handling.
        
        Implements detailed request handling with proper error recovery,
        retry logic, comprehensive logging, and enhanced timeout handling.
        
        Args:
            request_id: Unique identifier for tracking this request
            payload: Request payload containing model configuration and prompt
            
        Returns:
            Dictionary containing the API response
            
        Raises:
            Exception: If the API request fails after retry attempts
        """
        retry_count = 0
        max_retries = self.config.get("retry_count", 1) 
        retry_delay = self.config.get("retry_delay", 3)  # seconds
        
        # Important: Create a proper ClientTimeout object, not a dictionary
        # This fixes the "TypeError: '>' not supported between instances of 'dict' and 'int'" error
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        
        logger.debug(f"[{request_id}] Configured API request with timeout: {self.timeout_seconds}s")
        
        while True:
            try:
                logger.debug(f"[{request_id}] API request attempt {retry_count + 1}/{max_retries + 1}")
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    request_start_time = datetime.now()
                    
                    async with session.post(
                        f"{self.api_endpoint}/chat/completions",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self.api_key}"
                        },
                        json=payload
                    ) as response:
                        # Log response status
                        connection_time = (datetime.now() - request_start_time).total_seconds()
                        logger.debug(f"[{request_id}] API response status: {response.status} (connection time: {connection_time:.3f}s)")
                        
                        if response.status != 200:
                            response_text = await response.text()
                            logger.warning(
                                f"[{request_id}] API request failed with status {response.status}: "
                                f"{response_text[:500]}..."
                            )
                            raise Exception(f"API request failed: {response.status} - {response_text[:200]}")
                        
                        # Read response with explicit timeout handling
                        try:
                            # Use asyncio.wait_for to ensure we don't hang indefinitely
                            result = await asyncio.wait_for(
                                response.json(), 
                                timeout=self.timeout_seconds
                            )
                            
                            # Calculate total request time
                            total_request_time = (datetime.now() - request_start_time).total_seconds()
                            
                            # Log successful response
                            logger.debug(
                                f"[{request_id}] API request successful: received {len(json.dumps(result))} bytes "
                                f"in {total_request_time:.3f}s"
                            )
                            
                            return result
                            
                        except asyncio.TimeoutError:
                            logger.error(f"[{request_id}] Timeout while reading response body after {self.timeout_seconds}s")
                            raise TimeoutError(f"Timeout reading response body after {self.timeout_seconds}s")
            
            except asyncio.TimeoutError as e:
                # Explicit handling for timeout errors
                logger.warning(f"[{request_id}] Request timed out: {str(e)}")
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"[{request_id}] Max retries exceeded after timeout")
                    raise TimeoutError(f"API request timed out after {max_retries+1} attempts")
                
                logger.warning(
                    f"[{request_id}] Retrying timed-out request (attempt {retry_count}/{max_retries}). "
                    f"Waiting {retry_delay} seconds..."
                )
                await asyncio.sleep(retry_delay)
                
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"[{request_id}] Max retries exceeded: {str(e)}")
                    raise
                
                logger.warning(
                    f"[{request_id}] API request failed (attempt {retry_count}/{max_retries}): {str(e)}. "
                    f"Retrying in {retry_delay} seconds..."
                )
                await asyncio.sleep(retry_delay)

    def _generate_mock_response(self, content: str) -> Dict[str, Any]:
        """
        Generate a mock response for development and testing in the new format.
        
        Creates a realistic structured response mimicking the expected output
        from the new prompt format. Tailors the response based on content 
        characteristics to simulate realistic analysis results.
        
        Args:
            content: Email content being analyzed
            
        Returns:
            Dictionary containing structured mock response
        """
        # Content-based analysis to generate plausible mock responses
        is_complex = len(content) > 500 or "discuss" in content.lower()
        has_date_time = any(term in content.lower() for term in ["tomorrow", "today", "am", "pm", ":00"])
        has_location = any(term in content.lower() for term in ["room", "office", "zoom", "meet", "teams"])
        
        # Determine completeness
        completeness = 0
        missing_elements = []
        
        if has_date_time:
            completeness += 1
        else:
            missing_elements.append("Time/Date")
            
        if has_location:
            completeness += 1
        else:
            missing_elements.append("Location")
            
        # Check for purpose/agenda
        has_purpose = "agenda" in content.lower() or "discuss" in content.lower()
        if has_purpose:
            completeness += 1
        else:
            missing_elements.append("Agenda/Purpose")
            
        # Check for attendees
        has_attendees = "attendees" in content.lower() or "participants" in content.lower()
        if has_attendees:
            completeness += 1
        else:
            missing_elements.append("Attendee list")
        
        # Determine tone
        is_formal = "dear" in content.lower() or "sincerely" in content.lower()
        tone = "Formal" if is_formal else "Friendly"
        
        # Build response based on analysis
        if is_complex or completeness < 2:
            recommendation = "needs_review"
            response_message = (
                f"Dear Sender,\n\nThank you for your message. "
                f"Your request is being reviewed by our team and we will respond within 24 hours. "
                f"Please let us know if you have any urgent concerns.\n\nBest regards,\nAssistant"
            )
        elif completeness < 4:
            recommendation = "standard_response"
            missing_str = ", ".join(missing_elements)
            response_message = (
                f"Hi there,\n\nThanks for your meeting request! "
                f"Could you please provide the following details: {missing_str}? "
                f"This will help us properly schedule the meeting.\n\nThanks!\nAssistant"
            )
        else:
            recommendation = "standard_response"
            response_message = (
                f"Dear Sender,\n\nThank you for your meeting request. "
                f"I am pleased to confirm our meeting details. "
                f"Looking forward to our discussion.\n\nBest regards,\nAssistant"
            )
        
        # Construct the formatted analysis output - fixed proper indentation
        mock_content = f"""
Think step by step, but only keep a minimum draft for each thinking step, with 5 words at most. Return the answer at the end of the response after a separator ####
█ ANALYSIS █
Completeness: {completeness}/4 elements
Missing Elements: {", ".join(missing_elements) if missing_elements else "None"}
Risk Factors: {"Multiple parties involved" if is_complex else "None"}
Detected Tone: {tone}

█ RESPONSE █
Tone: {tone}
Message: |
{response_message}

█ RECOMMENDATION █
{recommendation}
"""
        
        # Create a structured mock response mimicking API format
        return {
            "id": f"mock-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": "mock-deepseek-reasoner",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": mock_content
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(content.split()),
                "completion_tokens": len(mock_content.split()) + 10,
                "total_tokens": len(content.split()) + len(mock_content.split()) + 10
            }
        }
    
    def _generate_fallback_summary(self, content: str) -> str:
        """
        Generate a fallback summary when API processing fails.
        
        Creates a basic analysis of the email content to ensure the pipeline
        can continue functioning even when the external API is unavailable.
        
        Args:
            content: Email content to analyze
            
        Returns:
            Basic summary of email content for pipeline continuation
        """
        # Extract basic meeting characteristics from content
        content_lower = content.lower()
        
        has_date = any(term in content_lower for term in ["tomorrow", "today", "monday", "tuesday", "wednesday", "thursday", "friday"])
        has_time = any(term in content_lower for term in [":00", "am", "pm", "morning", "afternoon"])
        has_location = any(term in content_lower for term in ["room", "office", "building", "cafe", "online", "zoom", "teams", "meet", "conference"])
        
        # Build appropriate fallback summary
        missing_items = []
        if not has_date:
            missing_items.append("date")
        if not has_time:
            missing_items.append("time")
        if not has_location:
            missing_items.append("location")
            
        if missing_items:
            missing_str = ", ".join(missing_items)
            summary = (
                f"This appears to be a meeting-related communication, but lacks clear specification of {missing_str}. "
                f"The email content is {len(content)} characters long and contains basic meeting discussion. "
                f"Due to the missing information, this email should be reviewed manually or additional information "
                f"should be requested."
            )
        else:
            summary = (
                f"This email appears to contain a meeting request with date, time, and location information. "
                f"The content is {len(content)} characters long and seems to be a straightforward meeting coordination. "
                f"A standard response confirming the meeting details would be appropriate."
            )
            
        return summary

    def _construct_analysis_prompt(self, content: str) -> str:
        """
        Construct comprehensive analysis prompt with structured workflow.
        
        Creates a prompt that guides the model through a systematic analysis process
        with specific steps for screening, completeness checking, risk assessment,
        and response strategy determination. This structured approach ensures
        consistent analysis output that can be reliably parsed by downstream
        components.
        
        Args:
            content: Email content to analyze
            
        Returns:
            Formatted prompt implementing the structured analysis workflow
        """
        prompt = f"""
Follow this analysis workflow:
STEP 1: Initial Screening
- Meeting request identified? [Y/N]
- Clear purpose statement? [Y/N]
- Tone assessment: [Friendly/Formal] (check greetings, sign-off, emojis)

STEP 2: Completeness Check
Required Elements:
1. Specific time/date
2. Location/virtual link
3. Agenda/objective
4. Attendee list

STEP 3: Risk Assessment
- Financial/legal implications? 
- Sensitive topics?
- Multi-party coordination?
STEP 4: Response Strategy
IF Complete + Low Risk → Immediate confirmation
IF Incomplete + Low Risk → Request missing info
IF Any High Risk Factor → Human review notice
IF Informational → Polite acknowledgment

FINAL OUTPUT FORMAT:
█ ANALYSIS █
Completeness: 2/4 elements
Missing Elements: Time, Location
Risk Factors: None
Detected Tone: Friendly

█ RESPONSE █
Tone: [Match detected tone: Friendly/Formal]
Message: |
[Generated response text here]
[Include time-specific reference if needs_review]
[Request missing elements if applicable]

█ RECOMMENDATION █
standard_response

RESPONSE TEMPLATES:
> Needs Review:
Friendly: "Hi [Name], thanks for your message! Our team will review 
your request and get back to you within 24 hours. We appreciate 
your patience!"

Formal: "Dear [Sender], your request has been received and is 
undergoing review. A response will be provided within 24 business 
hours. Regards, [Team]"
> Missing Info:
Friendly: "Hey there! Could you share the [missing elements]? 
This will help us prepare better 😊"

Formal: "Please provide the [missing elements] to facilitate 
processing your request. Thank you for your cooperation."
NOW ANALYZE:
{content}
"""
        return prompt.strip()

    def _process_analysis(self, analysis: str, request_id: str) -> Tuple[Dict[str, Any], str, str]:
        """
        Process and structure the analysis response from the new format.
        
        Extracts structured analysis information, pre-generated response text,
        and recommendation from the structured analysis output. Implements
        comprehensive validation and fallback mechanisms to ensure reliable
        processing even when the output deviates from expected structure.
        
        Args:
            analysis: Raw analysis text from the model
            request_id: Unique identifier for tracking this request
            
        Returns:
            Tuple of (analysis_data, response_text, recommendation)
            - analysis_data: Dictionary containing structured analysis information
            - response_text: Pre-generated response text extracted from analysis
            - recommendation: Validated recommendation (standard_response, needs_review, ignore)
        """
        try:
            logger.debug(f"[{request_id}] Processing structured analysis output of length: {len(analysis)}")
            
            # Initialize result containers
            analysis_data = {}
            response_text = ""
            recommendation = "needs_review"  # Default to needs_review as the safest option
            
            # Check for section markers
            analysis_marker = "█ ANALYSIS █"
            response_marker = "█ RESPONSE █"
            recommendation_marker = "█ RECOMMENDATION █"
            
            has_analysis = analysis_marker in analysis
            has_response = response_marker in analysis
            has_recommendation = recommendation_marker in analysis
            
            logger.debug(
                f"[{request_id}] Analysis structure check: "
                f"has_analysis={has_analysis}, has_response={has_response}, "
                f"has_recommendation={has_recommendation}"
            )
            
            # Extract sender information for response personalization
            sender_name = self._extract_sender_info(analysis)
            if sender_name:
                analysis_data["sender_name"] = sender_name
            
            # Process based on available sections
            if has_analysis and has_response and has_recommendation:
                # Extract analysis section
                analysis_parts = analysis.split(analysis_marker, 1)[1].split(response_marker, 1)[0].strip()
                
                # Parse analysis data
                for line in analysis_parts.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                        
                    if ":" in line:
                        key, value = [part.strip() for part in line.split(":", 1)]
                        analysis_data[key.lower()] = value
                
                # Extract response text
                if has_response:
                    response_section = analysis.split(response_marker, 1)[1]
                    if has_recommendation:
                        response_section = response_section.split(recommendation_marker, 1)[0]
                    
                    # Extract tone
                    tone_match = re.search(r"tone:\s*(friendly|formal)", response_section, re.IGNORECASE)
                    if tone_match:
                        analysis_data["tone"] = tone_match.group(1).lower()
                    
                    # Extract message - multiple patterns to handle various formatting possibilities
                    # Try various patterns to extract the message
                    message_patterns = [
                        # Standard format with pipe and content until next section or end
                        r"message:\s*\|(.*?)(?=█|\Z)",
                        # Alternative without pipe symbol
                        r"message:(.*?)(?=█|\Z)",
                        # Fallback for any content after "message:" label
                        r"message:(.+?)(?=\n\s*\n|\Z)"
                    ]
                    
                    for pattern in message_patterns:
                        message_match = re.search(pattern, response_section, re.DOTALL | re.IGNORECASE)
                        if message_match:
                            extracted_text = message_match.group(1).strip()
                            if extracted_text:
                                response_text = extracted_text
                                break
                
                # Extract recommendation
                if has_recommendation:
                    rec_section = analysis.split(recommendation_marker, 1)[1].strip().lower()
                    valid_recommendations = ["standard_response", "needs_review", "ignore"]
                    
                    for valid_rec in valid_recommendations:
                        if valid_rec in rec_section:
                            recommendation = valid_rec
                            break
            else:
                # Fallback for unexpected format
                logger.warning(
                    f"[{request_id}] Analysis format doesn't match expected structure. "
                    f"Using fallback processing approach."
                )
                
                # Try to extract any useful information we can find
                self._extract_from_unstructured_text(analysis, analysis_data)
                
                # Try to extract recommendation from anywhere in the text
                valid_recommendations = ["standard_response", "needs_review", "ignore"]
                for valid_rec in valid_recommendations:
                    if valid_rec in analysis.lower():
                        recommendation = valid_rec
                        break
            
            logger.debug(
                f"[{request_id}] Extracted analysis data: {json.dumps(analysis_data)}\n"
                f"Response text length: {len(response_text)}\n"
                f"Recommendation: {recommendation}"
            )
            
            # If no response text was extracted but recommendation suggests we need one
            if not response_text and recommendation == "standard_response":
                logger.warning(f"[{request_id}] No response text extracted but standard_response recommended")
                response_text = self._generate_fallback_response(analysis_data)
            
            return analysis_data, response_text, recommendation
                
        except Exception as e:
            # Log exception with stack trace
            logger.error(
                f"[{request_id}] Error processing analysis: {str(e)}\n"
                f"Stack trace:\n{traceback.format_exc()}"
            )
            
            # Return safe defaults
            return {"error": "Analysis processing failed"}, "", "needs_review"
    
    def _extract_sender_info(self, text: str) -> Optional[str]:
        """
        Extract sender name from analysis text for personalized responses.
        
        Args:
            text: Raw analysis text
            
        Returns:
            Sender name if found, None otherwise
        """
        # Look for common sender information patterns
        sender_patterns = [
            r"sender(?:'s)? name:?\s*([^\n,]+)",
            r"from:?\s*([^\n,]+)",
            r"(?:to|for):?\s*([^\n,]+)"
        ]
        
        for pattern in sender_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                sender = match.group(1).strip()
                # Remove common non-name components
                sender = re.sub(r"<[^>]+>", "", sender)
                return sender
                
        return None
        
    def _extract_from_unstructured_text(self, text: str, analysis_data: Dict[str, Any]) -> None:
        """
        Extract valuable information from unstructured text when standard format is missing.
        
        Updates the analysis_data dictionary in place with any extractable information.
        
        Args:
            text: Raw analysis text
            analysis_data: Dictionary to update with extracted information
        """
        # Common patterns to extract from unstructured text
        extraction_patterns = {
            "completeness": r"completeness:?\s*(\d+)/4",
            "missing_elements": r"missing(?:\s*elements)?:?\s*([^\n]+)",
            "risk_factors": r"risk(?:\s*factors)?:?\s*([^\n]+)",
            "tone": r"(?:detected\s*)?tone:?\s*(friendly|formal)",
        }
        
        for key, pattern in extraction_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                analysis_data[key] = match.group(1).strip()
                
        # If we have a completeness score but no missing elements, try to infer
        if "completeness" in analysis_data and "missing_elements" not in analysis_data:
            completeness = int(analysis_data["completeness"])
            if completeness < 4:
                all_elements = ["Time/Date", "Location", "Agenda/Purpose", "Attendee list"]
                
                # Look for each element in the text
                found_elements = []
                for element in all_elements:
                    if element.lower() in text.lower() and "missing" not in text[text.lower().find(element.lower())-20:text.lower().find(element.lower())]:
                        found_elements.append(element)
                        
                # Infer missing elements
                if found_elements:
                    missing_elements = [e for e in all_elements if e not in found_elements]
                    analysis_data["missing_elements"] = ", ".join(missing_elements)
    
    def _generate_fallback_response(self, analysis_data: Dict[str, Any]) -> str:
        """
        Generate a fallback response when response extraction fails.
        
        Creates an appropriate response based on available analysis data
        to ensure downstream components have a valid response text.
        
        Args:
            analysis_data: Extracted analysis information
            
        Returns:
            Generated response text
        """
        # Determine the appropriate salutation based on available data
        sender_name = analysis_data.get("sender_name", "")
        tone = analysis_data.get("tone", "formal").lower()
        
        # Select greeting based on tone
        if tone == "friendly":
            greeting = f"Hi {sender_name}," if sender_name else "Hi there,"
        else:
            greeting = f"Dear {sender_name}," if sender_name else "Dear Sender,"
        
        # Check for missing elements to customize response
        if "missing_elements" in analysis_data:
            missing_elements = analysis_data["missing_elements"]
            response = (
                f"{greeting}\n\n"
                f"Thank you for your meeting request. To help me properly schedule our meeting, "
                f"could you please provide the following information: {missing_elements}?\n\n"
            )
        else:
            # Generic response when no specific missing elements identified
            response = (
                f"{greeting}\n\n"
                f"Thank you for your meeting request. To help me properly schedule our meeting, "
                f"could you please provide additional details about the proposed meeting?\n\n"
            )
        
        # Add appropriate closing based on tone
        if tone == "friendly":
            response += "Thanks!\nIvaylo's AI Assistant"
        else:
            response += "Best regards,\nIvaylo's AI Assistant"
            
        return response
