"""
Test Infrastructure for Email Management System

This module provides comprehensive testing infrastructure including fixtures,
mocks, and utilities to enable consistent and reliable testing across all
system components, with proper isolation and dependency management.
"""

import os
import json
import asyncio
import logging
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Generator
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Configure test logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Path constants for test data
TEST_DATA_DIR = Path(__file__).parent / "test_data"
TEST_DATA_DIR.mkdir(exist_ok=True, parents=True)

# Ensure test data directory exists
TEST_SECURE_DIR = Path(__file__).parent / "test_data" / "secure"
TEST_SECURE_DIR.mkdir(exist_ok=True, parents=True)

# Helper to create test email data
def create_test_email(
    message_id: str = "test_message_id",
    subject: str = "Test Subject",
    content: str = "Test content",
    sender: str = "sender@example.com",
    is_meeting: bool = True
) -> Dict[str, Any]:
    """
    Create standardized test email data for consistent testing.
    
    Args:
        message_id: Unique identifier for the test email
        subject: Email subject line
        content: Email body content
        sender: Email sender address
        is_meeting: Whether this should represent a meeting email
        
    Returns:
        Complete email data dictionary suitable for testing
    """
    # Base email structure
    email_data = {
        "message_id": message_id,
        "thread_id": f"thread_{message_id}",
        "subject": subject,
        "sender": sender,
        "recipients": ["recipient@example.com"],
        "thread_messages": [message_id],
        "content": content,
        "processed_content": content,  # Simplified for testing
        "attachments": [],
        "labels": ["UNREAD"],
        "received_at": datetime.now().isoformat(),
        "processed_at": datetime.now().isoformat()
    }
    
    # Add meeting-specific content if needed
    if is_meeting:
        if "meet" not in content.lower():
            email_data["content"] = "Let's schedule a meeting tomorrow at 2pm. " + content
            email_data["processed_content"] = email_data["content"]
        
        # Add some meeting parameters to the subject if needed
        if "meet" not in subject.lower():
            email_data["subject"] = "Meeting Request: " + subject
    
    return email_data

def create_meeting_email(
    complete: bool = True, 
    message_id: str = None
) -> Dict[str, Any]:
    """
    Create a test meeting email with configurable completeness.
    
    Args:
        complete: If True, includes all meeting parameters; if False, omits some
        message_id: Optional custom message ID
        
    Returns:
        Meeting email data dictionary
    """
    mid = message_id or f"meeting_{datetime.now().timestamp()}"
    
    if complete:
        content = (
            "Hi team,\n\n"
            "Let's meet tomorrow at 2:00 PM in Conference Room A to discuss the project roadmap.\n\n"
            "Please come prepared with your status updates.\n\n"
            "Best regards,\nTest Sender"
        )
        subject = "Meeting: Project Roadmap Discussion"
    else:
        # Deliberately omit some parameters like location or time
        content = (
            "Hi team,\n\n"
            "Let's meet tomorrow to discuss the project roadmap.\n\n"
            "Please come prepared with your status updates.\n\n"
            "Best regards,\nTest Sender"
        )
        subject = "Meeting: Project Discussion"
    
    return create_test_email(
        message_id=mid,
        subject=subject,
        content=content,
        sender="meeting.organizer@example.com",
        is_meeting=True
    )

def create_non_meeting_email(message_id: str = None) -> Dict[str, Any]:
    """
    Create a test non-meeting email.
    
    Args:
        message_id: Optional custom message ID
        
    Returns:
        Non-meeting email data dictionary
    """
    mid = message_id or f"nonmeeting_{datetime.now().timestamp()}"
    
    content = (
        "Hi,\n\n"
        "I wanted to share the quarterly report with you. Please find it attached.\n\n"
        "Let me know if you have any questions.\n\n"
        "Regards,\nTest Sender"
    )
    
    return create_test_email(
        message_id=mid,
        subject="Quarterly Report",
        content=content,
        sender="reports@example.com",
        is_meeting=False
    )

def create_mixed_test_batch(size: int = 20, meeting_ratio: float = 0.7) -> List[Dict[str, Any]]:
    """
    Generate a mixed batch of test emails with specified meeting ratio.
    
    Args:
        size: Total number of emails to generate
        meeting_ratio: Ratio of meeting to non-meeting emails (0.0 to 1.0)
        
    Returns:
        List of email dictionaries with mixed types
    """
    import random
    
    emails = []
    meeting_count = int(size * meeting_ratio)
    
    # Generate meeting emails
    for i in range(meeting_count):
        # Mix of complete and incomplete meeting details
        complete = random.choice([True, True, False])  # 2:1 ratio of complete:incomplete
        emails.append(create_meeting_email(complete=complete))
    
    # Generate non-meeting emails
    for i in range(size - meeting_count):
        emails.append(create_non_meeting_email())
    
    # Shuffle to randomize order
    random.shuffle(emails)
    return emails

# Mock responses for various APIs
def create_mock_llama_response(is_meeting: bool = True) -> MagicMock:
    """
    Create a mock response for the Llama model API.
    
    Args:
        is_meeting: Whether the response should indicate a meeting
        
    Returns:
        Configured mock response object
    """
    mock_response = MagicMock()
    
    if is_meeting:
        content = "meeting"
    else:
        content = "not_meeting"
    
    # Configure the nested structure of the response
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    
    return mock_response

def create_mock_deepseek_response(
    missing_elements: Optional[str] = None,
    recommendation: str = "standard_response"
) -> str:
    """
    Create a mock response from the DeepSeek API.
    
    Args:
        missing_elements: Optional string indicating missing meeting elements
        recommendation: Response category recommendation
        
    Returns:
        Formatted mock response string
    """
    if missing_elements is None:
        missing_elements = "None"
    
    # Create a realistic-looking DeepSeek response
    response = (
        "ANALYSIS:\n"
        f"3/4 elements present. Missing elements: {missing_elements}. "
        "Risk factors: None. Detected tone: Neutral (3).\n\n"
        "RESPONSE:\n"
        "Dear Sender,\n\n"
        "Thank you for your meeting request. I am pleased to confirm our meeting tomorrow at 2 PM.\n\n"
        "Best regards,\nAI Assistant\n\n"
        f"RECOMMENDATION: {recommendation}"
    )
    
    return response

# Test fixtures
@pytest.fixture
def mock_groq_client():
    """
    Fixture providing a mocked EnhancedGroqClient for testing.
    
    Returns:
        Mock EnhancedGroqClient with configured methods
    """
    client = AsyncMock()
    client.process_with_retry = AsyncMock()
    client.process_with_retry.return_value = create_mock_llama_response(is_meeting=True)
    
    return client

@pytest.fixture
def mock_gmail_client():
    """
    Fixture providing a mocked GmailClient for testing.
    
    Returns:
        Mock GmailClient with common methods configured
    """
    client = MagicMock()
    client.get_unread_emails = MagicMock(return_value=[create_test_email()])
    client.mark_as_read = MagicMock(return_value=True)
    client.mark_as_unread = MagicMock(return_value=True)
    client.send_email = MagicMock(return_value=True)
    
    return client

@pytest.fixture
def mock_secure_storage():
    """
    Fixture providing a mocked SecureStorage instance for testing.
    
    Returns:
        Mock SecureStorage with common methods configured
    """
    storage = AsyncMock()
    
    # Configure common methods
    storage.add_record = AsyncMock(return_value=(True, True))
    storage.is_processed = AsyncMock(return_value=(False, True))
    storage.get_record_count = AsyncMock(return_value=10)
    storage._read_encrypted_data = AsyncMock(return_value={"records": []})
    storage._write_encrypted_data = AsyncMock(return_value=True)
    
    return storage

@pytest.fixture
def test_config():
    """
    Fixture providing standard test configuration for components.
    
    Returns:
        Configuration dictionary with test settings
    """
    return {
        "llama_analyzer": {
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.3,
            "max_tokens": 2000,
            "retry_count": 1,
            "retry_delay": 0.1  # Low delay for fast tests
        },
        "deepseek_analyzer": {
            "model": "deepseek-reasoner",
            "timeout": 1,  # Low timeout for fast tests
            "retry_count": 1,
            "retry_delay": 0.1
        },
        "storage": {
            "path": str(TEST_SECURE_DIR)
        }
    }

# Async test utilities
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop that can be used by all tests in the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Testing environment setup and cleanup
@pytest.fixture(autouse=True)
def setup_test_environment():
    """
    Set up and tear down the test environment for each test.
    
    Handles environment variable configuration and cleanup.
    """
    # Save original environment variables
    original_env = os.environ.copy()
    
    # Configure test environment variables
    os.environ["GROQ_API_KEY"] = "test_api_key"
    os.environ["DEEPSEEK_API_KEY"] = "test_api_key"
    os.environ["JWT_SECRET_KEY"] = "insecure_but_valid_for_testing_key_1234567890"
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
