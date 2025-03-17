"""
Comprehensive test suite for the LlamaAnalyzer component.

This test module validates the LlamaAnalyzer's functionality as the first stage 
of the email analysis pipeline, focusing on binary classification accuracy,
error handling mechanisms, and integration with the broader system.

Key test areas:
1. Binary classification accuracy for meeting vs. non-meeting content
2. Error handling during API failures with retry mechanisms
3. Logging behavior across normal and error conditions
4. Integration with EnhancedGroqClient and configuration
"""

import pytest
import json
import logging
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any, Tuple

# Import the system under test
from src.email_processing.analyzers.llama import LlamaAnalyzer
from src.integrations.groq.client_wrapper import EnhancedGroqClient

# Test fixtures and helper functions

@pytest.fixture
def mock_groq_client():
    """Create a mock GroqClient for testing API interactions."""
    mock_client = Mock(spec=EnhancedGroqClient)
    
    # Configure process_with_retry to be awaitable
    async def mock_process(*args, **kwargs):
        # Create a mock response structure that matches what the real API would return
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "meeting"
        return mock_response
        
    mock_client.process_with_retry = mock_process
    return mock_client

@pytest.fixture
def analyzer_with_mock_client(mock_groq_client):
    """Create a LlamaAnalyzer instance with mock client."""
    analyzer = LlamaAnalyzer()
    analyzer.client = mock_groq_client
    return analyzer

def create_mock_response(content: str):
    """Create a mock Groq API response with specified content."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_response.model = "llama-3.3-70b-versatile"
    mock_response.created = int(datetime.now().timestamp())
    return mock_response

# Unit Tests for LlamaAnalyzer

@pytest.mark.asyncio
async def test_llama_analyzer_initialization():
    """Test that LlamaAnalyzer initializes correctly with proper configuration."""
    # Initialize the analyzer
    analyzer = LlamaAnalyzer()
    
    # Verify the analyzer has been configured with correct components
    assert analyzer.client is not None
    assert analyzer.model_config is not None
    assert analyzer.model_config.get('name') is not None
    assert isinstance(analyzer.model_config, dict)

@pytest.mark.asyncio
async def test_classify_email_meeting_content(analyzer_with_mock_client):
    """Test classification of content containing meeting information."""
    # Configure mock to return "meeting"
    async def mock_process(*args, **kwargs):
        return create_mock_response("meeting")
        
    analyzer_with_mock_client.client.process_with_retry = mock_process
    
    # Call classification method with meeting-related content
    is_meeting, error = await analyzer_with_mock_client.classify_email(
        message_id="test123",
        subject="Meeting tomorrow at 2pm",
        content="Let's meet tomorrow at 2pm to discuss the project",
        sender="test@example.com"
    )
    
    # Verify classification results
    assert is_meeting is True
    assert error is None

@pytest.mark.asyncio
async def test_classify_email_non_meeting_content(analyzer_with_mock_client):
    """Test classification of content not containing meeting information."""
    # Configure mock to return "not_meeting"
    async def mock_process(*args, **kwargs):
        return create_mock_response("not_meeting")
        
    analyzer_with_mock_client.client.process_with_retry = mock_process
    
    # Call classification method with non-meeting content
    is_meeting, error = await analyzer_with_mock_client.classify_email(
        message_id="test456",
        subject="Project update",
        content="Here's the latest status update on our project.",
        sender="test@example.com"
    )
    
    # Verify classification results
    assert is_meeting is False
    assert error is None

@pytest.mark.asyncio
async def test_classify_email_handles_api_error(analyzer_with_mock_client):
    """Test error handling when API call fails."""
    # Configure mock to raise an exception
    async def mock_process_error(*args, **kwargs):
        raise RuntimeError("API connection failed")
        
    analyzer_with_mock_client.client.process_with_retry = mock_process_error
    
    # Call classification method
    is_meeting, error = await analyzer_with_mock_client.classify_email(
        message_id="test789",
        subject="Test Subject",
        content="Test Content",
        sender="test@example.com"
    )
    
    # Verify error handling results
    assert is_meeting is False  # Default to false on error
    assert error is not None
    assert "API connection failed" in error

@pytest.mark.asyncio
async def test_classify_email_constructs_correct_prompt(analyzer_with_mock_client):
    """Test that the analyzer constructs the correct classification prompt."""
    # Use a more sophisticated mock to capture the prompt
    prompt_content = None
    
    async def mock_process_capture_prompt(*args, **kwargs):
        nonlocal prompt_content
        messages = kwargs.get('messages', [])
        # Extract the prompt from the messages
        for msg in messages:
            if msg.get('role') == 'user':
                prompt_content = msg.get('content')
        return create_mock_response("meeting")
        
    analyzer_with_mock_client.client.process_with_retry = mock_process_capture_prompt
    
    # Test data
    subject = "Meeting Request"
    content = "Can we meet tomorrow at 3pm?"
    
    # Call classification method
    await analyzer_with_mock_client.classify_email(
        message_id="test101",
        subject=subject,
        content=content,
        sender="test@example.com"
    )
    
    # Verify prompt construction
    assert prompt_content is not None
    assert subject in prompt_content
    assert content in prompt_content
    assert "meeting" in prompt_content.lower()
    assert "not_meeting" in prompt_content.lower()

@pytest.mark.asyncio
async def test_classify_email_api_parameter_configuration(analyzer_with_mock_client):
    """Test that the analyzer configures API parameters correctly."""
    # Use a mock to capture API parameters
    api_params = None
    
    async def mock_process_capture_params(*args, **kwargs):
        nonlocal api_params
        api_params = kwargs
        return create_mock_response("meeting")
        
    analyzer_with_mock_client.client.process_with_retry = mock_process_capture_params
    
    # Call classification method
    await analyzer_with_mock_client.classify_email(
        message_id="test202",
        subject="Subject",
        content="Content",
        sender="test@example.com"
    )
    
    # Verify API parameters
    assert api_params is not None
    assert "model" in api_params
    assert "temperature" in api_params
    assert "messages" in api_params
    # Verify classification uses low temperature for consistent results
    assert api_params["temperature"] <= 0.3
    # Verify we're requesting minimal tokens for binary classification
    assert api_params.get("max_completion_tokens", 100) <= 20

@pytest.mark.asyncio
async def test_classify_email_logging(analyzer_with_mock_client, caplog):
    """Test that the analyzer logs classification decisions properly."""
    # Configure logging capture
    caplog.set_level(logging.DEBUG)
    
    # Configure mock response
    async def mock_process(*args, **kwargs):
        return create_mock_response("meeting")
        
    analyzer_with_mock_client.client.process_with_retry = mock_process
    
    # Call classification method
    await analyzer_with_mock_client.classify_email(
        message_id="test303",
        subject="Logging Test",
        content="Test Content",
        sender="test@example.com"
    )
    
    # Verify logging
    assert any("Starting initial classification" in record.message for record in caplog.records)
    assert any("Classification decision" in record.message for record in caplog.records)
    assert any("Completed classification" in record.message for record in caplog.records)

@pytest.mark.asyncio
async def test_classify_email_mask_email_functionality(analyzer_with_mock_client):
    """Test that the analyzer properly masks email addresses in logs."""
    # Direct test of the _mask_email method
    email = "test.user@example.com"
    masked = analyzer_with_mock_client._mask_email(email)
    
    # Verify masking
    assert masked != email
    assert "@" in masked
    assert "example.com" in masked
    assert "test.user" not in masked
    # First and last characters should be preserved
    assert masked.startswith("t")
    assert "r@" in masked

@pytest.mark.asyncio
async def test_classify_email_with_empty_content(analyzer_with_mock_client):
    """Test classification behavior with empty content."""
    # Call classification method with empty content
    is_meeting, error = await analyzer_with_mock_client.classify_email(
        message_id="test404",
        subject="Empty Test",
        content="",
        sender="test@example.com"
    )
    
    # Verify classification still works with empty content
    assert is_meeting is not None
    assert error is None

@pytest.mark.asyncio
async def test_classify_email_with_long_content(analyzer_with_mock_client):
    """Test classification with very long content."""
    # Generate long content
    long_content = "This is a test. " * 1000  # 16K characters
    
    # Call classification method with long content
    is_meeting, error = await analyzer_with_mock_client.classify_email(
        message_id="test505",
        subject="Long Content Test",
        content=long_content,
        sender="test@example.com"
    )
    
    # Verify classification works with long content
    assert is_meeting is not None
    assert error is None

# Integration Tests

@pytest.mark.asyncio
@patch('src.integrations.groq.client_wrapper.EnhancedGroqClient')
async def test_analyzer_retry_mechanism(mock_groq_client_class):
    """Test that the analyzer properly handles API failures and retries."""
    # Configure the mock to fail on first attempt, succeed on second
    mock_client_instance = Mock()
    retry_count = 0
    
    async def mock_process_with_retry(*args, **kwargs):
        nonlocal retry_count
        retry_count += 1
        if retry_count == 1:
            raise RuntimeError("First attempt failed")
        return create_mock_response("meeting")
        
    mock_client_instance.process_with_retry = mock_process_with_retry
    mock_groq_client_class.return_value = mock_client_instance
    
    # Create analyzer with the patched client class
    analyzer = LlamaAnalyzer()
    
    # Call classification method
    is_meeting, error = await analyzer.classify_email(
        message_id="test606",
        subject="Retry Test",
        content="Test Content",
        sender="test@example.com"
    )
    
    # Verify retry behavior
    assert retry_count == 2  # Should have attempted twice
    assert is_meeting is False  # Should default to False on error
    assert error is not None
    assert "First attempt failed" in error

@pytest.mark.asyncio
@patch('src.config.analyzer_config.ANALYZER_CONFIG')
async def test_analyzer_with_custom_config(mock_config):
    """Test that the analyzer loads and uses custom configuration."""
    # Configure mock configuration
    mock_config.get.return_value = {
        "model": {
            "name": "custom-model-name",
            "temperature": 0.1,
            "max_tokens": 1000
        }
    }
    
    # Create analyzer with the mocked configuration
    analyzer = LlamaAnalyzer()
    
    # Verify configuration was properly loaded
    assert analyzer.model_config.get("name") == "custom-model-name"
    assert analyzer.model_config.get("temperature") == 0.1
    assert analyzer.model_config.get("max_tokens") == 1000

# Performance Tests

@pytest.mark.asyncio
@pytest.mark.performance
async def test_analyzer_performance(analyzer_with_mock_client):
    """Test the analyzer's performance with multiple classifications."""
    # Configure fast mock response
    async def mock_process(*args, **kwargs):
        await asyncio.sleep(0.01)  # Simulate 10ms processing time
        return create_mock_response("meeting")
        
    analyzer_with_mock_client.client.process_with_retry = mock_process
    
    # Prepare test data
    test_count = 10
    test_data = [
        {
            "message_id": f"perf{i}",
            "subject": f"Test Subject {i}",
            "content": f"Test Content {i}",
            "sender": f"test{i}@example.com"
        }
        for i in range(test_count)
    ]
    
    # Measure classification time
    start_time = datetime.now()
    
    # Process all test emails
    results = await asyncio.gather(*[
        analyzer_with_mock_client.classify_email(
            message_id=data["message_id"],
            subject=data["subject"],
            content=data["content"],
            sender=data["sender"]
        )
        for data in test_data
    ])
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Verify performance
    assert len(results) == test_count
    # Calculate average time per classification
    avg_time = duration / test_count
    # Log performance metrics
    print(f"Average classification time: {avg_time:.4f} seconds")
    assert avg_time < 0.1  # Should be very fast with mocks
