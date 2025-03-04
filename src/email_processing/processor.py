"""
Enhanced Email Processing Implementation

Implements a sophisticated three-stage email analysis pipeline with comprehensive
error handling, logging, and state management. Coordinates between specialized
analyzers while maintaining proper processing state and data integrity.
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.email_processing.models import EmailMetadata, EmailTopic
from src.email_processing.classification.classifier import EmailRouter
from src.email_processing.handlers.content import ContentPreprocessor
from src.email_processing.handlers.date_service import EmailDateService
from src.email_processing.analyzers.llama import LlamaAnalyzer
from src.email_processing.analyzers.deepseek import DeepseekAnalyzer
from src.email_processing.analyzers.response_categorizer import ResponseCategorizer
from src.integrations.gmail.client import GmailClient
from src.storage.secure import SecureStorage
from src.email_processing.handlers.writer import EmailAgent

logger = logging.getLogger(__name__)

class EmailProcessor:
    """
    Sophisticated email processor implementing three-stage analysis pipeline.
    
    Coordinates between specialized analyzers for comprehensive email understanding:
    1. Initial meeting classification (LlamaAnalyzer)
    2. Detailed content analysis (DeepseekAnalyzer)
    3. Final categorization and response generation (ResponseCategorizer)
    
    Implements robust error handling, comprehensive logging, and proper state
    management throughout the processing pipeline.
    """
    
    def __init__(self, 
                 gmail_client: GmailClient,
                 llama_analyzer: LlamaAnalyzer,
                 deepseek_analyzer: DeepseekAnalyzer,
                 response_categorizer: ResponseCategorizer,
                 storage_path: str = "data/secure",
                 strict_date_parsing: bool = True):
        """
        Initialize the email processor with required components.
        
        Args:
            gmail_client: Client for Gmail API interactions
            llama_analyzer: Initial meeting classification analyzer
            deepseek_analyzer: Detailed content analysis component
            response_categorizer: Final categorization and response generator
            storage_path: Path for secure storage of processing records
            strict_date_parsing: Whether to enforce strict date validation
        """
        self.gmail = gmail_client
        self.llama_analyzer = llama_analyzer
        self.deepseek_analyzer = deepseek_analyzer
        self.response_categorizer = response_categorizer
        self.storage = SecureStorage(storage_path)
        self.content_processor = ContentPreprocessor()
        self.strict_date_parsing = strict_date_parsing
        self.agents = {}

        # Ensure storage directory exists
        Path(storage_path).mkdir(parents=True, exist_ok=True)
        logger.info("EmailProcessor initialized successfully")

    def register_agent(self, topic: EmailTopic, agent: any) -> None:
        """
        Register an agent to handle specific email topics.
        
        Implements agent registration for specialized email handling.
        Each agent is mapped to a specific EmailTopic and must implement
        the required interface for email processing.
        
        Args:
            topic: EmailTopic enum value indicating handled email type
            agent: Agent instance implementing required processing interface
            
        Raises:
            ValueError: If agent doesn't implement required methods
        """
        if not hasattr(agent, 'process_email'):
            raise ValueError(f"Agent for topic {topic.value} must implement process_email method")
            
        self.agents[topic] = agent
        logger.info(f"Registered agent for topic: {topic.value}")

    async def _process_single_email(self, email: Dict) -> Tuple[bool, Optional[str]]:
        """
        Process a single email through the three-stage analysis pipeline.
        
        Implements comprehensive email analysis through coordinated stages:
        1. Initial meeting classification using LlamaAnalyzer
        2. Detailed content analysis using DeepseekAnalyzer for meeting emails
        3. Final categorization and response generation using ResponseCategorizer
        
        Maintains proper error handling and state management throughout the
        pipeline, ensuring reliable processing and appropriate response generation.
        
        Args:
            email: Dictionary containing email data and metadata
            
        Returns:
            Tuple containing (success_flag: bool, error_message: Optional[str])
        """
        message_id = email.get("message_id")
        try:
            logger.info(f"Starting pipeline processing for email {message_id}")
            
            # Stage 1: Initial Classification with LlamaAnalyzer
            is_meeting, llama_error = await self.llama_analyzer.classify_email(
                message_id=message_id,
                subject=email.get("subject", ""),
                content=email.get("processed_content", ""),
                sender=email.get("sender", "")
            )
            
            if llama_error:
                logger.error(f"LlamaAnalyzer error: {llama_error}")
                return False, f"Initial classification failed: {llama_error}"
                
            if not is_meeting:
                logger.info(f"Email {message_id} classified as non-meeting")
                await self.storage.add_record(email)
                return True, None
                
            # Stage 2: Detailed Analysis with DeepseekAnalyzer
            analysis_data, response_text, recommendation, deepseek_error = await self.deepseek_analyzer.analyze_email(
                email_content=email.get("processed_content", "")
            )
            
            if deepseek_error:
                logger.error(f"DeepseekAnalyzer error: {deepseek_error}")
                return False, f"Detailed analysis failed: {deepseek_error}"
                
            # Stage 3: Final Categorization and Response Generation
            category, response_template = await self.response_categorizer.categorize_email(
                analysis_data=analysis_data,
                response_text=response_text,
                deepseek_recommendation=recommendation,
                deepseek_summary=analysis_data.get("summary", "")
            )
            
            # Update email metadata with processing results
            email["analysis_results"] = {
                "is_meeting": is_meeting,
                "analysis_data": analysis_data,
                "response_text": response_text,
                "deepseek_recommendation": recommendation,
                "final_category": category,
                "processed_at": datetime.now().isoformat(),
                "requires_response": response_template is not None
            }
            
            # Handle email based on categorization
            await self._handle_categorized_email(
                message_id=message_id,
                category=category,
                response_template=response_template,
                email_data=email
            )
            
            logger.info(f"Successfully processed email {message_id} as category: {category}")
            return True, None
            
        except Exception as e:
            error_msg = f"Pipeline error for {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    async def _handle_categorized_email(
    self,
    message_id: str,
    category: str,
    response_template: Optional[str],
    email_data: Dict
        ) -> None:
        
                # Handle email based on its final categorization.
                
                # Implements appropriate actions for each category:
                # - standard_response: Generate response via EmailAgent and mark as read
                # - needs_review: Keep unread for manual review
                # - ignore: Mark as read with no further action
                
                # Args:
                #     message_id: Unique identifier for the email
                #     category: Final categorization result
                #     response_template: Generated response text if applicable
                #     email_data: Complete email data dictionary
                # """
        try:
            # Register with agent in case it isn't already
            if EmailTopic.MEETING not in self.agents:
                email_agent = EmailAgent()
                self.register_agent(EmailTopic.MEETING, email_agent)
            
            email_agent = self.agents.get(EmailTopic.MEETING)
            
            if category == "standard_response" and response_template:
                # Create email metadata for the agent
                metadata = EmailMetadata(
                    message_id=message_id,
                    subject=email_data.get('subject', ''),
                    sender=email_data.get('sender', ''),
                    received_at=datetime.now(),
                    topic=EmailTopic.MEETING,
                    requires_response=True,
                    raw_content=email_data.get('content', ''),
                    analysis_data={
                        'response_template': response_template
                    }
                )
                
                # Process with the email agent to send response
                success = await email_agent.process_email(metadata)
                
                if success:
                    self.gmail.mark_as_read(message_id)
                    logger.info(f"Sent response and marked email {message_id} as read")
                else:
                    logger.error(f"Failed to send response for email {message_id}")
                    
            elif category == "needs_review":
                # Keep email unread for manual review
                self.gmail.mark_as_unread(message_id)
                logger.info(f"Marked email {message_id} for review")
                
            else:  # ignore
                self.gmail.mark_as_read(message_id)
                logger.info(f"Marked email {message_id} as read (ignored)")
                
            # Store processing record
            await self.storage.add_record(email_data)
            
        except Exception as e:
            logger.error(f"Error handling categorized email {message_id}: {e}")
            raise

    async def process_email_batch(self, batch_size: int = 100) -> Tuple[int, int, List[str]]:
        """
        Process a batch of emails through the analysis pipeline.
        
        Implements batch processing with proper error handling and state tracking.
        Maintains processing history and prevents duplicate processing.
        
        Args:
            batch_size: Maximum number of emails to process in this batch
            
        Returns:
            Tuple containing (processed_count, error_count, error_messages)
        """
        processed_count = 0
        error_count = 0
        error_messages = []
        
        try:
            # Fetch unread emails
            unread_emails = await asyncio.to_thread(
                self.gmail.get_unread_emails,
                max_results=batch_size
            )
            logger.info(f"Found {len(unread_emails)} unread emails")
            
            # Process each email through the pipeline
            for email in unread_emails:
                message_id = email.get("message_id")
                
                try:
                    # Check processing history
                    is_processed, check_success = await self.storage.is_processed(message_id)
                    if not check_success:
                        error_msg = f"Failed to check processing status for {message_id}"
                        logger.error(error_msg)
                        error_count += 1
                        error_messages.append(error_msg)
                        continue
                        
                    if is_processed:
                        logger.info(f"Email {message_id} already processed, skipping")
                        continue
                        
                    # Process content
                    processed_content = self.content_processor.preprocess_content(
                        email.get("content", "")
                    )
                    email["processed_content"] = processed_content.content
                    
                    # Process through pipeline
                    success, error = await self._process_single_email(email)
                    if success:
                        processed_count += 1
                    else:
                        error_count += 1
                        error_messages.append(error)
                        
                except Exception as e:
                    error_msg = f"Error processing email {message_id}: {str(e)}"
                    logger.error(error_msg)
                    error_count += 1
                    error_messages.append(error_msg)
                    
            logger.info(f"Completed batch processing: {processed_count} processed, {error_count} errors")
            return processed_count, error_count, error_messages
            
        except Exception as e:
            error_msg = f"Batch processing error: {str(e)}"
            logger.error(error_msg)
            return 0, 1, [error_msg]
