import base64
import json
import logging
import os
import re
from datetime import datetime
from email.mime.text import MIMEText
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

from src.email_processing.models import EmailMetadata
from src.integrations.gmail.client import GmailClient
from src.integrations.groq.client_wrapper import EnhancedGroqClient

logger = logging.getLogger(__name__)
load_dotenv(override=True)

class EmailAgent:
    """Agent for processing and responding to emails with AI-first approach."""
    
    def __init__(self):
        """Initialize the email agent with necessary clients and configurations."""
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.gmail = GmailClient()
        self.groq_client = EnhancedGroqClient()
        self.load_response_log()
        
    def load_response_log(self):
        """Load or create the response log that tracks all email responses."""
        try:
            with open('data/email_responses.json', 'r') as f:
                content = f.read().strip()
                if content:
                    self.response_log = json.load(f)
                else:
                    self.response_log = {"responses": []}
        except (FileNotFoundError, json.JSONDecodeError):
            self.response_log = {"responses": []}
            os.makedirs('data', exist_ok=True)
            with open('data/email_responses.json', 'w') as f:
                json.dump(self.response_log, f, indent=2)

    def save_response_log(self, email_id: str, response_data: Dict):
        """Save a new response to the log with timestamp."""
        self.response_log["responses"].append({
            "email_id": email_id,
            "response_time": datetime.now().isoformat(),
            "response_data": response_data
        })
        with open('data/email_responses.json', 'w') as f:
            json.dump(self.response_log, f, indent=2)

    def has_responded(self, email_id: str) -> bool:
        """Check if we've already responded to this email."""
        return any(r["email_id"] == email_id for r in self.response_log["responses"])

    async def verify_meeting_parameters_ai(self, content: str, subject: str) -> Tuple[Dict, bool]:
        """
        Use Groq AI to verify meeting parameters and identify missing information.
        
        Args:
            content: Email content to analyze
            subject: Email subject line
            
        Returns:
            Tuple of (parameter_analysis, success_flag)
        """
        try:
            # Detailed system prompt for parameter verification
            system_prompt = """You are an expert meeting coordinator. Analyze the email content 
            and identify if all required meeting parameters are provided. Extract and verify:
            1. Meeting date (must be a specific date)
            2. Meeting time (must be a specific hour)
            3. Meeting location (physical location or virtual meeting link)
            4. Meeting agenda/purpose

            Respond in JSON format:
            {
                "parameters": {
                    "date": {"found": boolean, "value": string or null, "confidence": float},
                    "time": {"found": boolean, "value": string or null, "confidence": float},
                    "location": {"found": boolean, "value": string or null, "confidence": float},
                    "agenda": {"found": boolean, "value": string or null, "confidence": float}
                },
                "missing_parameters": [string],
                "has_all_required": boolean,
                "overall_confidence": float
            }
            
            For confidence scores:
            - 1.0: Explicitly stated and clear
            - 0.7-0.9: Strongly implied or contextually clear
            - 0.4-0.6: Somewhat unclear or ambiguous
            - <0.4: Very uncertain or likely missing"""

            # Process with Groq AI
            response = await self.groq_client.process_with_retry(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Subject: {subject}\n\nContent: {content}"}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result, True

        except Exception as e:
            logger.error(f"AI parameter verification failed: {e}")
            return self._fallback_parameter_check(content), False

    def _fallback_parameter_check(self, content: str) -> Dict:
        """
        Fallback method using pattern matching to check meeting parameters.
        Used when AI verification fails.
        """
        info = self.extract_meeting_info(content)
        
        # Default confidence for pattern matching is 0.6
        return {
            "parameters": {
                "date": {"found": False, "value": None, "confidence": 0.0},
                "time": {"found": False, "value": None, "confidence": 0.0},
                "location": {
                    "found": bool(info['location']),
                    "value": info['location'],
                    "confidence": 0.6 if info['location'] else 0.0
                },
                "agenda": {
                    "found": bool(info['agenda']),
                    "value": info['agenda'],
                    "confidence": 0.6 if info['agenda'] else 0.0
                }
            },
            "missing_parameters": [
                param for param, details in {
                    "date": True,
                    "time": True,
                    "location": not info['location'],
                    "agenda": not info['agenda']
                }.items() if details
            ],
            "has_all_required": False,
            "overall_confidence": 0.6 if (info['location'] and info['agenda']) else 0.3
        }

    def extract_meeting_info(self, content: str) -> Dict[str, Optional[str]]:
        """Extract meeting information using pattern matching (fallback method)."""
        info = {
            'location': None,
            'agenda': None
        }
        
        location_patterns = [
            r'at\s+([^\.!?\n]+)',
            r'in\s+([^\.!?\n]+)',
            r'location:\s*([^\.!?\n]+)',
            r'meet\s+(?:at|in)\s+([^\.!?\n]+)'
        ]

        agenda_patterns = [
            r'(?:about|discuss|regarding|re:|topic:|agenda:)\s+([^\.!?\n]+)',
            r'for\s+([^\.!?\n]+\s+(?:meeting|discussion|sync|catch-up))',
            r'purpose:\s*([^\.!?\n]+)'
        ]

        for pattern in location_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                info['location'] = match.group(1).strip()
                break

        for pattern in agenda_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                info['agenda'] = match.group(1).strip()
                break

        return info

    def _format_missing_parameters(self, missing_params: List[str]) -> str:
        """Format the list of missing parameters into a natural language request."""
        if not missing_params:
            return ""

        parameter_names = {
            "date": "the meeting date",
            "time": "the meeting time",
            "location": "the meeting location",
            "agenda": "the meeting agenda/purpose"
        }

        readable_params = [parameter_names.get(param, param) for param in missing_params]

        if len(readable_params) == 1:
            return readable_params[0]
        elif len(readable_params) == 2:
            return f"{readable_params[0]} and {readable_params[1]}"
        else:
            readable_params[-1] = f"and {readable_params[-1]}"
            return ", ".join(readable_params)

    async def create_response(self, metadata: EmailMetadata) -> Optional[str]:
        """
        Create an appropriate response based on email metadata and AI analysis.
        Uses AI-first approach with pattern matching as fallback.
        """
        try:
            sender_name = metadata.sender.split('<')[0].strip()
            if not sender_name:
                sender_name = metadata.sender

            # Verify parameters using AI
            ai_analysis, ai_success = await self.verify_meeting_parameters_ai(
                metadata.raw_content, 
                metadata.subject
            )

            # Log the analysis results
            logger.info(f"Parameter analysis for {metadata.message_id}: {json.dumps(ai_analysis)}")

            if not ai_analysis["has_all_required"]:
                missing_info = self._format_missing_parameters(ai_analysis["missing_parameters"])
                
                return f"""Dear {sender_name},

Thank you for your meeting request. To help me properly schedule our meeting, could you please specify {missing_info}?

Best regards,
Ivaylo's AI Assistant"""
            parameter_names = {
                "date": "the meeting date",
                "time": "the meeting time",
                "location": "the meeting location",
                "agenda": "the meeting agenda/purpose"
            }
                        # If all parameters are present, verify confidence
            params = ai_analysis["parameters"]
            if ai_analysis["overall_confidence"] < 0.7:
                # Ask for confirmation when confidence is low
                verification_text = []
                for param, details in params.items():
                    if details["confidence"] < 0.7:
                        verification_text.append(f"{parameter_names[param]} ({details['value']})")
                
                verify_items = self._format_missing_parameters(verification_text)
                return f"""Dear {sender_name},

Thank you for your meeting request. Could you please confirm {verify_items}?

Best regards,
Ivaylo's AI Assistant"""

            # Create confirmation with all parameters
            return f"""Dear {sender_name},

Thank you for your meeting request. I am pleased to confirm our meeting on {params['date']['value']} at {params['time']['value']} at {params['location']['value']} to discuss {params['agenda']['value']}.

Best regards,
Ivaylo's AI Assistant"""

        except Exception as e:
            logger.error(f"Error in AI-based response creation: {e}")
            # Fallback to pattern-based response creation
            response = self._create_fallback_response(metadata)
            if response:
                logger.info(f"Successfully created fallback response for {metadata.message_id}")
            return response

    def send_email(self, to_email: str, subject: str, message_text: str) -> bool:
        """Send an email using Gmail API."""
        message = MIMEText(message_text)
        message['to'] = to_email
        message['subject'] = subject

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

        try:
            self.gmail.service.users().messages().send(
                userId="me",
                body={'raw': raw_message}
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    async def process_email(self, metadata: EmailMetadata) -> bool:
    # """
    # Process an email and send appropriate response.
    # This method is called by the EmailProcessor.
    
    # Implements comprehensive email processing with:
    # - Duplicate detection
    # - Response generation (or using provided template)
    # - Email sending
    # - Response logging
    
    # Args:
    #     metadata: Comprehensive email metadata including analysis results
        
    # Returns:
    #     bool: True if email successfully processed and responded to
    # """
        try:
            if self.has_responded(metadata.message_id):
                logger.info(f"Already responded to email {metadata.message_id}")
                return True

            # Check if a pre-generated response template is provided
            if metadata.analysis_data and 'response_template' in metadata.analysis_data:
                response_text = metadata.analysis_data['response_template']
                logger.info(f"Using provided response template for {metadata.message_id}")
            else:
                # Generate response if not provided
                response_text = await self.create_response(metadata)
                
            if not response_text:
                logger.error("Failed to create response")
                return False

            subject = metadata.subject if metadata.subject else "Meeting Request"
            subject_prefix = "Re: " if not subject.startswith("Re:") else ""
            full_subject = f"{subject_prefix}{subject}"

            success = self.send_email(
                to_email=metadata.sender,
                subject=full_subject,
                message_text=response_text
            )

            if success:
                self.save_response_log(metadata.message_id, {
                    "sender": metadata.sender,
                    "subject": metadata.subject,
                    "response": response_text
                })
                return True

            return False

        except Exception as e:
            logger.error(f"Error processing email {metadata.message_id}: {e}")
            return False
