import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.integrations.groq.client_wrapper import EnhancedGroqClient
from src.integrations.groq.model_manager import ModelManager
from src.email_processing.models import EmailMetadata, EmailTopic

logger = logging.getLogger(__name__)

class EmailClassifier:
    """
    Classifies emails by topic and determines if they require a response.
    Uses AI-first approach with pattern matching fallback.
    """
    
    def __init__(self):
        """Initialize classifier with model manager and pattern fallbacks."""
        self.model_manager = ModelManager()
        self.groq_client = EnhancedGroqClient()
        
        # Fallback patterns for when AI is unavailable
        self.topic_patterns: Dict[EmailTopic, List[str]] = {
            EmailTopic.MEETING: [
                "schedule meeting", "meeting request", "let's meet",
                "calendar invite", "schedule time", "schedule a call",
                "meeting availability", "when are you free",
                "zoom", "teams", "google meet"
            ]
        }
        
        self.response_required_patterns = [
            "please respond", "let me know", "confirm", "rsvp",
            "your thoughts", "what do you think", "get back to me",
            "need your input", "your feedback", "please reply",
            "can you", "would you", "?"
        ]

    def _normalize_text(self, text: Optional[str]) -> str:
        """Normalize text for pattern matching."""
        if text is None:
            return ""
        return text.lower().strip()

    def _contains_pattern(self, text: str, patterns: List[str]) -> bool:
        """Check if text contains any of the patterns."""
        normalized_text = self._normalize_text(text)
        return any(pattern in normalized_text for pattern in patterns)

    async def _determine_topic_llm(self, subject: str, content: str) -> EmailTopic:
        """
        Use LLM to determine email topic.
        Implements retry logic and fallback to pattern matching.
        """
        try:
            model_config = self.model_manager.get_model_config('email_classification')
            logger.info(f"Using model {model_config['name']} for topic classification")
            
            prompt = [
                {"role": "system", "content": "You are an email classifier. Analyze the email and determine if it's about scheduling a meeting. Respond with ONLY 'meeting' or 'unknown'."},
                {"role": "user", "content": f"Subject: {subject}\n\nContent: {content}"}
            ]
            logger.info(f"Sending prompt to model: {json.dumps(prompt, indent=2)}")
            
            start_time = time.time()
            response = await self.groq_client.process_with_retry(
                messages=prompt,
                model=model_config['name'],
                temperature=0.1,
                max_completion_tokens=10
            )
            duration = time.time() - start_time
            
            result = response.choices[0].message.content.strip().lower()
            logger.info(f"Model response received in {duration:.2f}s: {result}")
            print(f"Topic classification model response: {result}")  # Add this line
            
            return EmailTopic.MEETING if result == 'meeting' else EmailTopic.UNKNOWN
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}, falling back to pattern matching")
            return self._determine_topic_patterns(subject, content)
    
    def _determine_topic_patterns(self, subject: str, content: str) -> EmailTopic:
        """Fallback pattern-based topic determination."""
        logger.info("Falling back to pattern matching for topic determination")
        normalized_subject = self._normalize_text(subject)
        normalized_content = self._normalize_text(content)
        
        logger.info(f"Checking patterns for subject: {normalized_subject}")
        logger.info(f"Checking patterns for content: {normalized_content[:100]}...")
        
        for topic, patterns in self.topic_patterns.items():
            if self._contains_pattern(normalized_subject, patterns):
                logger.info(f"Found matching pattern in subject for topic: {topic.value}")
                return topic
            if self._contains_pattern(normalized_content, patterns):
                logger.info(f"Found matching pattern in content for topic: {topic.value}")
                return topic
        
        logger.info("No matching patterns found, returning UNKNOWN topic")
        return EmailTopic.UNKNOWN

    async def _requires_response_llm(self, subject: str, content: str) -> bool:
        """
        Use LLM to determine if email requires response.
        Implements retry logic and fallback to pattern matching.
        """
        try:
            model_config = self.model_manager.get_model_config('email_classification')
            logger.info(f"Using model {model_config['name']} for response requirement check")
            
            prompt = [
                {"role": "system", "content": "You are an email analyzer. Determine if this email requires a response. Respond with ONLY 'yes' or 'no'."},
                {"role": "user", "content": f"Subject: {subject}\n\nContent: {content}"}
            ]
            logger.info(f"Sending prompt to model: {json.dumps(prompt, indent=2)}")
            
            start_time = time.time()
            response = await self.groq_client.process_with_retry(
                messages=prompt,
                model=model_config['name'],
                temperature=0.1,
                max_completion_tokens=10
            )
            duration = time.time() - start_time
            
            result = response.choices[0].message.content.strip().lower()
            logger.info(f"Model response received in {duration:.2f}s: {result}")
            print(f"Response requirement model response: {result}")  # Add this line
            
            return result == 'yes'
            
        except Exception as e:
            logger.error(f"LLM response check failed: {e}, falling back to pattern matching")
            return self._requires_response_patterns(subject, content)
    
    def _requires_response_patterns(self, subject: str, content: str) -> bool:
        """Fallback pattern-based response check."""
        logger.info("Falling back to pattern matching for response requirement check")
        normalized_text = f"{self._normalize_text(subject)} {self._normalize_text(content)}"
        logger.info(f"Checking response patterns in combined text: {normalized_text[:100]}...")
        result = self._contains_pattern(normalized_text, self.response_required_patterns)
        logger.info(f"Response requirement determination: {result}")
        return result

    async def classify_email(self, 
                           message_id: str,
                           subject: str,
                           sender: str,
                           content: str,
                           received_at: datetime) -> EmailMetadata:
        """
        Classify an email and determine if it requires a response.
        Uses AI-first approach with pattern matching fallback.
        
        Args:
            message_id: Unique identifier for the email
            subject: Email subject line
            sender: Email sender address
            content: Email body content
            received_at: When the email was received
            
        Returns:
            EmailMetadata containing classification results
        """
        try:
            logger.info(f"Starting classification for email {message_id}")
            logger.info(f"Email details - Subject: {subject}, Sender: {sender}")
            
            start_time = time.time()
            
            # Run topic and response requirement checks in parallel
            topic, requires_response = await asyncio.gather(
                self._determine_topic_llm(subject, content),
                self._requires_response_llm(subject, content)
            )
            
            metadata = EmailMetadata(
                message_id=message_id,
                subject=subject,
                sender=sender,
                received_at=received_at,
                topic=topic,
                requires_response=requires_response,
                raw_content=content
            )
            
            duration = time.time() - start_time
            logger.info(f"Classification completed in {duration:.2f}s")
            logger.info(f"Classification result - Topic: {topic.value}, Requires Response: {requires_response}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error classifying email {message_id}: {e}")
            # Return as unknown topic that doesn't require response
            return EmailMetadata(
                message_id=message_id,
                subject=subject,
                sender=sender,
                received_at=received_at,
                topic=EmailTopic.UNKNOWN,
                requires_response=False,
                raw_content=content
            )

class EmailRouter:
    """
    Routes classified emails to appropriate agents.
    Handles asynchronous processing and agent coordination.
    """
    
    def __init__(self):
        """Initialize router with classifier and agent registry."""
        self.classifier = EmailClassifier()
        self.agents: Dict[EmailTopic, object] = {}
        
    def register_agent(self, topic: EmailTopic, agent: object):
        """Register an agent to handle a specific email topic."""
        if not hasattr(agent, 'process_email'):
            raise ValueError(f"Agent for topic {topic.value} must implement process_email method")
            
        self.agents[topic] = agent
        logger.info(f"Registered agent for topic: {topic.value}")
        
    async def process_email(self,
                          message_id: str,
                          subject: str,
                          sender: str,
                          content: str,
                          received_at: datetime) -> Tuple[bool, Optional[str]]:
        """
        Process an email by classifying it and routing to appropriate agent.
        
        Args:
            message_id: Unique identifier for the email
            subject: Email subject line
            sender: Email sender address
            content: Email body content
            received_at: When the email was received
            
        Returns:
            Tuple of (should_mark_read: bool, error_message: Optional[str])
        """
        try:
            logger.info(f"Starting email processing for {message_id}")
            start_time = time.time()
            
            # Classify the email
            metadata = await self.classifier.classify_email(
                message_id=message_id,
                subject=subject,
                sender=sender,
                content=content,
                received_at=received_at
            )
            
            # If no response required, keep unread
            if not metadata.requires_response:
                logger.info(f"Email {message_id} does not require response, keeping unread")
                return False, None
                
            # Get the appropriate agent
            agent = self.agents.get(metadata.topic)
            if not agent:
                logger.warning(f"No agent registered for topic: {metadata.topic.value}")
                return False, f"No agent available for topic: {metadata.topic.value}"
                
            # Process with agent
            try:
                if asyncio.iscoroutinefunction(agent.process_email):
                    # Handle async agent
                    success = await agent.process_email(metadata)
                else:
                    # Handle sync agent
                    success = await asyncio.to_thread(agent.process_email, metadata)
                
                if success:
                    duration = time.time() - start_time
                    logger.info(f"Successfully processed email {message_id} with {metadata.topic.value} agent in {duration:.2f}s")
                    return True, None
                return False, f"Agent processing failed for {message_id}"
                
            except Exception as e:
                error_msg = f"Agent error processing email {message_id}: {e}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error routing email {message_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
