"""
DeepseekAnalyzer: Detailed Email Content Analysis Service

Implements comprehensive email analysis using the DeepSeek Reasoner model,
following the architecture defined in analysis-pipeline.md. This component
serves as the second stage of the three-stage email analysis pipeline.

Design Considerations:
- Comprehensive content analysis with proper parameter extraction
- Dynamic response generation with enhanced formality control
- Robust error handling with configurable retry mechanisms
- Clear logging for system monitoring and debugging
"""

import logging
import os
import json
import asyncio
import time
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

from src.config.analyzer_config import ANALYZER_CONFIG

logger = logging.getLogger(__name__)

class DeepseekAnalyzer:
    """
    Detailed content analyzer using DeepSeek Reasoner model.
    
    Implements the second stage of the email analysis pipeline as specified
    in analysis-pipeline.md, providing comprehensive content analysis and
    response generation with enhanced formality control.
    
    Key capabilities:
    - Complete meeting parameter extraction (date, time, location, agenda)
    - Formality detection and adjustment (two levels more formal than sender)
    - Response generation with appropriate business language
    - Robust error handling with configurable retry
    """
    
    def __init__(self):
        """
        Initialize the analyzer with configuration from central settings.
        
        Loads configuration parameters from ANALYZER_CONFIG, establishes
        API connection details, and configures operational behaviors like
        timeouts and retry logic.
        """
        # Load configuration from centralized analyzer configuration
        self.config = ANALYZER_CONFIG.get("deepseek_analyzer", {})
        self.model_name = self.config.get("model", {}).get("name", "deepseek-reasoner")
        self.api_endpoint = self.config.get("model", {}).get("api_endpoint", "https://api.deepseek.com/v1")
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.temperature = self.config.get("model", {}).get("temperature", 0.7)
        self.timeout = self.config.get("timeout", 180)
        self.retry_count = self.config.get("retry_count", 1)
        self.retry_delay = self.config.get("retry_delay", 3)
        
        # Define formality levels for reference
        self.formality_levels = {
            1: "Very casual",
            2: "Casual",
            3: "Neutral",
            4: "Formal", 
            5: "Very formal"
        }
        
        # Validate API key existence
        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not found in environment variables")
        
        logger.debug(f"DeepseekAnalyzer initialized with configuration: "
                   f"model={self.model_name}, endpoint={self.api_endpoint}, "
                   f"temperature={self.temperature}, timeout={self.timeout}s")

    async def analyze_email(self, email_content: str) -> Tuple[Dict, str, str, Optional[str]]:
        """
        Analyze email content with comprehensive parameter extraction.
        
        Implements detailed content analysis with proper formality detection,
        tone adjustment, and response generation according to the rules in
        analysis-pipeline.md and response-management.md.
        
        Args:
            email_content: Raw email content to analyze
            
        Returns:
            Tuple containing:
            - analysis_data: Structured analysis results
            - response_text: Generated response with appropriate formality
            - recommendation: Processing recommendation (standard_response, needs_review, ignore)
            - error: Error message if analysis failed, None otherwise
        """
        # Generate unique request ID for tracking and logging
        request_id = f"deepseek-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(3).hex()}"
        
        try:
            # Handle empty or unavailable content
            if not email_content or email_content.strip() == "No content available":
                email_content = "No content available"
                
            # Log analysis start
            logger.info(f"[{request_id}] Starting detailed email content analysis")
            logger.debug(f"[{request_id}] Analyzing content of length: {len(email_content)} characters")
            logger.debug(f"[{request_id}] Content preview: {email_content[:100]}..." 
                        if len(email_content) > 100 else email_content)

            # Generate analysis prompt with formality instructions
            prompt = self._create_analysis_prompt(email_content, request_id)
            logger.debug(f"[{request_id}] Analysis prompt generated with length: {len(prompt)}")
            
            # Call API with retry logic
            self._start_time = time.time()
            analysis = await self._call_deepseek_api(prompt, request_id)
            logger.debug(f"[{request_id}] Raw analysis result:\n{analysis}")
            
            # Extract components from the unstructured response
            analysis_data, response_text, recommendation = self._process_analysis_result(analysis, request_id)
            
            # Log completion and details
            logger.info(f"[{request_id}] Successfully completed detailed analysis in "
                       f"{time.time() - self._start_time:.3f} seconds")
            logger.debug(f"[{request_id}] Analysis results:\n"
                        f"Analysis data: {json.dumps(analysis_data)}\n"
                        f"Response text length: {len(response_text)}\n"
                        f"Recommendation: {recommendation}")
            
            return analysis_data, response_text, recommendation, None
            
        except Exception as e:
            # Log error and return error information
            logger.error(f"[{request_id}] Analysis failed: {str(e)}")
            return {}, "", "needs_review", f"Analysis failed: {str(e)}"

    def _create_analysis_prompt(self, email_content: str, request_id: str) -> str:
        """
        Create comprehensive analysis prompt with formality guidance.
        
        Implements a structured prompt designed to extract meeting parameters,
        detect tone, adjust formality, and generate appropriate responses
        following the pipeline specifications.
        
        Args:
            email_content: Email content to analyze
            request_id: Unique identifier for this analysis request
            
        Returns:
            Formatted prompt string with detailed instructions
        """
        # Create system prompt with comprehensive instructions
        system_prompt = f"""You are an expert email analyzer specialized in meeting-related communications.

TASK:
Analyze this email to determine if it contains meeting information and extract key parameters.

ANALYSIS REQUIREMENTS:
1. Check if all REQUIRED elements are present:
   - Specific time/date
   - Location (physical or virtual meeting link)
   - Agenda/purpose
   - List of attendees

2. Assess any risk factors that might require human review:
   - Financial commitments
   - Legal implications
   - Complex multi-party coordination
   - Sensitive content
   - Technical complexity

3. Detect sender's tone and formality level on this 5-point scale:
   1. Very casual (emojis, slang, extremely informal language)
   2. Casual (conversational, friendly, informal)
   3. Neutral (balanced, standard business communication)
   4. Formal (professional, structured, traditional business style)
   5. Very formal (highly structured, ceremonial, extremely professional)

FORMALITY ADJUSTMENT RULES:
- ALWAYS make responses ONE LEVELS MORE FORMAL than the detected sender's tone
- If sender is casual (2), make response neutral (3)
- If sender is neutral (3), make response formal (4)
- If sender is formal (4), make response very formal (5)
- Minimum formality level is Neutral (3)
- For formal/very formal responses:
  - Remove emojis and exclamation points
  - Use complete sentences and proper business language
  - Address recipient with appropriate titles (Mr./Ms./Dr. if name known)
  - Include proper greeting and closing

RESPONSE REQUIREMENTS:
- Respond appropriately to the email content
- For complete meeting details, confirm the meeting
- For missing elements, request the specific missing information
- For high-risk content, indicate human review is needed
- Match formality level to the rules above
- Do not include placeholders like [NAME] - make reasonable assumptions

OUTPUT FORMAT:
Respond in free-form text that includes the following clearly marked sections:

ANALYSIS: 
Include completeness (e.g., "3/4 elements"), missing elements, risk factors, and detected tone.

RESPONSE:
Include your complete, formality-adjusted email response text.

RECOMMENDATION:
End with one of these keywords: standard_response, needs_review, or ignore

EMAIL TO ANALYZE:
{email_content}
"""

        return system_prompt

    async def _call_deepseek_api(self, prompt: str, request_id: str) -> str:
        """
        Call DeepSeek API with comprehensive error handling.
        
        Implements robust API calling with timeout protection,
        retry logic, and proper error handling following the
        protocols in error-handling.md.
        
        Args:
            prompt: Analysis prompt to send
            request_id: Request identifier for logging
            
        Returns:
            Raw analysis result text
            
        Raises:
            RuntimeError: If API call fails after all retries
        """
        import requests
        
        # Configure API request with timeout
        logger.debug(f"[{request_id}] Sending API request with configuration:\n"
                   f"Model: {self.model_name}\n"
                   f"Temperature: {self.temperature}\n"
                   f"Message length: {len(prompt)}")
        logger.debug(f"[{request_id}] Configured API request with timeout: {self.timeout}s")
        
        # Try API call with retries
        for attempt in range(self.retry_count + 1):
            try:
                logger.debug(f"[{request_id}] API request attempt {attempt + 1}/{self.retry_count + 1}")
                
                # Make API request
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature
                }
                
                # Send request with timeout
                start_time = time.time()
                response = requests.post(
                    f"{self.api_endpoint}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                connection_time = time.time() - start_time
                
                logger.debug(f"[{request_id}] API response status: {response.status_code} "
                           f"(connection time: {connection_time:.3f}s)")
                
                if response.status_code != 200:
                    raise RuntimeError(f"API returned status code {response.status_code}: {response.text}")
                
                # Process response
                response_data = response.json()
                if "choices" not in response_data or not response_data["choices"]:
                    raise ValueError("Invalid API response format")
                    
                result = response_data["choices"][0]["message"]["content"]
                
                # Calculate and log timing
                total_time = time.time() - start_time
                logger.debug(f"[{request_id}] API request successful: received {len(result)} bytes "
                           f"in {total_time:.3f}s")
                
                return result
                
            except Exception as e:
                # Log error and retry if attempts remain
                if attempt < self.retry_count:
                    logger.warning(f"[{request_id}] API request failed (attempt {attempt + 1}): {str(e)}")
                    logger.info(f"[{request_id}] Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    # Final failure
                    logger.error(f"[{request_id}] API request failed after {self.retry_count + 1} attempts: {str(e)}")
                    raise RuntimeError("API request timed out after all retry attempts")
        
        # This point should never be reached due to the raise in the loop
        raise RuntimeError("Unexpected error in API call retry logic")

    def _process_analysis_result(self, analysis: str, request_id: str) -> Tuple[Dict, str, str]:
        """
        Process unstructured analysis result from DeepSeek API.
        
        Extracts key information from the unstructured response, including
        analysis data, response text, and recommendation.
        
        Args:
            analysis: Raw analysis output from DeepSeek API
            request_id: Request identifier for logging
            
        Returns:
            Tuple containing:
            - analysis_data: Extracted analysis information
            - response_text: Generated response text
            - recommendation: Processing recommendation
        """
        logger.debug(f"[{request_id}] Processing unstructured analysis output of length: {len(analysis)}")
        
        # Initialize default values
        analysis_data = {}
        response_text = ""
        recommendation = "needs_review"  # Default to needs_review for safety
        
        # Extract analysis data
        analysis_match = re.search(r'ANALYSIS:(.*?)(?=RESPONSE:|$)', analysis, re.DOTALL | re.IGNORECASE)
        if analysis_match:
            analysis_text = analysis_match.group(1).strip()
            
            # Extract completeness
            completeness_match = re.search(r'(\d+)/4 elements', analysis_text)
            if completeness_match:
                analysis_data["completeness"] = f"{completeness_match.group(1)}/4 elements"
                
            # Extract missing elements
            missing_match = re.search(r'missing elements?:?\s*(.*?)(?=\.|$)', analysis_text, re.IGNORECASE)
            if missing_match:
                missing_elements = missing_match.group(1).strip()
                if missing_elements.lower() != "none":
                    analysis_data["missing elements"] = missing_elements
                    
            # Extract risk factors
            risk_match = re.search(r'risk factors?:?\s*(.*?)(?=\.|$)', analysis_text, re.IGNORECASE)
            if risk_match:
                risk_factors = risk_match.group(1).strip()
                analysis_data["risk factors"] = risk_factors
                
            # Extract tone
            tone_match = re.search(r'tone:?\s*(.*?)(?=\.|$)', analysis_text, re.IGNORECASE)
            if tone_match:
                detected_tone = tone_match.group(1).strip()
                analysis_data["detected tone"] = detected_tone
        
        # Extract response text
        response_match = re.search(r'RESPONSE:(.*?)(?=RECOMMENDATION:|$)', analysis, re.DOTALL | re.IGNORECASE)
        if response_match:
            response_text = response_match.group(1).strip()
            
            # Add tone information for the ResponseCategorizer
            response_tone = "friendly" 
            for level, tone_name in self.formality_levels.items():
                if tone_name.lower() in response_text.lower()[:100]:
                    response_tone = tone_name.lower()
                    break
            analysis_data["tone"] = response_tone
        
        # Extract recommendation
        recommendation_match = re.search(r'RECOMMENDATION:?\s*(.*?)(?=\.|$)', analysis, re.DOTALL | re.IGNORECASE)
        if recommendation_match:
            rec_text = recommendation_match.group(1).strip().lower()
            if "standard_response" in rec_text:
                recommendation = "standard_response"
            elif "needs_review" in rec_text:
                recommendation = "needs_review"
            elif "ignore" in rec_text:
                recommendation = "ignore"
        
        # As a final fallback, try to detect the recommendation from the entire response
        if recommendation == "needs_review":
            if "standard_response" in analysis.lower():
                recommendation = "standard_response"
            elif "ignore" in analysis.lower():
                recommendation = "ignore"
                
        return analysis_data, response_text, recommendation

    def decide_action(self, analysis_result: Any) -> str:
        """
        Determine appropriate action based on analysis results.
        
        Implements decision logic based on the recommendation
        provided by DeepSeek and additional safety checks for
        high-risk or incomplete content.
        
        Args:
            analysis_result: Analysis results from DeepSeek API
            
        Returns:
            Action string (respond, flag_for_review, ignore)
        """
        # Implementation depends on the analysis_result structure
        if hasattr(analysis_result, 'recommendation'):
            recommendation = analysis_result.recommendation
        elif isinstance(analysis_result, dict) and 'recommendation' in analysis_result:
            recommendation = analysis_result['recommendation']
        else:
            return "flag_for_review"  # Default to review if structure is unclear
        
        # Map recommendations to actions
        action_mapping = {
            "standard_response": "respond",
            "needs_review": "flag_for_review",
            "ignore": "ignore"
        }
        
        return action_mapping.get(recommendation, "flag_for_review")