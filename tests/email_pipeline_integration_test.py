"""
Integration Tests for Email Processing Pipeline

This module implements comprehensive integration testing for the four-stage
email processing pipeline, ensuring proper interaction between components:

1. LlamaAnalyzer - Initial meeting classification
2. DeepseekAnalyzer - Detailed content analysis
3. ResponseCategorizer - Response generation and categorization
4. EmailAgent - Response delivery and email status management

The tests validate end-to-end workflows, component integration,
error propagation, and overall system behavior under various scenarios.
"""

import pytest
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from unittest.mock import patch, MagicMock, AsyncMock

from src.email_processing.processor import EmailProcessor
from src.email_processing.analyzers.llama import LlamaAnalyzer
from src.email_processing.analyzers.deepseek import DeepseekAnalyzer
from src.email_processing.analyzers.response_categorizer import ResponseCategorizer
from src.email_processing.handlers.writer import EmailAgent
from src.email_processing.models import EmailMetadata, EmailTopic
from src.integrations.gmail.client import GmailClient
from src.integrations.groq.client_wrapper import EnhancedGroqClient
from src.storage.secure import SecureStorage

class TestEmailPipelineIntegration:
    """Integration test suite for the email processing pipeline."""

    @pytest.fixture
    def test_storage_path(self):
        """Create a temporary storage path for testing."""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        # Create required subdirectories
        os.makedirs(os.path.join(temp_dir, "backups"), exist_ok=True)
        
        yield temp_dir
        # Clean up
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_gmail_client(self):
        """Create a mock GmailClient for testing."""
        gmail_mock = MagicMock(spec=GmailClient)
        
        # Mock get_unread_emails to return test emails
        gmail_mock.get_unread_emails.return_value = [
            {
                "message_id": "meeting_email_id_1",
                "thread_id": "thread_1",
                "subject": "Meeting Tomorrow at 2pm",
                "sender": "sender@example.com",
                "content": "Let's meet tomorrow at 2pm in Conference Room A to discuss the project.",
                "received_at": datetime.now().isoformat(),
                "labels": ["UNREAD"]
            },
            {
                "message_id": "non_meeting_email_id_1",
                "thread_id": "thread_2",
                "subject": "Project Update",
                "sender": "updates@example.com",
                "content": "Here's the latest update on the project status. Please review the attached report.",
                "received_at": datetime.now().isoformat(),
                "labels": ["UNREAD"]
            }
        ]
        
        # Mock marking functions
        gmail_mock.mark_as_read.return_value = True
        gmail_mock.mark_as_unread.return_value = True
        
        # Mock send_email
        gmail_mock.send_email.return_value = True
        
        return gmail_mock

    @pytest.fixture
    def mock_llama_analyzer(self):
        """Create a mock LlamaAnalyzer for testing."""
        llama_mock = AsyncMock(spec=LlamaAnalyzer)
        
        # Define behavior for classify_email method
        async def mock_classify_email(message_id, subject, content, sender):
            # Classify as meeting if subject contains "meeting" or "meet"
            is_meeting = any(keyword in subject.lower() for keyword in ["meeting", "meet"])
            return is_meeting, None
            
        llama_mock.classify_email.side_effect = mock_classify_email
        
        return llama_mock

    @pytest.fixture
    def mock_deepseek_analyzer(self):
        """Create a mock DeepseekAnalyzer for testing."""
        deepseek_mock = AsyncMock(spec=DeepseekAnalyzer)
        
        # Define behavior for analyze_email method
        async def mock_analyze_email(email_content):
            # Detect meeting details in content
            has_time = "2pm" in email_content or "2 pm" in email_content
            has_location = "room" in email_content.lower() or "conference" in email_content.lower()
            has_agenda = "discuss" in email_content.lower() or "project" in email_content.lower()
            
            # Complete meeting details
            if has_time and has_location and has_agenda:
                analysis_data = {
                    "date": "tomorrow",
                    "time": "2pm",
                    "location": "Conference Room A",
                    "agenda": "discuss the project",
                    "completeness": "4/4",
                    "missing_elements": "None",
                    "detected tone": "Neutral"
                }
                response_text = (
                    "Thank you for your meeting request. I confirm our meeting tomorrow "
                    "at 2pm in Conference Room A to discuss the project."
                )
                recommendation = "standard_response"
            # Missing elements
            else:
                missing = []
                if not has_time:
                    missing.append("time")
                if not has_location:
                    missing.append("location")
                if not has_agenda:
                    missing.append("agenda")
                    
                missing_str = ", ".join(missing)
                completeness = f"{4-len(missing)}/4"
                
                analysis_data = {
                    "date": "tomorrow" if "tomorrow" in email_content else None,
                    "time": "2pm" if has_time else None,
                    "location": "Conference Room A" if has_location else None,
                    "agenda": "discuss the project" if has_agenda else None,
                    "completeness": completeness,
                    "missing_elements": missing_str,
                    "detected tone": "Neutral"
                }
                
                if len(missing) <= 1:  # Only missing one element
                    response_text = f"Thank you for your meeting request. Could you please provide the {missing_str}?"
                    recommendation = "standard_response"
                else:
                    response_text = "Your meeting request needs more details. I'll have someone review it."
                    recommendation = "needs_review"
            
            return analysis_data, response_text, recommendation, None
            
        deepseek_mock.analyze_email.side_effect = mock_analyze_email
        
        # Mock decide_action method
        deepseek_mock.decide_action.side_effect = lambda result: result
        
        return deepseek_mock

    @pytest.fixture
    def mock_response_categorizer(self):
        """Create a mock ResponseCategorizer for testing."""
        categorizer_mock = AsyncMock(spec=ResponseCategorizer)
        
        # Define behavior for categorize_email method
        async def mock_categorize_email(analysis_data, response_text, deepseek_recommendation, deepseek_summary=None):
            # Return category and response template based on recommendation
            return deepseek_recommendation, response_text
            
        categorizer_mock.categorize_email.side_effect = mock_categorize_email
        
        return categorizer_mock

    @pytest.fixture
    def mock_email_agent(self):
        """Create a mock EmailAgent for testing."""
        agent_mock = AsyncMock(spec=EmailAgent)
        
        # Define behavior for process_email method
        async def mock_process_email(metadata):
            # Always succeed in processing
            return True
            
        agent_mock.process_email.side_effect = mock_process_email
        
        return agent_mock

    @pytest.fixture
    def email_processor(self, test_storage_path, mock_gmail_client, mock_llama_analyzer, 
                      mock_deepseek_analyzer, mock_response_categorizer, mock_email_agent):
        """Create an EmailProcessor instance with mock components."""
        # Create real SecureStorage with test path
        secure_storage = SecureStorage(storage_path=test_storage_path)
        
        # Create EmailProcessor with mock components
        processor = EmailProcessor(
            gmail_client=mock_gmail_client,
            llama_analyzer=mock_llama_analyzer,
            deepseek_analyzer=mock_deepseek_analyzer,
            response_categorizer=mock_response_categorizer,
            storage_path=test_storage_path
        )
        
        # Override internal storage with our test instance
        processor.storage = secure_storage
        
        # Register mock email agent
        processor.register_agent(EmailTopic.MEETING, mock_email_agent)
        
        return processor

    @pytest.mark.asyncio
    async def test_process_single_email_meeting_complete(self, email_processor, mock_gmail_client,
                                                      mock_llama_analyzer, mock_deepseek_analyzer,
                                                      mock_response_categorizer, mock_email_agent):
        """
        Test processing a single complete meeting email through the pipeline.
        
        Verifies:
        - All pipeline stages are called with correct parameters
        - Email is properly classified as a meeting
        - Response is generated correctly
        - Email is marked as read
        - Email agent is called to process the response
        """
        # Create test email with complete meeting details
        test_email = {
            "message_id": "meeting_complete",
            "thread_id": "thread_complete",
            "subject": "Meeting Tomorrow at 2pm",
            "sender": "sender@example.com",
            "content": "Let's meet tomorrow at 2pm in Conference Room A to discuss the project.",
            "processed_content": "Let's meet tomorrow at 2pm in Conference Room A to discuss the project.",
            "received_at": datetime.now().isoformat(),
            "labels": ["UNREAD"]
        }
        
        # Process the email
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify success
        assert success is True
        assert error is None
        
        # Verify LlamaAnalyzer was called correctly
        mock_llama_analyzer.classify_email.assert_called_once_with(
            message_id="meeting_complete",
            subject="Meeting Tomorrow at 2pm",
            content="Let's meet tomorrow at 2pm in Conference Room A to discuss the project.",
            sender="sender@example.com"
        )
        
        # Verify DeepseekAnalyzer was called correctly
        mock_deepseek_analyzer.analyze_email.assert_called_once_with(
            email_content="Let's meet tomorrow at 2pm in Conference Room A to discuss the project."
        )
        
        # Verify ResponseCategorizer was called
        assert mock_response_categorizer.categorize_email.called
        
        # Verify email was marked as read (standard_response)
        mock_gmail_client.mark_as_read.assert_called_once_with("meeting_complete")
        
        # Verify EmailAgent was called to process the email
        assert mock_email_agent.process_email.called
        
        # Verify email was added to storage
        is_processed, success = await email_processor.storage.is_processed("meeting_complete")
        assert success is True
        assert is_processed is True

    @pytest.mark.asyncio
    async def test_process_single_email_meeting_incomplete(self, email_processor, mock_gmail_client,
                                                        mock_llama_analyzer, mock_deepseek_analyzer,
                                                        mock_response_categorizer, mock_email_agent):
        """
        Test processing a single incomplete meeting email through the pipeline.
        
        Verifies:
        - Missing meeting parameters are detected
        - Appropriate response requesting information is generated
        - Email is marked as read for minor incompleteness
        - Email is kept unread for major incompleteness
        """
        # Create test email with incomplete meeting details (missing location)
        test_email = {
            "message_id": "meeting_incomplete",
            "thread_id": "thread_incomplete",
            "subject": "Meeting Tomorrow at 2pm",
            "sender": "sender@example.com",
            "content": "Let's meet tomorrow at 2pm to discuss the project.",  # Missing location
            "processed_content": "Let's meet tomorrow at 2pm to discuss the project.",
            "received_at": datetime.now().isoformat(),
            "labels": ["UNREAD"]
        }
        
        # Override mock for this specific test to demonstrate incomplete meeting
        async def mock_analyze_email_incomplete(email_content):
            analysis_data = {
                "date": "tomorrow",
                "time": "2pm",
                "location": None,  # Missing location
                "agenda": "discuss the project",
                "completeness": "3/4",
                "missing_elements": "location",
                "detected tone": "Neutral"
            }
            response_text = "Thank you for your meeting request. Could you please provide the location?"
            recommendation = "standard_response"  # Still standard for one missing element
            return analysis_data, response_text, recommendation, None
            
        mock_deepseek_analyzer.analyze_email.side_effect = mock_analyze_email_incomplete
        
        # Process the email
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify success
        assert success is True
        assert error is None
        
        # Verify DeepseekAnalyzer was called correctly
        mock_deepseek_analyzer.analyze_email.assert_called_once_with(
            email_content="Let's meet tomorrow at 2pm to discuss the project."
        )
        
        # Verify email was marked as read (standard_response for minor incompleteness)
        mock_gmail_client.mark_as_read.assert_called_once_with("meeting_incomplete")
        
        # Verify EmailAgent was called to process the email
        assert mock_email_agent.process_email.called
        
        # Verify correct response template was generated (asking for location)
        call_args = mock_response_categorizer.categorize_email.call_args[1]
        assert "location" in call_args["analysis_data"]["missing_elements"]
        
        # Reset mock for other tests
        mock_deepseek_analyzer.analyze_email.reset_mock()

    @pytest.mark.asyncio
    async def test_process_single_email_needs_review(self, email_processor, mock_gmail_client,
                                                  mock_llama_analyzer, mock_deepseek_analyzer,
                                                  mock_response_categorizer, mock_email_agent):
        """
        Test processing a meeting email that needs human review.
        
        Verifies:
        - Complex meeting emails are flagged for review
        - Email is marked as unread for review
        - Response agent is not called for emails needing review
        """
        # Create test email with complex meeting details needing review
        test_email = {
            "message_id": "meeting_complex",
            "thread_id": "thread_complex",
            "subject": "Urgent Meeting Request",
            "sender": "vip@example.com",
            "content": "Need to discuss critical financial implications of the project.",
            "processed_content": "Need to discuss critical financial implications of the project.",
            "received_at": datetime.now().isoformat(),
            "labels": ["UNREAD"]
        }
        
        # Override mock for this specific test to demonstrate needs_review
        async def mock_analyze_email_complex(email_content):
            analysis_data = {
                "date": None,
                "time": None,
                "location": None,
                "agenda": "critical financial implications",
                "completeness": "1/4",
                "missing_elements": "date, time, location",
                "risk_assessment": "high - financial implications",
                "detected tone": "Formal"
            }
            response_text = "Your meeting request needs more details. I'll have someone review it."
            recommendation = "needs_review"
            return analysis_data, response_text, recommendation, None
            
        mock_deepseek_analyzer.analyze_email.side_effect = mock_analyze_email_complex
        
        # Process the email
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify success
        assert success is True
        assert error is None
        
        # Verify DeepseekAnalyzer was called correctly
        mock_deepseek_analyzer.analyze_email.assert_called_once_with(
            email_content="Need to discuss critical financial implications of the project."
        )
        
        # Verify email was marked as unread for review
        mock_gmail_client.mark_as_unread.assert_called_once_with("meeting_complex")
        
        # Verify EmailAgent was NOT called (no response for needs_review)
        mock_email_agent.process_email.assert_not_called()
        
        # Reset mock for other tests
        mock_deepseek_analyzer.analyze_email.reset_mock()
        mock_gmail_client.mark_as_unread.reset_mock()

    @pytest.mark.asyncio
    async def test_process_single_email_non_meeting(self, email_processor, mock_gmail_client,
                                                 mock_llama_analyzer, mock_deepseek_analyzer,
                                                 mock_response_categorizer, mock_email_agent):
        """
        Test processing a non-meeting email through the pipeline.
        
        Verifies:
        - Email is correctly classified as non-meeting
        - DeepseekAnalyzer is not called for non-meeting emails
        - Email is marked as read
        - Email agent is not called for non-meeting emails
        """
        # Create test non-meeting email
        test_email = {
            "message_id": "non_meeting",
            "thread_id": "thread_non_meeting",
            "subject": "Project Update",
            "sender": "updates@example.com",
            "content": "Here's the latest update on the project status. Please review the attached report.",
            "processed_content": "Here's the latest update on the project status. Please review the attached report.",
            "received_at": datetime.now().isoformat(),
            "labels": ["UNREAD"]
        }
        
        # Override the mock for non-meeting classification
        async def mock_classify_email_non_meeting(message_id, subject, content, sender):
            return False, None  # Not a meeting
            
        mock_llama_analyzer.classify_email.side_effect = mock_classify_email_non_meeting
        
        # Process the email
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify success
        assert success is True
        assert error is None
        
        # Verify LlamaAnalyzer was called correctly
        mock_llama_analyzer.classify_email.assert_called_once_with(
            message_id="non_meeting",
            subject="Project Update",
            content="Here's the latest update on the project status. Please review the attached report.",
            sender="updates@example.com"
        )
        
        # Verify DeepseekAnalyzer was NOT called for non-meeting email
        mock_deepseek_analyzer.analyze_email.assert_not_called()
        
        # Verify ResponseCategorizer was NOT called
        mock_response_categorizer.categorize_email.assert_not_called()
        
        # Email should still be marked as read
        mock_gmail_client.mark_as_read.assert_called_once_with("non_meeting")
        
        # Verify EmailAgent was NOT called
        mock_email_agent.process_email.assert_not_called()
        
        # Verify email was added to storage
        is_processed, success = await email_processor.storage.is_processed("non_meeting")
        assert success is True
        assert is_processed is True
        
        # Reset mock for other tests
        mock_llama_analyzer.classify_email.reset_mock()

    @pytest.mark.asyncio
    async def test_process_email_batch(self, email_processor, mock_gmail_client,
                                     mock_llama_analyzer, mock_deepseek_analyzer,
                                     mock_response_categorizer, mock_email_agent):
        """
        Test batch processing of emails through the pipeline.
        
        Verifies:
        - Multiple emails are processed correctly
        - Processing statistics are accurate
        - Error handling works properly for batch processing
        """
        # Mock get_unread_emails to return multiple test emails
        mock_gmail_client.get_unread_emails.return_value = [
            {
                "message_id": "batch_meeting_1",
                "thread_id": "thread_batch_1",
                "subject": "Meeting Tomorrow at 2pm",
                "sender": "sender1@example.com",
                "content": "Let's meet tomorrow at 2pm in Conference Room A to discuss the project.",
                "received_at": datetime.now().isoformat(),
                "labels": ["UNREAD"]
            },
            {
                "message_id": "batch_non_meeting_1",
                "thread_id": "thread_batch_2",
                "subject": "Project Update",
                "sender": "updates@example.com",
                "content": "Here's the latest update on the project status.",
                "received_at": datetime.now().isoformat(),
                "labels": ["UNREAD"]
            },
            {
                "message_id": "batch_meeting_2",
                "thread_id": "thread_batch_3",
                "subject": "Urgent Meeting",
                "sender": "urgent@example.com",
                "content": "We need to meet ASAP to discuss the critical issues.",
                "received_at": datetime.now().isoformat(),
                "labels": ["UNREAD"]
            }
        ]
        
        # Reset mocks to prepare for batch processing
        mock_llama_analyzer.classify_email.reset_mock()
        mock_deepseek_analyzer.analyze_email.reset_mock()
        
        # Set up mock behaviors for batch processing
        # LlamaAnalyzer will classify based on subject
        async def mock_batch_classify(message_id, subject, content, sender):
            is_meeting = "meeting" in subject.lower() or "meet" in subject.lower()
            return is_meeting, None
            
        mock_llama_analyzer.classify_email.side_effect = mock_batch_classify
        
        # Process the batch
        processed_count, error_count, errors = await email_processor.process_email_batch(batch_size=3)
        
        # Verify counts
        assert processed_count == 3  # All emails should be processed
        assert error_count == 0  # No errors expected
        assert len(errors) == 0  # No error messages
        
        # Verify LlamaAnalyzer was called 3 times (once for each email)
        assert mock_llama_analyzer.classify_email.call_count == 3
        
        # Verify DeepseekAnalyzer was called 2 times (only for meeting emails)
        assert mock_deepseek_analyzer.analyze_email.call_count == 2
        
        # Verify all emails were stored
        for message_id in ["batch_meeting_1", "batch_non_meeting_1", "batch_meeting_2"]:
            is_processed, success = await email_processor.storage.is_processed(message_id)
            assert success is True
            assert is_processed is True

    @pytest.mark.asyncio
    async def test_process_email_with_error(self, email_processor, mock_gmail_client,
                                         mock_llama_analyzer, mock_deepseek_analyzer,
                                         mock_response_categorizer, mock_email_agent):
        """
        Test error handling during email processing.
        
        Verifies:
        - Errors in pipeline components are properly handled
        - Error reporting is accurate
        - System recovers gracefully from component failures
        """
        # Create test email
        test_email = {
            "message_id": "error_test",
            "thread_id": "thread_error",
            "subject": "Meeting Tomorrow",
            "sender": "sender@example.com",
            "content": "Let's meet tomorrow to discuss the project.",
            "processed_content": "Let's meet tomorrow to discuss the project.",
            "received_at": datetime.now().isoformat(),
            "labels": ["UNREAD"]
        }
        
        # Configure LlamaAnalyzer to raise an exception
        mock_llama_analyzer.classify_email.side_effect = Exception("Simulated LlamaAnalyzer error")
        
        # Process the email
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify error handling
        assert success is False
        assert error is not None
        assert "Simulated LlamaAnalyzer error" in error
        
        # Verify email was NOT marked (neither read nor unread)
        mock_gmail_client.mark_as_read.assert_not_called()
        mock_gmail_client.mark_as_unread.assert_not_called()
        
        # Verify EmailAgent was NOT called
        mock_email_agent.process_email.assert_not_called()
        
        # Reset mock to simulate DeepseekAnalyzer error
        mock_llama_analyzer.classify_email.side_effect = None
        mock_llama_analyzer.classify_email.return_value = (True, None)  # Is a meeting
        mock_deepseek_analyzer.analyze_email.side_effect = Exception("Simulated DeepseekAnalyzer error")
        
        # Process the email again
        success, error = await email_processor._process_single_email(test_email)
        
        # Verify error handling
        assert success is False
        assert error is not None
        assert "Simulated DeepseekAnalyzer error" in error
        
        # Verify pipeline components were called in correct order until the error
        mock_llama_analyzer.classify_email.assert_called_once()
        mock_deepseek_analyzer.analyze_email.assert_called_once()
        
        # Verify downstream components were NOT called after error
        mock_response_categorizer.categorize_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_prevention(self, email_processor, mock_gmail_client,
                                      mock_llama_analyzer, mock_deepseek_analyzer):
        """
        Test duplicate prevention in email processing.
        
        Verifies:
        - Already processed emails are not processed again
        - Thread-based duplicate detection works correctly
        - Weekly history tracking functions as expected
        """
        # Create test email
        test_email = {
            "message_id": "duplicate_test",
            "thread_id": "thread_duplicate",
            "subject": "Meeting Tomorrow",
            "sender": "sender@example.com",
            "content": "Let's meet tomorrow to discuss the project.",
            "processed_content": "Let's meet tomorrow to discuss the project.",
            "received_at": datetime.now().isoformat(),
            "thread_messages": ["duplicate_test", "duplicate_related"],
            "labels": ["UNREAD"]
        }
        
        # First processing should succeed
        success, error = await email_processor._process_single_email(test_email)
        assert success is True
        assert error is None
        
        # Reset mocks to track second attempt
        mock_llama_analyzer.classify_email.reset_mock()
        mock_deepseek_analyzer.analyze_email.reset_mock()
        
        # Configure storage to simulate already processed email
        is_processed, check_success = await email_processor.storage.is_processed("duplicate_test")
        assert is_processed is True
        assert check_success is True
        
        # Add the email to mock return again
        mock_gmail_client.get_unread_emails.return_value = [test_email]
        
        # Process batch should skip the duplicate
        processed_count, error_count, errors = await email_processor.process_email_batch(batch_size=1)
        
        # Verify nothing was processed (already done)
        assert processed_count == 0
        assert error_count == 0
        
        # Verify classification was not attempted again
        mock_llama_analyzer.classify_email.assert_not_called()
        
        # Now test thread-based duplicate detection
        thread_email = {
            "message_id": "duplicate_related",  # Different ID but in same thread
            "thread_id": "thread_duplicate",
            "subject": "Re: Meeting Tomorrow",
            "sender": "responder@example.com",
            "content": "That works for me.",
            "processed_content": "That works for me.",
            "received_at": datetime.now().isoformat(),
            "labels": ["UNREAD"]
        }
        
        # This should be detected as already processed via thread membership
        is_processed, check_success = await email_processor.storage.is_processed("duplicate_related")
        assert is_processed is True  # Should be considered processed due to thread membership
        assert check_success is True

    @pytest.mark.asyncio
    async def test_end_to_end_pipeline_flow(self, email_processor, mock_gmail_client,
                                         mock_llama_analyzer, mock_deepseek_analyzer,
                                         mock_response_categorizer, mock_email_agent):
        """
        Test the complete end-to-end flow through the pipeline.
        
        Verifies:
        - All components interact correctly in sequence
        - Data is passed properly between pipeline stages
        - Final results are accurate and expected
        - Storage records match processing outcomes
        """
        # Create a batch of different types of emails
        mock_gmail_client.get_unread_emails.return_value = [
            {
                "message_id": "complete_meeting",
                "thread_id": "thread_complete",
                "subject": "Planning Meeting",
                "sender": "organizer@example.com",
                "content": "Let's meet tomorrow at 2pm in Conference Room A to discuss the project roadmap.",
                "received_at": datetime.now().isoformat(),
                "labels": ["UNREAD"]
            },
            {
                "message_id": "incomplete_meeting",
                "thread_id": "thread_incomplete",
                "subject": "Quick Meeting",
                "sender": "busy@example.com",
                "content": "Need to meet tomorrow about the project.",  # Missing time and location
                "received_at": datetime.now().isoformat(),
                "labels": ["UNREAD"]
            },
            {
                "message_id": "non_meeting_email",
                "thread_id": "thread_nonmeeting",
                "subject": "Document Review",
                "sender": "documents@example.com",
                "content": "Please review the attached document before Friday.",
                "received_at": datetime.now().isoformat(),
                "labels": ["UNREAD"]
            }
        ]
        
        # Reset all mocks for clean test
        mock_llama_analyzer.classify_email.reset_mock()
        mock_deepseek_analyzer.analyze_email.reset_mock()
        mock_response_categorizer.categorize_email.reset_mock()
        mock_email_agent.process_email.reset_mock()
        mock_gmail_client.mark_as_read.reset_mock()
        mock_gmail_client.mark_as_unread.reset_mock()
        
        # Set up responses for different email types
        async def mock_classify_email_mixed(message_id, subject, content, sender):
            # Non-meeting for "Document Review" email
            if "document" in subject.lower() or "review" in subject.lower():
                return False, None
            # Meeting for all others
            return True, None
            
        mock_llama_analyzer.classify_email.side_effect = mock_classify_email_mixed
        
        async def mock_analyze_email_mixed(email_content):
            # Complete meeting details case
            if "2pm" in email_content and "Conference Room" in email_content:
                analysis_data = {
                    "date": "tomorrow",
                    "time": "2pm",
                    "location": "Conference Room A",
                    "agenda": "discuss the project roadmap",
                    "completeness": "4/4",
                    "missing_elements": "None",
                    "detected tone": "Neutral"
                }
                response_text = (
                    "Thank you for your meeting request. I confirm our meeting tomorrow "
                    "at 2pm in Conference Room A to discuss the project roadmap."
                )
                recommendation = "standard_response"
            # Incomplete meeting details case
            else:
                analysis_data = {
                    "date": "tomorrow",
                    "time": None,
                    "location": None,
                    "agenda": "the project",
                    "completeness": "2/4",
                    "missing_elements": "time, location",
                    "detected tone": "Neutral"
                }
                response_text = "Your meeting request is missing important details. I'll have someone review it."
                recommendation = "needs_review"
            
            return analysis_data, response_text, recommendation, None
            
        mock_deepseek_analyzer.analyze_email.side_effect = mock_analyze_email_mixed
        
        # Run end-to-end batch processing
        processed_count, error_count, errors = await email_processor.process_email_batch(batch_size=3)
        
        # Verify all emails were processed
        assert processed_count == 3
        assert error_count == 0
        
        # Verify LlamaAnalyzer was called for all 3 emails
        assert mock_llama_analyzer.classify_email.call_count == 3
        
        # Verify DeepseekAnalyzer was called for the 2 meeting emails
        assert mock_deepseek_analyzer.analyze_email.call_count == 2
        
        # Verify correct categorization flow
        # - Complete meeting -> standard_response -> marked as read -> agent called
        # - Incomplete meeting -> needs_review -> marked as unread -> agent not called
        # - Non-meeting -> not analyzed -> marked as read -> agent not called
        
        # Verify appropriate Gmail status updates
        # Should have 2 mark_as_read calls (complete meeting and non-meeting)
        assert mock_gmail_client.mark_as_read.call_count == 2
        # Should have 1 mark_as_unread call (incomplete meeting needing review)
        assert mock_gmail_client.mark_as_unread.call_count == 1
        
        # Verify agent called only for complete meeting
        assert mock_email_agent.process_email.call_count == 1
        
        # Verify all emails were stored
        record_count = await email_processor.storage.get_record_count()
        assert record_count == 3
        
        # Check specific email outcomes in storage
        for message_id in ["complete_meeting", "incomplete_meeting", "non_meeting_email"]:
            is_processed, success = await email_processor.storage.is_processed(message_id)
            assert success is True
            assert is_processed is True
