"""
Unit tests for core email processing components.

These tests focus on individual component functionality rather than
integration between components. Each component is tested in isolation
with all dependencies mocked to ensure proper unit-level verification.

Design Considerations:
- Each component is tested in isolation with mocked dependencies
- Tests focus on specific functionality and edge cases
- Comprehensive testing of error handling and recovery
- Verification of component-specific business logic
"""


import sys
import os
import pytest
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple
from unittest.mock import Mock, patch, MagicMock, AsyncMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Import the components to test
from src.email_processing.analyzers.llama import LlamaAnalyzer
from src.email_processing.analyzers.deepseek import DeepseekAnalyzer
from src.email_processing.analyzers.response_categorizer import ResponseCategorizer
from src.email_processing.handlers.writer import EmailAgent
from src.storage.secure import SecureStorage
from src.email_processing.models import EmailMetadata, EmailTopic

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestLlamaAnalyzer:
    """
    Unit tests for the LlamaAnalyzer component.
    
    Tests the initial classification stage of the pipeline which determines
    if an email is meeting-related using the Llama-3.3-70b-versatile model.
    
    Focuses on proper API integration, error handling, and classification accuracy.
    """
    
    @pytest.fixture
    def mock_groq_client(self):
        """Create a mock Groq client with predictable behavior."""
        mock_client = AsyncMock()
        
        # Create a mock response object structure
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        
        # Configure process_with_retry to return different results based on content
        async def mock_process_with_retry(messages, **kwargs):
            # Extract the email content from the messages
            content = next((m for m in messages if m["role"] == "user"), {"content": ""})["content"]
            
            if "meeting" in content.lower() or "meet" in content.lower():
                mock_response.choices[0].message.content = "meeting"
            else:
                mock_response.choices[0].message.content = "not_meeting"
            
            return mock_response
            
        mock_client.process_with_retry = mock_process_with_retry
        return mock_client
    
    @pytest.mark.asyncio
    async def test_meeting_classification_positive(self, mock_groq_client):
        """
        Test classification of a meeting-related email.
        
        Verifies that emails containing meeting-related content are
        correctly classified as meeting-related.
        
        Args:
            mock_groq_client: Configured mock Groq client
        """
        # Setup LlamaAnalyzer with mock client
        analyzer = LlamaAnalyzer()
        analyzer.client = mock_groq_client
        
        # Test email with clear meeting content
        result, error = await analyzer.classify_email(
            message_id="test123",
            subject="Team Meeting",
            content="Let's meet tomorrow at 2pm to discuss the project.",
            sender="colleague@example.com"
        )
        
        # Verify classification
        assert result is True
        assert error is None
    
    @pytest.mark.asyncio
    async def test_meeting_classification_negative(self, mock_groq_client):
        """
        Test classification of a non-meeting email.
        
        Verifies that emails without meeting-related content are
        correctly classified as not meeting-related.
        
        Args:
            mock_groq_client: Configured mock Groq client
        """
        # Setup LlamaAnalyzer with mock client
        analyzer = LlamaAnalyzer()
        analyzer.client = mock_groq_client
        
        # Test email with no meeting content
        result, error = await analyzer.classify_email(
            message_id="test456",
            subject="Project Update",
            content="Here's the latest update on the project progress.",
            sender="colleague@example.com"
        )
        
        # Verify classification
        assert result is False
        assert error is None
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """
        Test handling of API errors during classification.
        
        Verifies that errors from the Groq API are properly caught and
        returned as error messages without crashing the component.
        """
        # Setup LlamaAnalyzer with a mock client that raises exceptions
        analyzer = LlamaAnalyzer()
        mock_error_client = AsyncMock()
        mock_error_client.process_with_retry = AsyncMock(side_effect=Exception("API connection error"))
        analyzer.client = mock_error_client
        
        # Test classification with failing API
        result, error = await analyzer.classify_email(
            message_id="test789",
            subject="Error Test",
            content="This should trigger an API error.",
            sender="colleague@example.com"
        )
        
        # Verify error handling
        assert result is False
        assert error is not None
        assert "API connection error" in error
    
    @pytest.mark.asyncio
    async def test_empty_content_handling(self, mock_groq_client):
        """
        Test handling of emails with empty content.
        
        Verifies that emails with empty or very minimal content are
        handled properly without causing errors.
        
        Args:
            mock_groq_client: Configured mock Groq client
        """
        # Setup LlamaAnalyzer with mock client
        analyzer = LlamaAnalyzer()
        analyzer.client = mock_groq_client
        
        # Test email with empty content
        result, error = await analyzer.classify_email(
            message_id="empty_content",
            subject="Empty Email",
            content="",
            sender="colleague@example.com"
        )
        
        # Empty content should default to not being a meeting
        assert result is False
        assert error is None


class TestDeepseekAnalyzer:
    """
    Unit tests for the DeepseekAnalyzer component.
    
    Tests the detailed content analysis stage of the pipeline which extracts
    meeting parameters and generates appropriate responses using the DeepSeek model.
    
    Focuses on parameter extraction, completeness checking, and response generation.
    """
    
    @pytest.fixture
    def mock_requests(self):
        """Create a mock requests object for API responses."""
        mock_req = MagicMock()
        
        # Create mock response object
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Configure json method to return different results based on content
        def mock_json():
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
ANALYSIS: 
Completeness: 4/4 elements
Missing elements: None
Risk factors: None
Detected tone: Casual (2)

RESPONSE:
Thank you for your meeting request. I'm pleased to confirm our meeting tomorrow at 2pm in Conference Room A to discuss the project.

RECOMMENDATION: standard_response
"""
                        }
                    }
                ]
            }
        
        mock_response.json = mock_json
        mock_req.post.return_value = mock_response
        
        return mock_req
    
    @pytest.mark.asyncio
    async def test_complete_meeting_analysis(self, mock_requests):
        """
        Test analysis of a complete meeting email.
        
        Verifies that emails with all required meeting parameters are correctly
        analyzed with proper parameter extraction and response generation.
        
        Args:
            mock_requests: Configured mock requests object
        """
        # Patch requests module to use our mock
        with patch('requests.post', mock_requests.post):
            # Initialize analyzer
            analyzer = DeepseekAnalyzer()
            
            # Test with complete meeting content
            analysis_data, response_text, recommendation, error = await analyzer.analyze_email(
                email_content="Let's meet tomorrow at 2pm in Conference Room A to discuss the project."
            )
            
            # Verify analysis results
            assert error is None
            assert recommendation == "standard_response"
            assert "confirm our meeting" in response_text
            assert analysis_data is not None
            # The mock is configured to return a complete meeting with no missing elements
            assert "missing elements" not in analysis_data or not analysis_data["missing elements"]
    
    @pytest.mark.asyncio
    async def test_incomplete_meeting_analysis(self, mock_requests):
        """
        Test analysis of an incomplete meeting email.
        
        Verifies that emails missing some required meeting parameters are correctly
        analyzed with proper identification of missing elements and appropriate
        response generation requesting the missing information.
        
        Args:
            mock_requests: Configured mock requests object
        """
        # Configure mock to return incomplete meeting analysis
        def mock_json_incomplete():
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
ANALYSIS: 
Completeness: 3/4 elements
Missing elements: time
Risk factors: None
Detected tone: Casual (2)

RESPONSE:
Thank you for your meeting request. Could you please specify the meeting time?

RECOMMENDATION: standard_response
"""
                        }
                    }
                ]
            }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = mock_json_incomplete
        mock_requests.post.return_value = mock_response
        
        # Patch requests module to use our mock
        with patch('requests.post', mock_requests.post):
            # Initialize analyzer
            analyzer = DeepseekAnalyzer()
            
            # Test with incomplete meeting content
            analysis_data, response_text, recommendation, error = await analyzer.analyze_email(
                email_content="Let's meet tomorrow in Conference Room A to discuss the project."
            )
            
            # Verify analysis results
            assert error is None
            assert recommendation == "standard_response"
            assert "specify the meeting time" in response_text
            assert analysis_data is not None
            assert "missing elements" in analysis_data
            assert "time" in analysis_data["missing elements"]
    
    @pytest.mark.asyncio
    async def test_high_risk_meeting_analysis(self, mock_requests):
        """
        Test analysis of a high-risk meeting email.
        
        Verifies that emails with high-risk content (financial, legal, etc.)
        are correctly identified as needing review with appropriate flagging.
        
        Args:
            mock_requests: Configured mock requests object
        """
        # Configure mock to return high-risk meeting analysis
        def mock_json_high_risk():
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
ANALYSIS: 
Completeness: 4/4 elements
Missing elements: None
Risk factors: Financial implications, executive involvement
Detected tone: Formal (4)

RESPONSE:
Thank you for your meeting request regarding the budget approval. Your request requires additional review, and we will respond within 24 hours.

RECOMMENDATION: needs_review
"""
                        }
                    }
                ]
            }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = mock_json_high_risk
        mock_requests.post.return_value = mock_response
        
        # Patch requests module to use our mock
        with patch('requests.post', mock_requests.post):
            # Initialize analyzer
            analyzer = DeepseekAnalyzer()
            
            # Test with high-risk meeting content
            analysis_data, response_text, recommendation, error = await analyzer.analyze_email(
                email_content="Let's schedule a meeting tomorrow at 2pm in the boardroom to approve the $1.5M budget with the executive team."
            )
            
            # Verify analysis results
            assert error is None
            assert recommendation == "needs_review"
            assert "requires additional review" in response_text
            assert analysis_data is not None
            assert "risk factors" in analysis_data
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """
        Test handling of API errors during analysis.
        
        Verifies that errors from the DeepSeek API are properly caught and
        returned as error messages without crashing the component.
        """
        # Create a mock that raises an exception
        mock_error = MagicMock()
        mock_error.side_effect = Exception("API timeout error")
        
        # Patch requests module to use our error-raising mock
        with patch('requests.post', mock_error):
            # Initialize analyzer
            analyzer = DeepseekAnalyzer()
            
            # Test analysis with failing API
            analysis_data, response_text, recommendation, error = await analyzer.analyze_email(
                email_content="This should trigger an API error."
            )
            
            # Verify error handling
            assert error is not None
            assert "API timeout error" in error
            assert recommendation == "needs_review"  # Default to needs_review on error
            assert not analysis_data  # Should be empty on error


class TestResponseCategorizer:
    """
    Unit tests for the ResponseCategorizer component.
    
    Tests the response categorization stage of the pipeline which determines
    the final handling category and prepares response templates.
    
    Focuses on categorization logic, response formatting, and parameter handling.
    """
    
    @pytest.fixture
    def setup_categorizer(self):
        """Set up a ResponseCategorizer with necessary mocks."""
        categorizer = ResponseCategorizer()
        # Mock any needed clients or services
        return categorizer
    
    @pytest.mark.asyncio
    async def test_standard_response_categorization(self, setup_categorizer):
        """
        Test categorization of a standard response.
        
        Verifies that emails with complete meeting information are correctly
        categorized as standard_response with appropriate response templates.
        
        Args:
            setup_categorizer: Configured ResponseCategorizer
        """
        categorizer = setup_categorizer
        
        # Test data for a complete meeting
        analysis_data = {
            "date": "tomorrow",
            "time": "2pm",
            "location": "Conference Room A",
            "agenda": "project discussion",
            "missing_elements": "",
            "tone": "friendly"
        }
        response_text = "Thank you for your meeting request. I confirm our meeting tomorrow at 2pm in Conference Room A."
        deepseek_recommendation = "standard_response"
        
        # Get categorization result
        category, response_template = await categorizer.categorize_email(
            analysis_data=analysis_data,
            response_text=response_text,
            deepseek_recommendation=deepseek_recommendation
        )
        
        # Verify categorization
        assert category == "standard_response"
        assert response_template is not None
        assert "confirm our meeting" in response_template
    
    @pytest.mark.asyncio
    async def test_needs_review_categorization(self, setup_categorizer):
        """
        Test categorization of an email needing review.
        
        Verifies that emails flagged for review by DeepseekAnalyzer are correctly
        categorized as needs_review with proper handling.
        
        Args:
            setup_categorizer: Configured ResponseCategorizer
        """
        categorizer = setup_categorizer
        
        # Test data for a high-risk meeting
        analysis_data = {
            "date": "tomorrow",
            "time": "2pm",
            "location": "Conference Room A",
            "agenda": "budget approval",
            "risk factors": "Financial implications, executive involvement",
            "missing_elements": "",
            "tone": "formal"
        }
        response_text = "Thank you for your meeting request. Your request requires additional review."
        deepseek_recommendation = "needs_review"
        
        # Get categorization result
        category, response_template = await categorizer.categorize_email(
            analysis_data=analysis_data,
            response_text=response_text,
            deepseek_recommendation=deepseek_recommendation
        )
        
        # Verify categorization
        assert category == "needs_review"
        assert response_template is None  # No template for needs_review
    
    @pytest.mark.asyncio
    async def test_parameter_request_generation(self, setup_categorizer):
        """
        Test generation of parameter request responses.
        
        Verifies that when meeting parameters are missing, the categorizer
        correctly generates responses requesting the specific missing information.
        
        Args:
            setup_categorizer: Configured ResponseCategorizer
        """
        categorizer = setup_categorizer
        
        # Test data for an incomplete meeting (missing time)
        analysis_data = {
            "date": "tomorrow",
            "time": None,
            "location": "Conference Room A",
            "agenda": "project discussion",
            "missing_elements": "time",
            "tone": "friendly"
        }
        response_text = "Thank you for your meeting request. Could you please specify the meeting time?"
        deepseek_recommendation = "standard_response"
        
        # Get categorization result
        category, response_template = await categorizer.categorize_email(
            analysis_data=analysis_data,
            response_text=response_text,
            deepseek_recommendation=deepseek_recommendation
        )
        
        # Verify categorization
        assert category == "standard_response"
        assert response_template is not None
        assert "specify the meeting time" in response_template
    
    @pytest.mark.asyncio
    async def test_legacy_categorization_support(self, setup_categorizer):
        """
        Test backward compatibility with legacy categorization.
        
        Verifies that the categorizer can handle legacy format input from
        older versions of DeepseekAnalyzer to maintain backward compatibility.
        
        Args:
            setup_categorizer: Configured ResponseCategorizer
        """
        categorizer = setup_categorizer
        
        # Test with legacy method and minimal data
        category, response_template = await categorizer.categorize_email_legacy(
            deepseek_summary="This email contains a complete meeting request for tomorrow at 2pm in Room A.",
            deepseek_recommendation="standard_response"
        )
        
        # Verify categorization works with legacy method
        assert category == "standard_response"
        # Template might be generic due to limited information
        assert response_template is not None


class TestEmailAgent:
    """
    Unit tests for the EmailAgent component.
    
    Tests the response delivery stage of the pipeline which handles
    sending responses and updating email status in Gmail.
    
    Focuses on response sending, Gmail integration, and error handling.
    """
    
    @pytest.fixture
    def setup_agent(self):
        """Set up an EmailAgent with necessary mocks."""
        agent = EmailAgent()
        
        # Mock Gmail client
        mock_gmail = AsyncMock()
        mock_gmail.send_email.return_value = True
        agent.gmail = mock_gmail
        
        # Mock OpenAI client if needed
        if hasattr(agent, 'client'):
            mock_openai = AsyncMock()
            agent.client = mock_openai
        
        # Mock GroqClient if used
        if hasattr(agent, 'groq_client'):
            mock_groq = AsyncMock()
            agent.groq_client = mock_groq
        
        return agent
    
    @pytest.mark.asyncio
    async def test_response_sending(self, setup_agent):
        """
        Test sending a response to an email.
        
        Verifies that responses are correctly sent through the Gmail API
        with proper formatting and error handling.
        
        Args:
            setup_agent: Configured EmailAgent
        """
        agent = setup_agent
        
        # Create test metadata with a response template
        metadata = EmailMetadata(
            message_id="test123",
            subject="Meeting Request",
            sender="colleague@example.com",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Let's meet tomorrow at 2pm.",
            analysis_data={
                'response_template': "Thank you for your meeting request. I confirm our meeting tomorrow at 2pm."
            }
        )
        
        # Process the email
        success = await agent.process_email(metadata)
        
        # Verify success
        assert success is True
        
        # Verify Gmail send_email was called with correct parameters
        agent.gmail.send_email.assert_called_once()
        call_args = agent.gmail.send_email.call_args[0]
        assert call_args[0] == metadata.sender  # To email
        assert "Meeting Request" in call_args[1]  # Subject
        assert "confirm our meeting" in call_args[2]  # Message text
    
    @pytest.mark.asyncio
    async def test_duplicate_response_prevention(self, setup_agent):
        """
        Test prevention of duplicate responses.
        
        Verifies that the agent correctly prevents sending duplicate
        responses to the same email.
        
        Args:
            setup_agent: Configured EmailAgent
        """
        agent = setup_agent
        
        # Mock has_responded to return True (already responded)
        original_has_responded = agent.has_responded
        agent.has_responded = lambda email_id: True
        
        # Create test metadata
        metadata = EmailMetadata(
            message_id="duplicate_test",
            subject="Meeting Request",
            sender="colleague@example.com",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Let's meet tomorrow at 2pm.",
            analysis_data={
                'response_template': "Thank you for your meeting request. I confirm our meeting tomorrow at 2pm."
            }
        )
        
        # Process the email
        success = await agent.process_email(metadata)
        
        # Verify success (should still return True even though no action taken)
        assert success is True
        
        # Verify Gmail send_email was NOT called
        agent.gmail.send_email.assert_not_called()
        
        # Restore original method
        agent.has_responded = original_has_responded
    
    @pytest.mark.asyncio
    async def test_parameter_verification(self, setup_agent):
        """
        Test verification of meeting parameters.
        
        Verifies that the agent correctly identifies and requests missing
        meeting parameters when needed.
        
        Args:
            setup_agent: Configured EmailAgent
        """
        agent = setup_agent
        
        # Mock verify_meeting_parameters_ai to return specific results
        async def mock_verify_parameters(content, subject):
            return {
                "parameters": {
                    "date": {"found": True, "value": "tomorrow", "confidence": 0.9},
                    "time": {"found": False, "value": None, "confidence": 0.0},
                    "location": {"found": True, "value": "Conference Room A", "confidence": 0.8},
                    "agenda": {"found": True, "value": "project discussion", "confidence": 0.7}
                },
                "missing_parameters": ["time"],
                "has_all_required": False,
                "overall_confidence": 0.6
            }, True
        
        # Save original method and patch with our mock
        original_verify = agent.verify_meeting_parameters_ai
        agent.verify_meeting_parameters_ai = mock_verify_parameters
        
        # Create test metadata without a response template (to force parameter verification)
        metadata = EmailMetadata(
            message_id="param_test",
            subject="Meeting Request",
            sender="colleague@example.com",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Let's meet tomorrow in Conference Room A to discuss the project.",
            analysis_data={}  # No response template
        )
        
        # Process the email
        success = await agent.process_email(metadata)
        
        # Verify success
        assert success is True
        
        # Verify Gmail send_email was called with a response requesting the time
        agent.gmail.send_email.assert_called_once()
        call_args = agent.gmail.send_email.call_args[0]
        assert "specify the meeting time" in call_args[2]  # Message text should request time
        
        # Restore original method
        agent.verify_meeting_parameters_ai = original_verify
    
    @pytest.mark.asyncio
    async def test_gmail_error_handling(self, setup_agent):
        """
        Test handling of Gmail API errors.
        
        Verifies that the agent correctly handles errors from the Gmail API
        during response sending without crashing.
        
        Args:
            setup_agent: Configured EmailAgent
        """
        agent = setup_agent
        
        # Configure Gmail to raise an error
        agent.gmail.send_email.side_effect = Exception("Gmail API error")
        
        # Create test metadata
        metadata = EmailMetadata(
            message_id="error_test",
            subject="Meeting Request",
            sender="colleague@example.com",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Let's meet tomorrow at 2pm.",
            analysis_data={
                'response_template': "Thank you for your meeting request. I confirm our meeting tomorrow at 2pm."
            }
        )
        
        # Process the email
        success = await agent.process_email(metadata)
        
        # Verify failure
        assert success is False
