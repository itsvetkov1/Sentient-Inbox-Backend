"""
LlamaAnalyzer: Initial Meeting Classification Service

Implements focused binary classification of emails to determine if they are
meeting-related. Acts as the first stage in the three-stage email analysis
pipeline, providing initial filtering before detailed content analysis.

Design Considerations:
- Comprehensive DEBUG level logging of all operations
- Complete input/output logging for model interactions
- Detailed error state documentation
- Processing decision tracking
"""

import logging
import json
from typing import Tuple, Dict, Optional, Any
from datetime import datetime
import traceback

from src.integrations.groq.client_wrapper import EnhancedGroqClient
from src.config.analyzer_config import ANALYZER_CONFIG

# Configure logger with proper naming
logger = logging.getLogger(__name__)

class LlamaAnalyzer:
    """
    Initial stage analyzer using Llama model for binary meeting classification.
    
    Focuses solely on determining whether an email contains meeting-related
    content, acting as the gateway for further detailed analysis in the 
    three-stage email analysis pipeline.
    
    Implements comprehensive DEBUG level logging for:
    - Complete model input/output tracking
    - Detailed error state documentation
    - Processing flow monitoring
    - Decision point logging
    """
    
    def __init__(self):
        """
        Initialize analyzer with required Groq client and configuration.
        
        Sets up the EnhancedGroqClient connection and loads model configuration
        parameters from the centralized analyzer configuration.
        """
        self.client = EnhancedGroqClient()
        self.model_config = ANALYZER_CONFIG["default_analyzer"]["model"]
        logger.debug(
            f"LlamaAnalyzer initialized with model configuration: "
            f"{json.dumps(self.model_config, indent=2)}"
        )
        
    async def classify_email(
        self,
        message_id: str,
        subject: str,
        content: str,
        sender: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if an email is meeting-related through binary classification.
        
        Implements the first stage of the analysis pipeline by performing
        binary classification on email content to identify meeting-related
        information. This serves as a gateway filter before more detailed
        analysis in subsequent pipeline stages.
        
        Args:
            message_id: Unique identifier for the email
            subject: Email subject line
            content: Email body content
            sender: Email sender address
            
        Returns:
            Tuple of (is_meeting: bool, error: Optional[str])
        """
        try:
            logger.info(f"Starting initial classification for email {message_id}")
            
            # Log input data at debug level with proper information masking
            logger.debug(
                f"Classification input for {message_id}:\n"
                f"Subject: {subject}\n"
                f"Sender: {self._mask_email(sender)}\n"
                f"Content length: {len(content)} characters\n"
                f"Content preview: {content[:100]}..." if len(content) > 100 else content
            )
            
            # Construct focused classification prompt
            prompt = self._construct_classification_prompt(subject, content)
            
            # Prepare messages for the API
            messages = [
                {"role": "system", "content": "You are a binary email classifier. Analyze the email and respond with EXACTLY 'meeting' or 'not_meeting'."},
                {"role": "user", "content": prompt}
            ]
            
            # Log the API request details
            logger.debug(
                f"Sending API request for {message_id} with configuration:\n"
                f"Model: {self.model_config['name']}\n"
                f"Temperature: {0.3}\n"
                f"Max tokens: {10}\n"
                f"Messages: {json.dumps(messages, indent=2)}"
            )
            
            # Process with Groq API
            start_time = datetime.now()
            response = await self.client.process_with_retry(
                messages=messages,
                model=self.model_config["name"],
                temperature=0.3,  # Low temperature for consistent binary classification
                max_completion_tokens=10  # Minimal tokens needed for binary response
            )
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Log the complete API response
            logger.debug(
                f"API response for {message_id} (processing time: {processing_time:.3f}s):\n"
                f"{json.dumps(self._extract_response_for_logging(response), indent=2)}"
            )
            
            # Extract and normalize response
            classification = response.choices[0].message.content.strip().lower()
            is_meeting = classification == "meeting"
            
            logger.info(
                f"Completed classification for {message_id}: meeting={is_meeting} "
                f"(processing time: {processing_time:.3f}s)"
            )
            
            # Log the decision point
            logger.debug(f"Classification decision for {message_id}: {classification} → is_meeting={is_meeting}")
            
            return is_meeting, None
            
        except Exception as e:
            # Capture full error context
            error_msg = f"Classification failed: {str(e)}"
            stack_trace = traceback.format_exc()
            
            # Log comprehensive error information
            logger.error(
                f"Error classifying email {message_id}: {error_msg}\n"
                f"Stack trace: {stack_trace}"
            )
            
            # Return error state following error handling protocol
            return False, error_msg

    def _construct_classification_prompt(self, subject: str, content: str) -> str:
        """
        Construct focused prompt for binary meeting classification.
        
        Creates a prompt that emphasizes clear binary classification without
        requesting additional analysis or details. The prompt is designed
        for optimal performance with the Llama model focused on the binary
        classification task.
        
        Args:
            subject: Email subject line
            content: Email body content
            
        Returns:
            Formatted prompt string optimized for binary classification
        """
        prompt = f"""
        Determine if this email is related to a meeting, gathering, or appointment.
        
        Subject: {subject}
        
        Content:
        {content}
        
        Respond with ONLY:
        'meeting' - if the email is about scheduling, discussing, or coordinating any type of meeting
        'not_meeting' - for all other email content
        """
        
        logger.debug(f"Constructed classification prompt of length {len(prompt)}")
        return prompt
    
    def _extract_response_for_logging(self, response: Any) -> Dict[str, Any]:
        """
        Extract relevant information from the API response for logging.
        
        Creates a structured representation of the API response suitable
        for logging while handling potential serialization issues.
        
        Args:
            response: Raw API response object
            
        Returns:
            Dictionary containing structured response data
        """
        try:
            # Extract only the necessary fields for logging
            return {
                "choices": [
                    {
                        "message": {
                            "content": choice.message.content,
                            "role": choice.message.role
                        },
                        "index": choice.index,
                        "finish_reason": choice.finish_reason
                    }
                    for choice in response.choices
                ],
                "created": response.created,
                "model": response.model,
                # Add any other relevant fields that should be logged
            }
        except Exception as e:
            logger.warning(f"Error extracting response for logging: {e}")
            return {"error": "Unable to extract response data for logging"}
    
    def _mask_email(self, email: str) -> str:
        """
        Mask email addresses for privacy in logs.
        
        Implements privacy protection by masking parts of email addresses
        while preserving enough information for debugging purposes.
        
        Args:
            email: Email address to mask
            
        Returns:
            Masked email address
        """
        if not email or '@' not in email:
            return email
            
        try:
            username, domain = email.split('@', 1)
            if len(username) <= 2:
                masked_username = '*' * len(username)
            else:
                masked_username = username[0] + '*' * (len(username) - 2) + username[-1]
                
            domain_parts = domain.split('.')
            masked_domain = domain_parts[0][0] + '*' * (len(domain_parts[0]) - 1)
            
            return f"{masked_username}@{masked_domain}.{'.'.join(domain_parts[1:])}"
        except Exception:
            # If masking fails, return a generic masked value
            return "***@***.***"
