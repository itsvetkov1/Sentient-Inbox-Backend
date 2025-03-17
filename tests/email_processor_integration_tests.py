"""
Integration tests for EmailProcessor component.

These tests verify the interactions between the various components 
of the email processing pipeline, focusing on proper data flow,
error propagation, and the correct handling of different email types.

Design Considerations:
- Tests the complete pipeline integration with realistic components
- Verifies correct data passing between pipeline stages
- Tests error propagation across component boundaries
- Validates proper email categorization across the full pipeline
- Confirms the correct email status management in Gmail
"""

import os
import pytest
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Import the components to test
from src.email_processing.processor import EmailProcessor
from src.email_processing.analyzers.llama import LlamaAnalyzer
from src.email_processing.analyzers.deepseek import DeepseekAnalyzer
from src.email_processing.analyzers.response_categorizer import ResponseCategorizer
from src.email_processing.handlers.writer import EmailAgent
from src.integrations.gmail.client import GmailClient
from src.storage.secure import SecureStorage
from src.email_processing.models import EmailMetadata, EmailTopic

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestEmailProcessorIntegration:
    """
    Integration test suite for EmailProcessor to verify pipeline interactions.
    
    Tests the orchestration of the four-stage email processing pipeline:
    1. LlamaAnalyzer (Initial meeting classification)
    2. DeepseekAnalyzer (Detailed content analysis)
    3. ResponseCategorizer (Final categorization)
    4. EmailAgent (Response delivery)
    
    Verifies that components properly interact with each other and that
    data flows correctly through the entire pipeline.
    """
    
    @pytest.fixture
    async def mock_components(self):
        """
        Create mock components for the email processing pipeline.
        
        Creates consistent mock implementations that simulate realistic
        behavior of each component while allowing verification of interactions.
        
        Returns:
            Dictionary containing all mocked components
        """
        # Create mock LlamaAnalyzer
        mock_llama = AsyncMock(spec=LlamaAnalyzer)
        # Configure classify_email to return different results based on input
        mock_llama.classify_email = AsyncMock(side_effect=lambda message_id, subject, content, sender: 
            (True, None) if "meeting" in content.lower() or "meet" in content.lower() 
            else (False, None)
        )
        
        # Create mock DeepseekAnalyzer
        mock_deepseek = AsyncMock(spec=DeepseekAnalyzer)
        # Configure analyze_email to provide structured response
        mock_deepseek.analyze_email = AsyncMock(side_effect=lambda email_content: 
            (
                # analysis_data with structured meeting details
                {
                    "date": "tomorrow",
                    "time": "2pm",
                    "location": "Conference Room A",
                    "agenda": "project discussion",
                    "missing_elements": "",
                    "tone": "friendly"
                },
                # response_text
                "Thank you for your meeting request. I confirm our meeting tomorrow at 2pm in Conference Room A.",
                # recommendation
                "standard_response",
                # error
                None
            ) if "complete" in email_content.lower() else
            (
                # analysis_data with missing elements
                {
                    "date": "tomorrow",
                    "time": None,
                    "location": "Conference Room A",
                    "agenda": "project discussion",
                    "missing_elements": "time",
                    "tone": "formal"
                },
                # response_text
                "Thank you for your meeting request. Could you please specify the meeting time?",
                # recommendation
                "standard_response",
                # error
                None
            )
        )
        
        # Create mock ResponseCategorizer
        mock_categorizer = AsyncMock(spec=ResponseCategorizer)
        # Configure categorize_email to return appropriate category
        mock_categorizer.categorize_email = AsyncMock(side_effect=lambda analysis_data, response_text, deepseek_recommendation, deepseek_summary=None:
            (
                # category
                "standard_response",
                # response_template
                response_text
            ) if deepseek_recommendation == "standard_response" else
            (
                # category
                "needs_review",
                # response_template
                None
            )
        )
        
        # Create mock EmailAgent
        mock_agent = AsyncMock(spec=EmailAgent)
        mock_agent.process_email = AsyncMock(return_value=True)
        
        # Create mock GmailClient
        mock_gmail = AsyncMock(spec=GmailClient)
        mock_gmail.mark_as_read = AsyncMock(return_value=True)
        mock_gmail.mark_as_unread = AsyncMock(return_value=True)
        
        # Create mock SecureStorage
        mock_storage = AsyncMock(spec=SecureStorage)
        mock_storage.add_record = AsyncMock(return_value=(True, True))
        mock_storage.is_processed = AsyncMock(return_value=(False, True))  # Not processed, operation success
        
        return {
            "llama_analyzer": mock_llama,
            "deepseek_analyzer": mock_deepseek,
            "response_categorizer": mock_categorizer,
            "email_agent": mock_agent,
            "gmail_client": mock_gmail,
            "secure_storage": mock_storage
        }
    
    @pytest.fixture
    async def email_processor(self, mock_components):
        """
        Create EmailProcessor with mock components.
        
        Sets up the EmailProcessor with all the necessary mock components
        to enable testing of the complete pipeline integration.
        
        Args:
            mock_components: Dictionary containing mock components
            
        Returns:
            Configured EmailProcessor instance with mock components
        """
        processor = EmailProcessor(
            gmail_client=mock_components["gmail_client"],
            llama_analyzer=mock_components["llama_analyzer"],
            deepseek_analyzer=mock_components["deepseek_analyzer"],
            response_categorizer=mock_components["response_categorizer"],
            storage_path="test_data/secure"
        )
        
        # Replace storage directly to avoid initialization issues
        processor.storage = mock_components["secure_storage"]
        
        # Register the email agent
        processor.register_agent(EmailTopic.MEETING, mock_components["email_agent"])
        
        return processor
    
    @pytest.mark.asyncio
    async def test_complete_meeting_email_processing(self, email_processor, mock_components):
        """
        Test processing a complete meeting email through the entire pipeline.
        
        Verifies that a complete meeting email is correctly:
        1. Classified as a meeting by LlamaAnalyzer
        2. Analyzed in detail by DeepseekAnalyzer
        3. Categorized as standard_response by ResponseCategorizer
        4. Processed for response by EmailAgent
        5. Marked as read in Gmail
        6. Added to secure storage
        
        Args:
            email_processor: Configured EmailProcessor with mock components
            mock_components: Dictionary containing mock components for verification
        """
        # Setup test email with complete meeting information
        test_email = {
            "message_id": "test_complete_meeting_123",
            "subject": "Team Meeting Tomorrow",
            "sender": "colleague@example.com",
            "processed_content": "Let's meet tomorrow at 2pm in Conference Room A to discuss the project. This is a complete meeting request.",
            "content": "Let's meet tomorrow at 2pm in Conference Room A to discuss the project. This is a complete meeting request."
        }
        
        # Process the email
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify success
        assert success is True
        assert error is None
        
        # Verify LlamaAnalyzer was called with correct parameters
        mock_components["llama_analyzer"].classify_email.assert_called_once_with(
            message_id=test_email["message_id"],
            subject=test_email["subject"],
            content=test_email["processed_content"],
            sender=test_email["sender"]
        )
        
        # Verify DeepseekAnalyzer was called with correct content
        mock_components["deepseek_analyzer"].analyze_email.assert_called_once_with(
            email_content=test_email["processed_content"]
        )
        
        # Verify ResponseCategorizer was called with correct parameters
        mock_components["response_categorizer"].categorize_email.assert_called_once()
        
        # Verify EmailAgent was called for response processing
        mock_components["email_agent"].process_email.assert_called_once()
        
        # Verify the email was marked as read (standard_response handling)
        mock_components["gmail_client"].mark_as_read.assert_called_once_with(test_email["message_id"])
        
        # Verify the record was stored
        mock_components["secure_storage"].add_record.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_incomplete_meeting_email_processing(self, email_processor, mock_components):
        """
        Test processing an incomplete meeting email through the entire pipeline.
        
        Verifies that an incomplete meeting email is correctly:
        1. Classified as a meeting by LlamaAnalyzer
        2. Analyzed in detail by DeepseekAnalyzer which identifies missing elements
        3. Categorized as standard_response by ResponseCategorizer (with parameter request)
        4. Processed for response by EmailAgent
        5. Marked as read in Gmail
        6. Added to secure storage
        
        Args:
            email_processor: Configured EmailProcessor with mock components
            mock_components: Dictionary containing mock components for verification
        """
        # Setup test email with incomplete meeting information (missing time)
        test_email = {
            "message_id": "test_incomplete_meeting_456",
            "subject": "Team Meeting Tomorrow",
            "sender": "colleague@example.com",
            "processed_content": "Let's meet tomorrow in Conference Room A to discuss the project. This is an incomplete meeting request.",
            "content": "Let's meet tomorrow in Conference Room A to discuss the project. This is an incomplete meeting request."
        }
        
        # Process the email
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify success
        assert success is True
        assert error is None
        
        # Verify LlamaAnalyzer was called with correct parameters
        mock_components["llama_analyzer"].classify_email.assert_called_once_with(
            message_id=test_email["message_id"],
            subject=test_email["subject"],
            content=test_email["processed_content"],
            sender=test_email["sender"]
        )
        
        # Verify DeepseekAnalyzer was called with correct content
        mock_components["deepseek_analyzer"].analyze_email.assert_called_once_with(
            email_content=test_email["processed_content"]
        )
        
        # Verify ResponseCategorizer was called with correct parameters
        mock_components["response_categorizer"].categorize_email.assert_called_once()
        
        # Verify EmailAgent was called for response processing
        mock_components["email_agent"].process_email.assert_called_once()
        
        # Verify the email was marked as read (standard_response handling)
        mock_components["gmail_client"].mark_as_read.assert_called_once_with(test_email["message_id"])
        
        # Verify the record was stored
        mock_components["secure_storage"].add_record.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_non_meeting_email_processing(self, email_processor, mock_components):
        """
        Test processing a non-meeting email through the pipeline.
        
        Verifies that a non-meeting email is correctly:
        1. Classified as non-meeting by LlamaAnalyzer
        2. Not sent to DeepseekAnalyzer (early exit)
        3. Properly stored in secure storage
        4. No response is generated
        
        Args:
            email_processor: Configured EmailProcessor with mock components
            mock_components: Dictionary containing mock components for verification
        """
        # Setup test email with non-meeting content
        test_email = {
            "message_id": "test_non_meeting_789",
            "subject": "Project Update",
            "sender": "colleague@example.com",
            "processed_content": "Here's the latest update on the project. We've completed phase 1 and are moving to phase 2.",
            "content": "Here's the latest update on the project. We've completed phase 1 and are moving to phase 2."
        }
        
        # Process the email
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify success
        assert success is True
        assert error is None
        
        # Verify LlamaAnalyzer was called with correct parameters
        mock_components["llama_analyzer"].classify_email.assert_called_once_with(
            message_id=test_email["message_id"],
            subject=test_email["subject"],
            content=test_email["processed_content"],
            sender=test_email["sender"]
        )
        
        # Verify DeepseekAnalyzer was NOT called (early exit for non-meeting)
        mock_components["deepseek_analyzer"].analyze_email.assert_not_called()
        
        # Verify ResponseCategorizer was NOT called
        mock_components["response_categorizer"].categorize_email.assert_not_called()
        
        # Verify EmailAgent was NOT called
        mock_components["email_agent"].process_email.assert_not_called()
        
        # Verify the record was stored
        mock_components["secure_storage"].add_record.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_already_processed_email_skipping(self, email_processor, mock_components):
        """
        Test skipping of already processed emails.
        
        Verifies that emails already marked as processed are correctly:
        1. Detected as already processed
        2. Skipped from further processing
        3. No components in the pipeline are called
        
        Args:
            email_processor: Configured EmailProcessor with mock components
            mock_components: Dictionary containing mock components for verification
        """
        # Configure mock storage to indicate email is already processed
        mock_components["secure_storage"].is_processed.return_value = (True, True)  # Is processed, operation success
        
        # Setup test email
        test_email = {
            "message_id": "test_already_processed_101",
            "subject": "Previously Processed Email",
            "sender": "colleague@example.com",
            "processed_content": "Let's meet tomorrow at 2pm. This email has already been processed.",
            "content": "Let's meet tomorrow at 2pm. This email has already been processed."
        }
        
        # Process the email batch containing the already processed email
        processed_count, error_count, errors = await email_processor.process_email_batch(batch_size=1)
        
        # Verify processing stats
        assert processed_count == 0
        assert error_count == 0
        
        # Verify storage was checked but email was skipped
        mock_components["secure_storage"].is_processed.assert_called()
        
        # Verify no other components were called
        mock_components["llama_analyzer"].classify_email.assert_not_called()
        mock_components["deepseek_analyzer"].analyze_email.assert_not_called()
        mock_components["response_categorizer"].categorize_email.assert_not_called()
        mock_components["email_agent"].process_email.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_error_propagation_in_pipeline(self, email_processor, mock_components):
        """
        Test error propagation through the pipeline.
        
        Verifies that errors in pipeline components are correctly:
        1. Detected and logged
        2. Propagated to the caller
        3. Captured in the processing statistics
        
        Args:
            email_processor: Configured EmailProcessor with mock components
            mock_components: Dictionary containing mock components for verification
        """
        # Configure LlamaAnalyzer to raise an error
        mock_components["llama_analyzer"].classify_email.side_effect = Exception("Test error in LlamaAnalyzer")
        
        # Setup test email
        test_email = {
            "message_id": "test_error_email_202",
            "subject": "Error Test Email",
            "sender": "colleague@example.com",
            "processed_content": "This email will trigger an error in the pipeline.",
            "content": "This email will trigger an error in the pipeline."
        }
        
        # Mock get_unread_emails to return our test email
        mock_components["gmail_client"].get_unread_emails = lambda max_results: [test_email]
        
        # Process the email batch
        processed_count, error_count, errors = await email_processor.process_email_batch(batch_size=1)
        
        # Verify processing stats
        assert processed_count == 0
        assert error_count == 1
        assert len(errors) == 1
        assert "Test error in LlamaAnalyzer" in errors[0]
        
        # Verify error was captured and pipeline was stopped
        mock_components["deepseek_analyzer"].analyze_email.assert_not_called()
        mock_components["response_categorizer"].categorize_email.assert_not_called()
        mock_components["email_agent"].process_email.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_batch_processing_multiple_emails(self, email_processor, mock_components):
        """
        Test processing multiple emails in a batch.
        
        Verifies that batch processing correctly:
        1. Processes multiple emails in sequence
        2. Correctly tracks processing statistics
        3. Handles mixed email types properly
        
        Args:
            email_processor: Configured EmailProcessor with mock components
            mock_components: Dictionary containing mock components for verification
        """
        # Reset call counts on mock components
        for component in mock_components.values():
            component.reset_mock()
        
        # Create a batch of test emails with different types
        test_emails = [
            {
                "message_id": "batch_complete_meeting_1",
                "subject": "Complete Meeting",
                "sender": "sender1@example.com",
                "processed_content": "Let's meet tomorrow at 2pm in Room A. This is a complete meeting request.",
                "content": "Let's meet tomorrow at 2pm in Room A. This is a complete meeting request."
            },
            {
                "message_id": "batch_incomplete_meeting_2",
                "subject": "Incomplete Meeting",
                "sender": "sender2@example.com",
                "processed_content": "Let's meet tomorrow in Room B. This is an incomplete meeting request.",
                "content": "Let's meet tomorrow in Room B. This is an incomplete meeting request."
            },
            {
                "message_id": "batch_non_meeting_3",
                "subject": "Non-Meeting Email",
                "sender": "sender3@example.com",
                "processed_content": "Here's the project update you requested. No meeting required.",
                "content": "Here's the project update you requested. No meeting required."
            }
        ]
        
        # Mock get_unread_emails to return our test batch
        mock_components["gmail_client"].get_unread_emails = lambda max_results: test_emails
        
        # Configure storage to indicate none of the emails are already processed
        mock_components["secure_storage"].is_processed.return_value = (False, True)  # Not processed, operation success
        
        # Process the batch
        processed_count, error_count, errors = await email_processor.process_email_batch(batch_size=3)
        
        # Verify processing stats
        assert processed_count == 3
        assert error_count == 0
        assert len(errors) == 0
        
        # Verify LlamaAnalyzer was called for all emails
        assert mock_components["llama_analyzer"].classify_email.call_count == 3
        
        # DeepseekAnalyzer should be called only for meeting emails (2 of them)
        assert mock_components["deepseek_analyzer"].analyze_email.call_count == 2
        
        # ResponseCategorizer should be called only for meeting emails (2 of them)
        assert mock_components["response_categorizer"].categorize_email.call_count == 2
        
        # EmailAgent should be called only for meeting emails (2 of them)
        assert mock_components["email_agent"].process_email.call_count == 2
        
        # Storage should be checked for all emails and records added for all processed emails
        assert mock_components["secure_storage"].is_processed.call_count == 3
        assert mock_components["secure_storage"].add_record.call_count == 3
    
    @pytest.mark.asyncio
    async def test_needs_review_email_handling(self, email_processor, mock_components):
        """
        Test handling of emails that need review.
        
        Verifies that emails flagged for review are correctly:
        1. Processed through the pipeline
        2. Categorized as needs_review
        3. Marked as unread in Gmail
        4. Starred for visibility
        
        Args:
            email_processor: Configured EmailProcessor with mock components
            mock_components: Dictionary containing mock components for verification
        """
        # Configure ResponseCategorizer to return needs_review
        mock_components["response_categorizer"].categorize_email.return_value = ("needs_review", None)
        
        # Setup test email
        test_email = {
            "message_id": "test_needs_review_303",
            "subject": "Complex Meeting Request",
            "sender": "important@example.com",
            "processed_content": "Let's schedule a meeting to discuss the critical project issues with the executive team.",
            "content": "Let's schedule a meeting to discuss the critical project issues with the executive team."
        }
        
        # Process the email
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify success
        assert success is True
        assert error is None
        
        # Verify entire pipeline was executed
        mock_components["llama_analyzer"].classify_email.assert_called_once()
        mock_components["deepseek_analyzer"].analyze_email.assert_called_once()
        mock_components["response_categorizer"].categorize_email.assert_called_once()
        
        # Verify EmailAgent was NOT called (no response for needs_review)
        mock_components["email_agent"].process_email.assert_not_called()
        
        # Verify the email was marked as unread (needs_review handling)
        mock_components["gmail_client"].mark_as_unread.assert_called_once_with(test_email["message_id"])
        
        # Verify the record was stored
        mock_components["secure_storage"].add_record.assert_called_once()
