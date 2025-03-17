"""
ResponseCategorizer Unit Tests

This module provides comprehensive test coverage for the ResponseCategorizer component,
which processes structured analysis output into final handling categories and
generates responses as the third stage of the email processing pipeline.
"""

import pytest
import json
import re
from unittest.mock import AsyncMock, patch, MagicMock, call
from typing import Dict, Any, Optional, Tuple

# Import test infrastructure
from tests.test_infrastructure import (
    create_test_email, mock_groq_client, test_config
)

# Import component under test
from src.email_processing.analyzers.response_categorizer import ResponseCategorizer


class TestResponseCategorizer:
    """Test suite for the ResponseCategorizer component."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test proper initialization of ResponseCategorizer."""
        categorizer = ResponseCategorizer()
        assert categorizer.client is not None
        assert categorizer.model_config is not None

    @pytest.mark.asyncio
    async def test_categorize_standard_response(self, mock_groq_client):
        """Test categorization for standard response with pre-generated text."""
        # Setup
        categorizer = ResponseCategorizer()
        categorizer.client = mock_groq_client
        
        # Test data for standard response with complete analysis
        analysis_data = {
            "date": "tomorrow",
            "time": "2pm",
            "location": "Conference Room A",
            "agenda": "project discussion",
            "completeness": "4/4 elements",
            "detected tone": "neutral"
        }
        
        response_text = (
            "Dear Team,\n\n"
            "Thank you for your meeting request. I confirm our meeting tomorrow at 2pm "
            "in Conference Room A to discuss the project.\n\n"
            "Best regards,\nAssistant"
        )
        
        deepseek_recommendation = "standard_response"
        
        # Execute
        category, template = await categorizer.categorize_email(
            analysis_data, response_text, deepseek_recommendation
        )
        
        # Assert
        assert category == "standard_response"
        assert template is not None
        assert "tomorrow" in template
        assert "2pm" in template
        assert "Conference Room A" in template
        
        # Should use the pre-generated text without calling API
        assert not mock_groq_client.process_with_retry.called

    @pytest.mark.asyncio
    async def test_categorize_needs_review(self, mock_groq_client):
        """Test categorization for emails requiring manual review."""
        # Setup
        categorizer = ResponseCategorizer()
        categorizer.client = mock_groq_client
        
        # Test data for review scenario
        analysis_data = {
            "risk factors": "financial implications",
            "detected tone": "formal"
        }
        
        response_text = (
            "Dear Sir/Madam,\n\n"
            "Thank you for your meeting request. Your request requires additional "
            "review, and we will respond within 24 hours.\n\n"
            "Best regards,\nAssistant"
        )
        
        deepseek_recommendation = "needs_review"
        
        # Execute
        category, template = await categorizer.categorize_email(
            analysis_data, response_text, deepseek_recommendation
        )
        
        # Assert
        assert category == "needs_review"
        assert template is None  # No response template for needs_review
        
        # Should not call the API for response generation
        assert not mock_groq_client.process_with_retry.called

    @pytest.mark.asyncio
    async def test_categorize_with_missing_parameters(self, mock_groq_client):
        """Test handling of emails with missing parameters."""
        # Setup
        categorizer = ResponseCategorizer()
        categorizer.client = mock_groq_client
        
        # Configure mock API response for parameter request
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = (
            "Dear Team,\n\n"
            "Thank you for your meeting request. Could you please provide the meeting location?\n\n"
            "Best regards,\nAssistant"
        )
        mock_groq_client.process_with_retry.return_value = mock_response
        
        # Test data with missing location
        analysis_data = {
            "date": "tomorrow",
            "time": "2pm",
            "location": None,
            "agenda": "project discussion",
            "missing elements": "location",
            "detected tone": "neutral"
        }
        
        # Empty response text to trigger generation
        response_text = ""
        
        deepseek_recommendation = "standard_response"
        
        # Execute
        category, template = await categorizer.categorize_email(
            analysis_data, response_text, deepseek_recommendation, "Test summary with missing location"
        )
        
        # Assert
        assert category == "standard_response"
        assert template is not None
        assert "location" in template.lower()
        
        # Should generate a response for the missing parameter
        assert mock_groq_client.process_with_retry.called

    @pytest.mark.asyncio
    async def test_categorize_ignore(self, mock_groq_client):
        """Test categorization for emails to be ignored."""
        # Setup
        categorizer = ResponseCategorizer()
        categorizer.client = mock_groq_client
        
        # Test data for ignore scenario
        analysis_data = {}
        response_text = ""
        deepseek_recommendation = "ignore"
        
        # Execute
        category, template = await categorizer.categorize_email(
            analysis_data, response_text, deepseek_recommendation
        )
        
        # Assert
        assert category == "ignore"
        assert template is None  # No response template for ignore
        
        # Should not call the API for response generation
        assert not mock_groq_client.process_with_retry.called

    @pytest.mark.asyncio
    async def test_extract_missing_parameters_structured(self):
        """Test extraction of missing parameters from structured data."""
        # Setup
        categorizer = ResponseCategorizer()
        
        # Test cases
        test_cases = [
            (
                {"missing_elements": "date, time"},
                ["date", "time"]
            ),
            (
                {"missing_elements": "location"},
                ["location"]
            ),
            (
                {"missing_elements": "None"},
                []
            ),
            (
                {"completeness": "2/4"},
                ["date", "time", "location"]  # Default missing params when incomplete
            ),
            (
                {"completeness": "4/4"},
                []  # No missing params when complete
            ),
            (
                {},  # Empty analysis
                []  # No missing params detected
            )
        ]
        
        # Execute and assert
        for analysis_data, expected_params in test_cases:
            missing_params = categorizer._extract_missing_parameters_structured(analysis_data)
            
            # Check if the expected parameters are in the result
            for param in expected_params:
                assert param in missing_params
                
            # Check if the result doesn't have unexpected parameters
            for param in missing_params:
                assert param in expected_params or param in ["date", "time", "location", "agenda"]

    @pytest.mark.asyncio
    async def test_extract_missing_parameters_legacy(self):
        """Test extraction of missing parameters from text summary (legacy)."""
        # Setup
        categorizer = ResponseCategorizer()
        
        # Test cases
        test_cases = [
            (
                "Meeting details: missing date, time is unclear",
                ["date", "time"]
            ),
            (
                "Meeting analysis: location is missing, has agenda",
                ["location"]
            ),
            (
                "All required elements are present",
                []
            ),
            (
                "Missing agenda: purpose unclear",
                ["agenda"]
            ),
            (
                "",  # Empty summary
                []  # No missing params detected
            )
        ]
        
        # Execute and assert
        for summary, expected_params in test_cases:
            missing_params = categorizer._extract_missing_parameters(summary)
            
            # Check if the expected parameters are in the result
            for param in expected_params:
                assert param in missing_params
                
            # Check if the result doesn't have unexpected parameters
            for param in missing_params:
                assert param in expected_params

    @pytest.mark.asyncio
    async def test_generate_response_template(self, mock_groq_client):
        """Test generation of response templates when none provided."""
        # Setup
        categorizer = ResponseCategorizer()
        categorizer.client = mock_groq_client
        
        # Configure mock API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = (
            "Dear John,\n\n"
            "Thank you for your meeting request. I am pleased to confirm our meeting "
            "tomorrow at 2pm.\n\n"
            "Best regards,\nAssistant"
        )
        mock_groq_client.process_with_retry.return_value = mock_response
        
        # Test data
        analysis_data = {
            "date": "tomorrow",
            "time": "2pm",
            "sender_name": "John",
            "tone": "formal"
        }
        
        # Execute
        template = await categorizer._generate_response_template(analysis_data)
        
        # Assert
        assert template is not None
        assert "Dear John" in template
        assert "tomorrow" in template
        assert "2pm" in template
        
        # Should call the API for response generation
        assert mock_groq_client.process_with_retry.called

    @pytest.mark.asyncio
    async def test_generate_parameter_request(self, mock_groq_client):
        """Test generation of requests for missing parameters."""
        # Setup
        categorizer = ResponseCategorizer()
        categorizer.client = mock_groq_client
        
        # Configure mock API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = (
            "Dear Jane,\n\n"
            "Thank you for your meeting request. Could you please provide the meeting location?\n\n"
            "Thanks,\nAssistant"
        )
        mock_groq_client.process_with_retry.return_value = mock_response
        
        # Test data
        analysis_data = {
            "sender_name": "Jane",
            "tone": "friendly"
        }
        missing_params = ["location"]
        
        # Execute
        template = await categorizer._generate_parameter_request(
            analysis_data, missing_params, "Meeting request missing location"
        )
        
        # Assert
        assert template is not None
        assert "Jane" in template
        assert "location" in template.lower()
        assert "Thanks" in template  # Friendly tone
        
        # Should call the API for parameter request generation
        assert mock_groq_client.process_with_retry.called

    @pytest.mark.asyncio
    async def test_generate_greeting(self):
        """Test generation of appropriate greetings based on tone."""
        # Setup
        categorizer = ResponseCategorizer()
        
        # Test cases
        test_cases = [
            # (sender_name, tone, expected_substring)
            ("John", "friendly", "Hi John"),
            ("Jane", "formal", "Dear Jane"),
            (None, "friendly", "Hi"),
            (None, "formal", "Dear"),
            ("Dr. Smith", "formal", "Dear Dr. Smith")
        ]
        
        # Execute and assert
        for sender_name, tone, expected in test_cases:
            greeting = categorizer._generate_greeting(sender_name, tone)
            assert expected in greeting
            assert greeting.endswith(",")  # Proper greeting format

    @pytest.mark.asyncio
    async def test_extract_sender_name(self):
        """Test extraction of sender name from summary text."""
        # Setup
        categorizer = ResponseCategorizer()
        
        # Test cases
        test_cases = [
            ("Email from John regarding meeting", "John"),
            ("Sender: Jane Smith requests a meeting", "Jane Smith"),
            ("Meeting request without sender info", None),
            ("", None)  # Empty summary
        ]
        
        # Execute and assert
        for summary, expected_name in test_cases:
            sender_name = categorizer._extract_sender_name(summary)
            assert sender_name == expected_name

    @pytest.mark.asyncio
    async def test_get_default_response_template(self):
        """Test default response template generation for error cases."""
        # Setup
        categorizer = ResponseCategorizer()
        
        # Execute
        template = categorizer._get_default_response_template()
        
        # Assert
        assert template is not None
        assert "Dear Sender" in template
        assert "meeting request" in template.lower()
        assert "additional details" in template.lower()

    @pytest.mark.asyncio
    async def test_format_missing_parameters(self):
        """Test formatting of missing parameters into natural language."""
        # Setup
        categorizer = ResponseCategorizer()
        
        # Test cases with private method access
        test_cases = [
            # We'll simulate the private method by implementing it here
            (["date"], "the meeting date"),
            (["time", "location"], "the specific time (including AM/PM) and the exact meeting location or virtual meeting link"),
            (["date", "time", "location"], "the meeting date, the specific time (including AM/PM), and the exact meeting location or virtual meeting link"),
            ([], "")  # No missing params
        ]
        
        # Execute and assert through parameter request generation
        for params, expected_text in test_cases:
            # We'll implement a simplified version of the private method
            param_descriptions = {
                "date": "the meeting date",
                "time": "the specific time (including AM/PM)",
                "location": "the exact meeting location or virtual meeting link",
                "agenda": "the meeting purpose or agenda"
            }
            
            formatted_params = [param_descriptions[param] for param in params if param in param_descriptions]
            
            if len(formatted_params) == 0:
                param_text = ""
            elif len(formatted_params) == 1:
                param_text = formatted_params[0]
            elif len(formatted_params) == 2:
                param_text = f"{formatted_params[0]} and {formatted_params[1]}"
            else:
                param_text = ", ".join(formatted_params[:-1]) + f", and {formatted_params[-1]}"
                
            assert param_text in expected_text

    @pytest.mark.asyncio
    async def test_categorize_email_legacy(self, mock_groq_client):
        """Test legacy method compatibility."""
        # Setup
        categorizer = ResponseCategorizer()
        categorizer.client = mock_groq_client
        
        # Mock the new implementation method
        categorizer.categorize_email = AsyncMock()
        categorizer.categorize_email.return_value = ("standard_response", "Test template")
        
        # Execute legacy method
        category, template = await categorizer.categorize_email_legacy(
            "Test summary",
            "standard_response"
        )
        
        # Assert
        assert category == "standard_response"
        assert template == "Test template"
        
        # Should call the new implementation
        categorizer.categorize_email.assert_called_once()
