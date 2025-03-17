"""
Comprehensive Tests for ResponseCategorizer Component

This module implements extensive unit testing for the ResponseCategorizer class,
which represents the third stage of the four-stage email analysis pipeline.

The ResponseCategorizer is responsible for:
1. Processing structured analysis from DeepseekAnalyzer
2. Finalizing categorization decisions (standard_response, needs_review, ignore)
3. Extracting and processing response templates
4. Handling parameter requests for incomplete meeting details

The tests verify correct categorization logic, response generation,
parameter handling, and formatting under various scenarios.
"""

import pytest
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock, AsyncMock

from src.email_processing.analyzers.response_categorizer import ResponseCategorizer
from src.integrations.groq.client_wrapper import EnhancedGroqClient

class TestResponseCategorizer:
    """Test suite for ResponseCategorizer component with comprehensive coverage."""

    @pytest.fixture
    def categorizer(self):
        """Initialize ResponseCategorizer with mocked dependencies."""
        with patch('src.email_processing.analyzers.response_categorizer.EnhancedGroqClient') as mock_groq:
            # Configure mock GroqClient for response generation tests
            mock_instance = MagicMock(spec=EnhancedGroqClient)
            mock_groq.return_value = mock_instance
            
            # Setup async process_with_retry method
            async def mock_process(*args, **kwargs):
                # Mock the response structure
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message = MagicMock()
                mock_response.choices[0].message.content = "Test response text from Groq"
                return mock_response
                
            mock_instance.process_with_retry = AsyncMock(side_effect=mock_process)
            
            categorizer = ResponseCategorizer()
            yield categorizer

    @pytest.mark.asyncio
    async def test_categorize_email_standard_response(self, categorizer):
        """
        Test categorization of emails with complete meeting details.
        
        Verifies:
        - Proper categorization as standard_response
        - Correct use of pre-generated response text
        - Appropriate handling of complete meeting parameters
        """
        # Test data for complete meeting details
        analysis_data = {
            "date": "tomorrow",
            "time": "2pm",
            "location": "Conference Room A",
            "agenda": "project roadmap",
            "completeness": "4/4",
            "missing_elements": "None",
            "detected tone": "Neutral",
            "tone": "formal"
        }
        
        response_text = (
            "Thank you for your meeting request. I confirm our meeting tomorrow "
            "at 2pm in Conference Room A to discuss the project roadmap."
        )
        
        recommendation = "standard_response"
        
        # Process categorization
        category, template = await categorizer.categorize_email(
            analysis_data, response_text, recommendation
        )
        
        # Verify correct categorization
        assert category == "standard_response"
        assert template == response_text
        
        # Verify client was not called (used pre-generated response)
        categorizer.client.process_with_retry.assert_not_called()

    @pytest.mark.asyncio
    async def test_categorize_email_needs_review(self, categorizer):
        """
        Test categorization of emails needing human review.
        
        Verifies:
        - Proper categorization as needs_review
        - No response template is generated
        - Correct handling of complex or incomplete meeting details
        """
        # Test data for meeting needing review
        analysis_data = {
            "date": None,
            "time": None,
            "location": None,
            "agenda": "financial discussion",
            "completeness": "1/4",
            "missing_elements": "date, time, location",
            "risk_assessment": "high - financial implications",
            "detected tone": "Formal"
        }
        
        response_text = "Your meeting request needs more details. We'll have someone review it."
        recommendation = "needs_review"
        
        # Process categorization
        category, template = await categorizer.categorize_email(
            analysis_data, response_text, recommendation
        )
        
        # Verify correct categorization
        assert category == "needs_review"
        assert template is None  # No response template for needs_review
        
        # Verify client was not called
        categorizer.client.process_with_retry.assert_not_called()

    @pytest.mark.asyncio
    async def test_categorize_email_ignore(self, categorizer):
        """
        Test categorization of emails to be ignored.
        
        Verifies:
        - Proper categorization as ignore
        - No response template is generated
        - Correct handling of non-actionable content
        """
        # Test data for email to be ignored
        analysis_data = {
            "completeness": "0/4",
            "detected tone": "Neutral"
        }
        
        response_text = ""  # No response needed
        recommendation = "ignore"
        
        # Process categorization
        category, template = await categorizer.categorize_email(
            analysis_data, response_text, recommendation
        )
        
        # Verify correct categorization
        assert category == "ignore"
        assert template is None  # No response template for ignore
        
        # Verify client was not called
        categorizer.client.process_with_retry.assert_not_called()

    @pytest.mark.asyncio
    async def test_categorize_email_missing_parameters(self, categorizer):
        """
        Test handling of emails with missing meeting parameters.
        
        Verifies:
        - Proper extraction of missing elements
        - Generation of appropriate parameter request response
        - Correct formatting based on missing element count
        """
        # Test data for meeting with missing parameters
        analysis_data = {
            "date": "tomorrow",
            "time": None,  # Missing
            "location": None,  # Missing
            "agenda": "project discussion",
            "completeness": "2/4",
            "missing_elements": "time, location",
            "detected tone": "Neutral",
            "tone": "friendly"
        }
        
        response_text = "Thank you for your meeting request. Could you please provide the meeting time and location?"
        recommendation = "standard_response"  # Still standard if we can ask for specifics
        
        # Process categorization
        category, template = await categorizer.categorize_email(
            analysis_data, response_text, recommendation
        )
        
        # Verify correct categorization
        assert category == "standard_response"
        assert template == response_text
        
        # Verify parameters were extracted correctly
        with patch.object(categorizer, '_extract_missing_parameters_structured') as mock_extract:
            mock_extract.return_value = ["time", "location"]
            
            # Ensure method is called with analysis data
            await categorizer.categorize_email(
                analysis_data, "", recommendation
            )
            
            mock_extract.assert_called_once_with(analysis_data)

    @pytest.mark.asyncio
    async def test_extract_missing_parameters_structured(self, categorizer):
        """
        Test extraction of missing parameters from structured analysis data.
        
        Verifies:
        - Correct extraction from missing_elements field
        - Proper handling of various missing element formats
        - Fallback to completeness score when needed
        """
        # Test with explicit missing_elements field
        analysis_data1 = {
            "missing_elements": "time, location"
        }
        
        missing1 = categorizer._extract_missing_parameters_structured(analysis_data1)
        assert "time" in missing1
        assert "location" in missing1
        assert len(missing1) == 2
        
        # Test with different format of missing elements
        analysis_data2 = {
            "missing_elements": "Missing meeting time and venue details"
        }
        
        missing2 = categorizer._extract_missing_parameters_structured(analysis_data2)
        assert "time" in missing2
        assert "location" in missing2
        
        # Test with completeness score
        analysis_data3 = {
            "completeness": "2/4"
        }
        
        missing3 = categorizer._extract_missing_parameters_structured(analysis_data3)
        assert len(missing3) > 0  # Should infer missing elements from score
        
        # Test with "None" as missing elements
        analysis_data4 = {
            "missing_elements": "None"
        }
        
        missing4 = categorizer._extract_missing_parameters_structured(analysis_data4)
        assert len(missing4) == 0  # Should have no missing elements

    @pytest.mark.asyncio
    async def test_extract_missing_parameters_from_summary(self, categorizer):
        """
        Test extraction of missing parameters from text summary.
        
        Verifies:
        - Correct extraction from text descriptions
        - Handling of various formats and phrasings
        - Detection of different missing parameter types
        """
        # Test with explicit missing parameter mentions
        summary1 = "The meeting request is missing a specific time. Date and location are provided."
        missing1 = categorizer._extract_missing_parameters(summary1)
        assert "time" in missing1
        assert "date" not in missing1
        assert "location" not in missing1
        
        # Test with multiple missing parameters
        summary2 = "Meeting request has unclear location and no specified time."
        missing2 = categorizer._extract_missing_parameters(summary2)
        assert "time" in missing2
        assert "location" in missing2
        
        # Test with no missing parameters
        summary3 = "Meeting request contains all required details."
        missing3 = categorizer._extract_missing_parameters(summary3)
        assert len(missing3) == 0
        
        # Test with empty summary
        missing4 = categorizer._extract_missing_parameters("")
        assert len(missing4) == 0
        
        # Test with None summary
        missing5 = categorizer._extract_missing_parameters(None)
        assert len(missing5) == 0

    @pytest.mark.asyncio
    async def test_generate_response_template(self, categorizer):
        """
        Test generation of response templates.
        
        Verifies:
        - Proper response template generation
        - Formatting based on available data
        - Handling of missing elements
        - Tone-appropriate responses
        """
        # Mock client response for template generation
        async def mock_process(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "Thank you for your meeting request. I will review the details."
            return mock_response
            
        categorizer.client.process_with_retry = AsyncMock(side_effect=mock_process)
        
        # Test complete meeting response
        analysis_data1 = {
            "sender_name": "John",
            "tone": "friendly",
            "missing_elements": None
        }
        
        template1 = await categorizer._generate_response_template(analysis_data1)
        assert "Thank you" in template1
        assert "John" in template1  # Should include sender name
        
        # Test with missing elements
        analysis_data2 = {
            "sender_name": "Dr. Smith",
            "tone": "formal",
            "missing_elements": "time, location"
        }
        
        template2 = await categorizer._generate_response_template(analysis_data2)
        assert "Dr. Smith" in template2  # Should use formal address
        assert "could you please provide" in template2.lower()  # Should ask for missing info
        
        # Test with unknown sender
        analysis_data3 = {
            "tone": "formal",
            "missing_elements": None
        }
        
        template3 = await categorizer._generate_response_template(analysis_data3)
        assert "Thank you for your meeting request" in template3
        assert "Best regards" in template3  # Should use formal closing

    @pytest.mark.asyncio
    async def test_generate_parameter_request(self, categorizer):
        """
        Test generation of parameter request responses.
        
        Verifies:
        - Proper formatting of missing parameter requests
        - Appropriate tone based on sender formality
        - Correct handling of multiple missing parameters
        - Proper greeting and closing
        """
        # Test single missing parameter
        analysis_data1 = {
            "sender_name": "John",
            "tone": "friendly"
        }
        missing_params1 = ["time"]
        
        request1 = await categorizer._generate_parameter_request(
            analysis_data1, missing_params1, None
        )
        
        assert "Hi John," in request1  # Friendly greeting
        assert "could you please provide the meeting time" in request1.lower()
        assert "Thanks!" in request1  # Friendly closing
        
        # Test multiple missing parameters
        analysis_data2 = {
            "sender_name": "Dr. Smith",
            "tone": "formal"
        }
        missing_params2 = ["date", "time", "location"]
        
        request2 = await categorizer._generate_parameter_request(
            analysis_data2, missing_params2, None
        )
        
        assert "Dear Dr. Smith," in request2  # Formal greeting
        assert "could you please provide" in request2.lower()
        assert "the meeting date" in request2
        assert "the meeting time" in request2
        assert "the exact meeting location" in request2
        assert "Best regards," in request2  # Formal closing

    @pytest.mark.asyncio
    async def test_generate_greeting(self, categorizer):
        """
        Test generation of tone-appropriate greetings.
        
        Verifies:
        - Proper greeting format based on formality level
        - Inclusion of sender name when available
        - Appropriate fallback for unknown senders
        """
        # Test friendly greeting with name
        greeting1 = categorizer._generate_greeting("John", "friendly")
        assert greeting1 == "Hi John,"
        
        # Test formal greeting with name
        greeting2 = categorizer._generate_greeting("Dr. Smith", "formal")
        assert greeting2 == "Dear Dr. Smith,"
        
        # Test friendly greeting without name
        greeting3 = categorizer._generate_greeting(None, "friendly")
        assert greeting3 == "Hi [Sender],"
        
        # Test formal greeting without name
        greeting4 = categorizer._generate_greeting(None, "formal")
        assert greeting4 == "Dear [Sender],"

    @pytest.mark.asyncio
    async def test_extract_sender_name(self, categorizer):
        """
        Test extraction of sender name from summary text.
        
        Verifies:
        - Proper extraction of name using various patterns
        - Handling of different summary formats
        - Appropriate fallback for unrecognized formats
        """
        # Test explicit sender format
        summary1 = "This is an email from John Smith regarding a meeting tomorrow."
        name1 = categorizer._extract_sender_name(summary1)
        assert name1 == "John Smith"
        
        # Test sender: format
        summary2 = "Sender: Dr. Jane Doe"
        name2 = categorizer._extract_sender_name(summary2)
        assert name2 == "Dr. Jane Doe"
        
        # Test from: format
        summary3 = "From: Michael Johnson"
        name3 = categorizer._extract_sender_name(summary3)
        assert name3 == "Michael Johnson"
        
        # Test no recognizable pattern
        summary4 = "Meeting request received on March 15th."
        name4 = categorizer._extract_sender_name(summary4)
        assert name4 is None
        
        # Test empty summary
        name5 = categorizer._extract_sender_name("")
        assert name5 is None
        
        # Test None summary
        name6 = categorizer._extract_sender_name(None)
        assert name6 is None

    @pytest.mark.asyncio
    async def test_get_default_response_template(self, categorizer):
        """
        Test retrieval of default response template.
        
        Verifies:
        - Appropriate default template format
        - Template contains greeting, body, and closing
        - Generic content suitable for fallback scenario
        """
        template = categorizer._get_default_response_template()
        
        # Verify template structure
        assert "Dear Sender," in template
        assert "Thank you for your meeting request" in template
        assert "Best regards," in template
        assert "Ivaylo's AI Assistant" in template
        
        # Verify it contains a request for details
        assert "could you please provide additional details" in template.lower()

    @pytest.mark.asyncio
    async def test_categorize_email_legacy(self, categorizer):
        """
        Test legacy categorization method for backward compatibility.
        
        Verifies:
        - Proper handling of legacy format inputs
        - Correct conversion to new format internally
        - Consistent results between legacy and new interfaces
        """
        # Test legacy method with standard response
        deepseek_summary = "Meeting request for tomorrow at 2pm in Conference Room A."
        deepseek_recommendation = "standard_response"
        
        with patch.object(categorizer, 'categorize_email') as mock_categorize:
            # Set return value for the patched method
            mock_categorize.return_value = ("standard_response", "Thank you for your meeting request.")
            
            # Call legacy method
            result = await categorizer.categorize_email_legacy(
                deepseek_summary, deepseek_recommendation
            )
            
            # Verify correct parameters passed to new method
            mock_categorize.assert_called_once()
            args, kwargs = mock_categorize.call_args
            
            # Verify empty analysis_data
            assert isinstance(kwargs['analysis_data'], dict)
            assert len(kwargs['analysis_data']) == 0
            
            # Verify empty response_text
            assert kwargs['response_text'] == ""
            
            # Verify recommendation passed through
            assert kwargs['deepseek_recommendation'] == deepseek_recommendation
            
            # Verify summary passed through
            assert kwargs['deepseek_summary'] == deepseek_summary
            
            # Verify result matches mock return value
            assert result == ("standard_response", "Thank you for your meeting request.")

    @pytest.mark.asyncio
    async def test_error_handling(self, categorizer):
        """
        Test error handling during categorization.
        
        Verifies:
        - Proper handling of exceptions during processing
        - Appropriate fallback to safe values
        - Logging of errors without propagation
        """
        # Test with analysis data that causes exception
        analysis_data = {
            "problematic_field": lambda x: x()  # Will cause exception when accessed
        }
        
        response_text = "Test response"
        recommendation = "standard_response"
        
        # Process categorization with problematic data
        with patch('src.email_processing.analyzers.response_categorizer.logger') as mock_logger:
            category, template = await categorizer.categorize_email(
                analysis_data, response_text, recommendation
            )
            
            # Verify error was logged
            assert mock_logger.error.called
            
            # Verify safe fallback
            assert category == "needs_review"  # Default to needs_review on error
            assert template is None  # No template on error

    @pytest.mark.asyncio
    async def test_formality_adaptation(self, categorizer):
        """
        Test adaptation of response formality based on detected tone.
        
        Verifies:
        - Proper detection of sender formality level
        - Appropriate adjustment of response formality
        - Consistent formatting across different formality levels
        """
        # Test formal tone adaptation
        analysis_data_formal = {
            "sender_name": "Dr. Smith",
            "detected tone": "Formal",
            "tone": "formal",
            "missing_elements": None
        }
        
        template_formal = await categorizer._generate_response_template(analysis_data_formal)
        
        # Verify formal elements
        assert "Dear Dr. Smith," in template_formal
        assert "Best regards," in template_formal
        assert "!" not in template_formal  # No exclamation marks in formal tone
        
        # Test friendly tone adaptation
        analysis_data_friendly = {
            "sender_name": "John",
            "detected tone": "Casual",
            "tone": "friendly",
            "missing_elements": None
        }
        
        template_friendly = await categorizer._generate_response_template(analysis_data_friendly)
        
        # Verify friendly elements
        assert "Hi John," in template_friendly
        assert "Thanks!" in template_friendly  # Friendly closing with exclamation
