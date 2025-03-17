"""
Comprehensive test suite for the ResponseCategorizer component.

This module implements exhaustive tests for the ResponseCategorizer, which serves
as the third stage of the email analysis pipeline as defined in analysis-pipeline.md.
The ResponseCategorizer processes structured analysis data from the DeepseekAnalyzer,
makes final categorization decisions, and prepares responses for delivery.

Testing strategy:
1. Mock dependencies to isolate testing of categorization logic
2. Test initialization and configuration
3. Test the main categorize_email method with various analysis scenarios
4. Test parameter extraction and response generation
5. Test fallback mechanisms and error handling
6. Test backward compatibility with legacy interfaces
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from src.email_processing.analyzers.response_categorizer import ResponseCategorizer


@pytest.fixture
def response_categorizer():
    """
    Fixture for creating a ResponseCategorizer instance with mocked dependencies.
    
    Creates an instance with mocked EnhancedGroqClient to prevent actual API calls
    during testing, ensuring isolated unit testing of the categorizer's logic.
    
    Returns:
        ResponseCategorizer: Configured categorizer instance for testing
    """
    with patch('src.email_processing.analyzers.response_categorizer.EnhancedGroqClient'):
        categorizer = ResponseCategorizer()
        return categorizer


@pytest.fixture
def complete_analysis_data():
    """
    Sample complete analysis data with all required meeting parameters.
    
    Returns:
        dict: Structured analysis data with complete meeting details
    """
    return {
        "completeness": "4/4 elements",
        "missing elements": "None",
        "risk factors": "None",
        "detected tone": "Neutral (3)",
        "date": "tomorrow",
        "time": "2:00 PM",
        "location": "Conference Room A",
        "agenda": "Q3 project plan",
        "tone": "formal"
    }


@pytest.fixture
def missing_info_analysis_data():
    """
    Sample analysis data with missing meeting parameters.
    
    Returns:
        dict: Structured analysis data with incomplete meeting details
    """
    return {
        "completeness": "2/4 elements",
        "missing elements": "time, location",
        "risk factors": "None",
        "detected tone": "Casual (2)",
        "date": "tomorrow",
        "agenda": "project discussion",
        "tone": "friendly"
    }


@pytest.fixture
def high_risk_analysis_data():
    """
    Sample high-risk analysis data requiring review.
    
    Returns:
        dict: Structured analysis data with risk factors that trigger review
    """
    return {
        "completeness": "4/4 elements",
        "missing elements": "None",
        "risk factors": "Financial commitments, Multi-party coordination",
        "detected tone": "Formal (4)",
        "date": "next Monday",
        "time": "10:00 AM",
        "location": "Executive Conference Room",
        "agenda": "Budget approval",
        "tone": "formal"
    }


class TestResponseCategorizer:
    """
    Comprehensive test suite for the ResponseCategorizer class.
    
    Tests initialization, categorization logic, parameter extraction, response
    generation, and error handling capabilities of the ResponseCategorizer
    component, which serves as the third stage of the email analysis pipeline.
    """

    def test_initialization(self):
        """
        Test that ResponseCategorizer initializes correctly with required components.
        
        Verifies that the categorizer loads configuration parameters correctly and
        sets up the expected client connection and model configuration.
        """
        with patch('src.email_processing.analyzers.response_categorizer.EnhancedGroqClient'):
            categorizer = ResponseCategorizer()
            assert hasattr(categorizer, 'client')
            assert hasattr(categorizer, 'model_config')
    
    async def test_categorize_email_standard_response(self, response_categorizer, complete_analysis_data):
        """
        Test categorizing a standard response with complete information.
        
        Verifies that the categorizer correctly processes complete analysis data
        with a standard_response recommendation, returning the appropriate category
        and pre-generated response text.
        """
        response_text = "Thank you for your meeting request. I confirm the meeting."
        deepseek_recommendation = "standard_response"
        
        # Call the method
        category, response_template = await response_categorizer.categorize_email(
            complete_analysis_data,
            response_text,
            deepseek_recommendation,
            "Meeting confirmed with all details"
        )
        
        # Assertions
        assert category == "standard_response"
        assert response_template == response_text
    
    async def test_categorize_email_missing_info(self, response_categorizer, missing_info_analysis_data):
        """
        Test categorizing an email with missing information.
        
        Verifies that the categorizer correctly processes analysis data with
        missing parameters, identifying which parameters are missing and generating
        an appropriate response requesting the missing information.
        """
        response_text = "Could you please provide the time and location?"
        deepseek_recommendation = "standard_response"
        
        # Call the method
        category, response_template = await response_categorizer.categorize_email(
            missing_info_analysis_data,
            response_text,
            deepseek_recommendation,
            "Missing time and location"
        )
        
        # Assertions
        assert category == "standard_response"
        assert response_template == response_text
    
    async def test_categorize_email_needs_review(self, response_categorizer, high_risk_analysis_data):
        """
        Test categorizing an email that needs review.
        
        Verifies that the categorizer correctly processes high-risk analysis data
        with a needs_review recommendation, returning the appropriate category
        and no response template as this requires human intervention.
        """
        response_text = "Your request requires additional review."
        deepseek_recommendation = "needs_review"
        
        # Call the method
        category, response_template = await response_categorizer.categorize_email(
            high_risk_analysis_data,
            response_text,
            deepseek_recommendation,
            "High risk content identified"
        )
        
        # Assertions
        assert category == "needs_review"
        assert response_template is None  # No response template for needs_review
    
    async def test_categorize_email_ignore(self, response_categorizer):
        """
        Test categorizing an email that should be ignored.
        
        Verifies that the categorizer correctly processes analysis data with
        an ignore recommendation, returning the appropriate category and no
        response template as no response is needed.
        """
        analysis_data = {"completeness": "0/4 elements"}
        response_text = "This is a notification email only."
        deepseek_recommendation = "ignore"
        
        # Call the method
        category, response_template = await response_categorizer.categorize_email(
            analysis_data,
            response_text,
            deepseek_recommendation,
            "Not a meeting email"
        )
        
        # Assertions
        assert category == "ignore"
        assert response_template is None  # No response template for ignore
    
    async def test_categorize_email_empty_response(self, response_categorizer, complete_analysis_data):
        """
        Test categorizing with empty response text but standard recommendation.
        
        Verifies that the categorizer handles cases where the DeepseekAnalyzer
        provides a standard_response recommendation but no response text, by
        generating an appropriate response based on the analysis data.
        """
        # Mock the generate_response_template method
        response_categorizer._generate_response_template = AsyncMock(return_value="Generated response")
        
        # Call the method
        category, response_template = await response_categorizer.categorize_email(
            complete_analysis_data,
            "",  # Empty response text
            "standard_response",
            "Complete meeting details but no response"
        )
        
        # Assertions
        assert category == "standard_response"
        assert response_template == "Generated response"
        assert response_categorizer._generate_response_template.called
    
    async def test_categorize_email_missing_parameters(self, response_categorizer, missing_info_analysis_data):
        """
        Test categorizing with missing parameters and empty response.
        
        Verifies that the categorizer correctly identifies missing parameters and
        generates an appropriate response requesting the specific missing information
        when no response text is provided by the DeepseekAnalyzer.
        """
        # Mock the generate_parameter_request method
        response_categorizer._generate_parameter_request = AsyncMock(return_value="Please provide missing details")
        
        # Call the method
        category, response_template = await response_categorizer.categorize_email(
            missing_info_analysis_data,
            "",  # Empty response text
            "standard_response",
            "Missing parameters"
        )
        
        # Assertions
        assert category == "standard_response"
        assert response_template == "Please provide missing details"
        assert response_categorizer._generate_parameter_request.called
    
    async def test_categorize_email_unknown_recommendation(self, response_categorizer, complete_analysis_data):
        """
        Test categorizing with unknown recommendation.
        
        Verifies that the categorizer safely handles unknown recommendations by
        defaulting to needs_review for human intervention, following the safety
        principles in error-handling.md.
        """
        # Call the method
        category, response_template = await response_categorizer.categorize_email(
            complete_analysis_data,
            "Some response",
            "unknown_recommendation",
            "Unknown recommendation"
        )
        
        # Assertions - should default to needs_review for safety
        assert category == "needs_review"
        assert response_template is None
    
    async def test_categorize_email_error_handling(self, response_categorizer, complete_analysis_data):
        """
        Test error handling during categorization.
        
        Verifies that the categorizer properly handles exceptions during processing,
        logging errors and defaulting to needs_review for human intervention.
        """
        # Mock _extract_missing_parameters_structured to raise an exception
        response_categorizer._extract_missing_parameters_structured = MagicMock(side_effect=Exception("Test error"))
        
        # Call the method
        category, response_template = await response_categorizer.categorize_email(
            complete_analysis_data,
            "Some response",
            "standard_response",
            "Error during processing"
        )
        
        # Assertions - should default to needs_review on error
        assert category == "needs_review"
        assert response_template is None
    
    def test_extract_missing_parameters_structured_direct(self, response_categorizer):
        """
        Test extracting missing parameters from structured data with direct field.
        
        Verifies that the categorizer correctly extracts missing parameters when
        they are explicitly listed in the missing_elements field of the analysis data.
        """
        # Test with direct missing_elements field
        analysis_data = {
            "missing elements": "date, time, location"
        }
        
        missing_params = response_categorizer._extract_missing_parameters_structured(analysis_data)
        
        # Assertions
        assert "date" in missing_params
        assert "time" in missing_params
        assert "location" in missing_params
        assert len(missing_params) == 3
    
    def test_extract_missing_parameters_structured_completeness(self, response_categorizer):
        """
        Test extracting missing parameters from structured data using completeness.
        
        Verifies that the categorizer can infer missing parameters from the
        completeness score when explicit missing_elements information is not available.
        """
        # Test with completeness score
        analysis_data = {
            "completeness": "1/4"
        }
        
        missing_params = response_categorizer._extract_missing_parameters_structured(analysis_data)
        
        # Assertions - should infer missing parameters
        assert len(missing_params) > 0
        # Typically defaults to critical parameters
        assert "date" in missing_params or "time" in missing_params or "location" in missing_params
    
    def test_extract_missing_parameters_text(self, response_categorizer):
        """
        Test extracting missing parameters from summary text.
        
        Verifies that the categorizer correctly identifies missing parameters
        from descriptive text when structured data is not available or incomplete.
        """
        summary = "Missing date for the meeting. Time is specified but location is missing."
        
        missing_params = response_categorizer._extract_missing_parameters(summary)
        
        # Assertions
        assert "date" in missing_params
        assert "location" in missing_params
        assert "time" not in missing_params  # Time is specified, so not missing
    
    async def test_generate_response_template_complete(self, response_categorizer):
        """
        Test generating a response template for complete meeting details.
        
        Verifies that the categorizer generates an appropriate confirmation
        response when all required meeting parameters are available.
        """
        analysis_data = {
            "sender_name": "John",
            "tone": "friendly",
            "missing_elements": "None",
            "date": "tomorrow",
            "time": "2:00 PM",
            "location": "Conference Room A",
            "agenda": "project planning"
        }
        
        response = await response_categorizer._generate_response_template(analysis_data)
        
        # Assertions
        assert "Hi John" in response  # Friendly greeting
        assert "Thank you for your meeting request" in response
        assert "tomorrow" in response
        assert "2:00 PM" in response
        assert "Conference Room A" in response
        assert "Thanks!" in response  # Friendly closing
    
    async def test_generate_response_template_formal(self, response_categorizer):
        """
        Test generating a formal response template.
        
        Verifies that the categorizer adjusts the response tone appropriately
        when a formal tone is specified, following the formality guidelines
        in response-management.md.
        """
        analysis_data = {
            "sender_name": "Dr. Smith",
            "tone": "formal",
            "missing_elements": "None",
            "date": "next Monday",
            "time": "10:00 AM",
            "location": "Executive Conference Room",
            "agenda": "budget approval"
        }
        
        response = await response_categorizer._generate_response_template(analysis_data)
        
        # Assertions
        assert "Dear Dr. Smith" in response  # Formal greeting
        assert "Thank you for your meeting request" in response
        assert "next Monday" in response
        assert "10:00 AM" in response
        assert "Executive Conference Room" in response
        assert "Best regards" in response  # Formal closing
    
    async def test_generate_parameter_request_friendly(self, response_categorizer):
        """
        Test generating a friendly parameter request based on missing parameters.
        
        Verifies that the categorizer generates an appropriate friendly-toned
        request for missing parameters when the sender's tone is casual.
        """
        analysis_data = {
            "sender_name": "John",
            "tone": "friendly"
        }
        missing_params = ["date", "location"]
        
        response = await response_categorizer._generate_parameter_request(
            analysis_data,
            missing_params,
            "Meeting request missing date and location"
        )
        
        # Assertions
        assert "Hi John," in response  # Friendly greeting
        assert "could you please provide" in response
        assert "the meeting date" in response
        assert "the exact meeting location" in response
        assert "Thanks!" in response  # Friendly closing
    
    async def test_generate_parameter_request_formal(self, response_categorizer):
        """
        Test generating a formal parameter request based on missing parameters.
        
        Verifies that the categorizer generates an appropriate formal-toned
        request for missing parameters when the sender's tone is formal.
        """
        analysis_data = {
            "sender_name": "Ms. Johnson",
            "tone": "formal"
        }
        missing_params = ["time", "agenda"]
        
        response = await response_categorizer._generate_parameter_request(
            analysis_data,
            missing_params,
            "Meeting request missing time and agenda"
        )
        
        # Assertions
        assert "Dear Ms. Johnson," in response  # Formal greeting
        assert "could you please provide" in response
        assert "the specific time" in response
        assert "the meeting purpose" in response
        assert "Best regards," in response  # Formal closing
    
    def test_format_missing_parameters(self, response_categorizer):
        """
        Test formatting missing parameters into natural language.
        
        Verifies that the categorizer formats lists of missing parameters
        into grammatically correct natural language phrases for inclusion
        in response templates.
        """
        # Test with single parameter
        single_param = response_categorizer._format_missing_parameters(["date"])
        assert single_param == "the meeting date"
        
        # Test with two parameters
        two_params = response_categorizer._format_missing_parameters(["date", "time"])
        assert two_params == "the meeting date and the meeting time"
        
        # Test with three parameters
        three_params = response_categorizer._format_missing_parameters(["date", "time", "location"])
        assert "the meeting date" in three_params
        assert "the meeting time" in three_params
        assert "the meeting location" in three_params
        assert "and" in three_params
    
    def test_generate_greeting(self, response_categorizer):
        """
        Test generating appropriate greetings based on tone.
        
        Verifies that the categorizer generates tone-appropriate greetings
        following the guidelines in response-management.md.
        """
        # Test friendly tone
        greeting = response_categorizer._generate_greeting("John", "friendly")
        assert greeting == "Hi John,"
        
        # Test formal tone
        greeting = response_categorizer._generate_greeting("Ms. Smith", "formal")
        assert greeting == "Dear Ms. Smith,"
        
        # Test with no sender name
        greeting = response_categorizer._generate_greeting(None, "formal")
        assert greeting == "Dear [Sender],"
    
    def test_extract_sender_name(self, response_categorizer):
        """
        Test extracting sender name from summary text.
        
        Verifies that the categorizer correctly extracts sender names from
        various text formats for personalization in responses.
        """
        # Test with clear sender information
        summary = "Email from John Smith requesting a meeting."
        sender_name = response_categorizer._extract_sender_name(summary)
        assert sender_name == "John Smith"
        
        # Test with different format
        summary = "The sender's name is Jane Doe."
        sender_name = response_categorizer._extract_sender_name(summary)
        assert sender_name == "Jane Doe"
        
        # Test with no sender information
        summary = "Meeting request for tomorrow."
        sender_name = response_categorizer._extract_sender_name(summary)
        assert sender_name is None
    
    def test_get_default_response_template(self, response_categorizer):
        """
        Test getting the default response template.
        
        Verifies that the categorizer provides a safe default response template
        when other response generation methods fail, ensuring graceful degradation.
        """
        template = response_categorizer._get_default_response_template()
        
        # Assertions
        assert "Dear Sender" in template
        assert "Thank you for your meeting request" in template
        assert "additional details" in template
        assert "Best regards" in template
    
    async def test_categorize_email_legacy(self, response_categorizer):
        """
        Test the legacy categorize_email method for backward compatibility.
        
        Verifies that the categorizer maintains backward compatibility with
        older code by supporting the legacy method signature while leveraging
        the new implementation internally.
        """
        # Mock the new categorize_email method
        response_categorizer.categorize_email = AsyncMock(return_value=("standard_response", "Response text"))
        
        # Call the legacy method
        category, response_template = await response_categorizer.categorize_email_legacy(
            "Meeting summary",
            "standard_response"
        )
        
        # Assertions
        assert category == "standard_response"
        assert response_template == "Response text"
        assert response_categorizer.categorize_email.called
        
        # Verify the new method was called with expected parameters
        call_args = response_categorizer.categorize_email.call_args
        assert isinstance(call_args[0][0], dict)  # Analysis data
        assert call_args[0][2] == "standard_response"  # Recommendation
