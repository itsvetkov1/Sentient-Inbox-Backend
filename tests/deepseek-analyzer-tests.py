"""
DeepseekAnalyzer Unit Tests

This module provides comprehensive test coverage for the DeepseekAnalyzer component,
which performs detailed content analysis and response generation in the second
stage of the email processing pipeline, following the specifications in analysis-pipeline.md.
"""

import pytest
import json
import re
from unittest.mock import AsyncMock, patch, MagicMock, call
import requests
from typing import Dict, Any, Optional, Tuple

# Import test infrastructure
from tests.test_infrastructure import (
    create_test_email, create_mock_deepseek_response, 
    test_config, setup_test_environment
)

# Import component under test
from src.email_processing.analyzers.deepseek import DeepseekAnalyzer


class TestDeepseekAnalyzer:
    """Test suite for the DeepseekAnalyzer component."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test proper initialization of DeepseekAnalyzer with configuration."""
        # Test default initialization
        analyzer = DeepseekAnalyzer()
        assert analyzer.model_name == "deepseek-reasoner"
        assert analyzer.api_endpoint is not None
        assert analyzer.api_key is not None
        assert analyzer.timeout > 0
        assert analyzer.retry_count >= 0
        assert analyzer.retry_delay > 0

    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_analyze_email_complete_meeting(self, mock_post):
        """Test successful analysis of a complete meeting email."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": create_mock_deepseek_response(
                            missing_elements="None",
                            recommendation="standard_response"
                        )
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # Create analyzer and test email
        analyzer = DeepseekAnalyzer()
        email_content = (
            "Hi team,\n\n"
            "Let's meet tomorrow at 2:00 PM in Conference Room A to discuss the project roadmap.\n\n"
            "Please come prepared with your status updates.\n\n"
            "Best regards,\nTest Sender"
        )
        
        # Execute
        analysis_data, response_text, recommendation, error = await analyzer.analyze_email(email_content)
        
        # Assert
        assert error is None
        assert recommendation == "standard_response"
        assert response_text is not None and len(response_text) > 0
        assert analysis_data is not None
        assert isinstance(analysis_data, dict)
        
        # Verify API call
        mock_post.assert_called_once()
        
        # Verify prompt contains email content
        args, kwargs = mock_post.call_args
        assert 'json' in kwargs
        assert email_content in json.dumps(kwargs['json'])

    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_analyze_email_incomplete_meeting(self, mock_post):
        """Test analysis of a meeting email with missing elements."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": create_mock_deepseek_response(
                            missing_elements="location, time",
                            recommendation="standard_response"
                        )
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # Create analyzer and test email
        analyzer = DeepseekAnalyzer()
        email_content = (
            "Hi team,\n\n"
            "Let's meet tomorrow to discuss the project roadmap.\n\n"
            "Please come prepared with your status updates.\n\n"
            "Best regards,\nTest Sender"
        )
        
        # Execute
        analysis_data, response_text, recommendation, error = await analyzer.analyze_email(email_content)
        
        # Assert
        assert error is None
        assert recommendation == "standard_response"
        assert response_text is not None and len(response_text) > 0
        assert analysis_data is not None
        assert "missing elements" in analysis_data or "missing_elements" in analysis_data
        
        # Check that missing elements were detected
        missing_elements_key = "missing elements" if "missing elements" in analysis_data else "missing_elements"
        assert "location" in analysis_data[missing_elements_key].lower()
        assert "time" in analysis_data[missing_elements_key].lower()

    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_analyze_email_high_risk(self, mock_post):
        """Test analysis of a high-risk meeting email requiring review."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": create_mock_deepseek_response(
                            missing_elements="None",
                            recommendation="needs_review"
                        )
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # Create analyzer and test email
        analyzer = DeepseekAnalyzer()
        email_content = (
            "Hi team,\n\n"
            "Let's meet tomorrow at 2:00 PM in Conference Room A to discuss the financial audit.\n\n"
            "We need to review the contract terms and legal implications before proceeding.\n\n"
            "Best regards,\nTest Sender"
        )
        
        # Execute
        analysis_data, response_text, recommendation, error = await analyzer.analyze_email(email_content)
        
        # Assert
        assert error is None
        assert recommendation == "needs_review"
        assert response_text is not None
        assert analysis_data is not None

    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_analyze_email_empty_content(self, mock_post):
        """Test handling of empty or minimal content."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": create_mock_deepseek_response(
                            recommendation="ignore"
                        )
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # Create analyzer
        analyzer = DeepseekAnalyzer()
        
        # Test with empty content
        analysis_data, response_text, recommendation, error = await analyzer.analyze_email("")
        
        # Assert
        assert error is None  # Should handle empty content gracefully
        assert recommendation == "ignore"
        
        # Test with "No content available"
        analysis_data, response_text, recommendation, error = await analyzer.analyze_email("No content available")
        
        # Assert
        assert error is None  # Should handle this case gracefully
        assert recommendation == "ignore"

    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_api_error_handling(self, mock_post):
        """Test error handling when API calls fail."""
        # Setup mock to raise exception
        mock_post.side_effect = requests.exceptions.RequestException("API connection failed")
        
        # Create analyzer
        analyzer = DeepseekAnalyzer()
        email_content = "Test content for error handling"
        
        # Execute
        analysis_data, response_text, recommendation, error = await analyzer.analyze_email(email_content)
        
        # Assert
        assert error is not None
        assert "API connection failed" in error
        assert recommendation == "needs_review"  # Default to review on error
        assert not analysis_data  # Should be empty dict
        assert response_text == ""  # Should be empty string

    @pytest.mark.asyncio
    @patch('requests.post')
    @patch('asyncio.sleep')
    async def test_retry_mechanism(self, mock_sleep, mock_post):
        """Test retry mechanism for transient API failures."""
        # Setup mock to fail once then succeed
        mock_error_response = MagicMock()
        mock_error_response.status_code = 500
        mock_error_response.text = "Internal Server Error"
        
        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": create_mock_deepseek_response()
                    }
                }
            ]
        }
        
        # First call fails, second succeeds
        mock_post.side_effect = [
            requests.exceptions.RequestException("Temporary failure"),
            mock_success_response
        ]
        
        # Create analyzer with retry
        analyzer = DeepseekAnalyzer()
        analyzer.retry_count = 1  # Ensure at least 1 retry
        email_content = "Test content for retry mechanism"
        
        # Execute
        analysis_data, response_text, recommendation, error = await analyzer.analyze_email(email_content)
        
        # Assert
        assert error is None  # Should eventually succeed
        assert mock_post.call_count == 2  # Called twice due to retry
        assert mock_sleep.called  # Should have slept between retries
        assert recommendation == "standard_response"

    @pytest.mark.asyncio
    async def test_prompt_creation(self):
        """Test proper creation of analysis prompt."""
        # Create analyzer
        analyzer = DeepseekAnalyzer()
        email_content = "Test email content"
        
        # Generate prompt
        prompt = analyzer._create_analysis_prompt(email_content, "test_request_id")
        
        # Assert prompt contains key elements
        assert "REQUIRED elements" in prompt
        assert "ANALYSIS REQUIREMENTS" in prompt
        assert "FORMALITY ADJUSTMENT" in prompt
        assert "RESPONSE REQUIREMENTS" in prompt
        assert "OUTPUT FORMAT" in prompt
        assert email_content in prompt

    @pytest.mark.asyncio
    async def test_response_processing(self):
        """Test processing of analysis result into structured components."""
        # Create analyzer
        analyzer = DeepseekAnalyzer()
        
        # Test response with all components
        test_response = (
            "ANALYSIS:\n"
            "3/4 elements present. Missing elements: location. Risk factors: None. Detected tone: Casual (2).\n\n"
            "RESPONSE:\n"
            "Hi Team,\n\n"
            "Thank you for your meeting request. To help me schedule properly, could you please specify the location?\n\n"
            "Best regards,\nAI Assistant\n\n"
            "RECOMMENDATION: standard_response"
        )
        
        # Process the response
        analysis_data, response_text, recommendation = analyzer._process_analysis_result(test_response, "test_request_id")
        
        # Assert
        assert isinstance(analysis_data, dict)
        assert "missing elements" in analysis_data
        assert "location" in analysis_data["missing elements"].lower()
        
        assert response_text is not None
        assert "location" in response_text.lower()
        
        assert recommendation == "standard_response"
        
        # Test incomplete response handling
        incomplete_response = "ANALYSIS:\nMissing some information.\n\nRECOMMENDATION: needs_review"
        analysis_data, response_text, recommendation = analyzer._process_analysis_result(incomplete_response, "test_request_id")
        
        # Should handle missing RESPONSE section
        assert recommendation == "needs_review"
        assert response_text is not None

    @pytest.mark.asyncio
    async def test_decide_action(self):
        """Test decision logic for determining appropriate action."""
        # Create analyzer
        analyzer = DeepseekAnalyzer()
        
        # Test with explicit recommendation objects
        class MockResult:
            def __init__(self, rec):
                self.recommendation = rec
        
        # Test dictionary style
        assert analyzer.decide_action({"recommendation": "standard_response"}) == "respond"
        assert analyzer.decide_action({"recommendation": "needs_review"}) == "flag_for_review"
        assert analyzer.decide_action({"recommendation": "ignore"}) == "ignore"
        
        # Test object style
        assert analyzer.decide_action(MockResult("standard_response")) == "respond"
        assert analyzer.decide_action(MockResult("needs_review")) == "flag_for_review"
        assert analyzer.decide_action(MockResult("ignore")) == "ignore"
        
        # Test default behavior for unknown structure
        assert analyzer.decide_action("unknown") == "flag_for_review"
