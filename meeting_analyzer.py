import logging
from typing import Tuple, Dict, Optional
from email.message import Message
from src.email_processing.analyzers import DeepseekAnalyzer

logger = logging.getLogger(__name__)

class MeetingEmailAnalyzer:
    def __init__(self, groq_client):
        logger.info("Initializing MeetingEmailAnalyzer")
        self.deepseek_analyzer = DeepseekAnalyzer(groq_client)

    async def analyze_meeting_email(self, message_id: str, subject: str, content: str, sender: str) -> Tuple[str, Dict]:
        """
        Analyze an email using DeepSeek R1 model to determine appropriate action.

        Args:
            message_id (str): Unique identifier for the email
            subject (str): Email subject
            content (str): Email content
            sender (str): Email sender

        Returns:
            Tuple[str, Dict]: A tuple containing the recommendation and analysis results
        """
        logger.info(f"Analyzing email {message_id} with DeepSeek R1 model")
        
        analysis_result = await self.deepseek_analyzer.analyze_email(
            email_content=content,
            subject=subject,
            sender=sender
        )

        action = self.deepseek_analyzer.decide_action(analysis_result)

        if action == "respond":
            recommendation = "needs_standard_response"
            analysis = {
                "is_meeting": True,
                "action": action,
                "response_text": analysis_result.response_text,
                "confidence": analysis_result.confidence
            }
        elif action == "flag_for_review":
            recommendation = "needs_review"
            analysis = {
                "is_meeting": True,
                "action": action,
                "confidence": analysis_result.confidence
            }
        else:
            recommendation = "needs_standard_response"
            analysis = {
                "is_meeting": False,
                "action": action,
                "confidence": analysis_result.confidence
            }

        return recommendation, analysis
