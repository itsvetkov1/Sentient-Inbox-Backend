"""
Comprehensive test suite for the DeepseekAnalyzer component.

This module implements exhaustive tests for the DeepseekAnalyzer, which serves 
as the second stage of the email analysis pipeline as defined in analysis-pipeline.md. 
The DeepseekAnalyzer is responsible for detailed content analysis of meeting-related 
emails, extracting parameters, assessing risk factors, and generating appropriate responses.

Testing strategy:
1. Mock the API calls to avoid making actual requests
2. Test initialization parameters and configuration
3. Test the main analyze_email method with various scenarios
4. Test error handling and recovery mechanisms
5. Test the decide_action method with different recommendations
6. Test internal helper methods for prompt creation and response processing
"""

import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from src.email_processing.analyzers.deepseek import DeepseekAnalyzer


@pytest.fixture
def deepseek_analyzer():
    """
    Fixture for creating a DeepseekAnalyzer instance with mocked dependencies.
    
    Creates an instance with a mock API key and replaces the _call_deepseek_api method
    with an AsyncMock to prevent actual API calls during testing.
    
    Returns:
        DeepseekAnalyzer: Configured analyzer instance with mocked API method
    """
    with patch('src.email_processing.analyzers.deepseek.os.getenv', return_value='fake_api_key'):
        analyzer = DeepseekAnalyzer()
        # Mock the internal API call method to prevent actual API calls
        analyzer._call_deepseek_api = AsyncMock()
        return analyzer


@pytest.fixture
def sample_meeting_email():
    """
    Sample email content for testing meeting-related scenarios.
    
    Returns:
        str: Sample email text with complete meeting details
    """
    return """
    Hi Team,
    
    Let's have a meeting tomorrow at 2:00 PM in Conference Room A to discuss the Q3 project plan.
    Please bring your department reports.
    
    Best regards,
    John Smith
    """


@pytest.fixture
def sample_incomplete_meeting_email():
    """
    Sample email content for testing meeting scenarios with missing information.
    
    Returns:
        str: Sample email text with incomplete meeting details
    """
    return """
    Hi Team,
    
    Let's meet to discuss the Q3 project plan soon.
    Please bring your department reports.
    
    Best regards,
    John Smith
    """


@pytest.fixture
def sample_complex_meeting_email():
    """
    Sample email content for testing complex meeting scenarios requiring review.
    
    Returns:
        str: Sample email text with complex requirements that should trigger review
    """
    return """
    Dear Executive Team,
    
    I'd like to schedule a meeting to discuss the proposed budget allocation for Q3,
    including financial commitments to our new product lines. The meeting will involve
    representatives from Finance, Legal, and all department heads.
    
    Let's meet tomorrow at 10:00 AM in the Executive Conference Room.
    Please prepare your budget justifications and ROI projections.
    
    Best regards,
    Jane Doe
    CEO
    """


@pytest.fixture
def sample_api_response_standard():
    """
    Sample API response for standard meeting scenario.
    
    Returns:
        str: Mock API response with complete analysis and standard_response recommendation
    """
    return """
    ANALYSIS:
    Completeness: 4/4 elements
    Missing elements: None
    Risk factors: None
    Detected tone: Neutral (3)
    
    RESPONSE:
    Dear John,
    
    Thank you for your meeting request. I confirm our meeting tomorrow at 2:00 PM in Conference Room A to discuss the Q3 project plan.
    
    Best regards,
    Assistant
    
    RECOMMENDATION: standard_response
    """


@pytest.fixture
def sample_api_response_missing_info():
    """
    Sample API response for meeting with missing information.
    
    Returns:
        str: Mock API response with missing information and standard_response recommendation
    """
    return """
    ANALYSIS:
    Completeness: 2/4 elements
    Missing elements: time, location
    Risk factors: None
    Detected tone: Casual (2)
    
    RESPONSE:
    Hi John,
    
    Thanks for your meeting request. Could you please provide the specific time and location for the meeting?
    
    Thanks!
    Assistant
    
    RECOMMENDATION: standard_response
    """


@pytest.fixture
def sample_api_response_needs_review():
    """
    Sample API response for complex meeting requiring review.
    
    Returns:
        str: Mock API response with risk factors and needs_review recommendation
    """
    return """
    ANALYSIS:
    Completeness: 4/4 elements
    Missing elements: None
    Risk factors: Financial commitments, Multi-party coordination
    Detected tone: Formal (4)
    
    RESPONSE:
    Dear Ms. Doe,
    
    Thank you for your meeting request. Your request requires additional review, and we will respond within 24 hours.
    
    Best regards,
    Assistant
    
    RECOMMENDATION: needs_review
    """


@pytest.fixture
def sample_api_response_ignore():
    """
    Sample API response for email that should be ignored.
    
    Returns:
        str: Mock API response with ignore recommendation
    """
    return """
    ANALYSIS:
    Completeness: 0/4 elements
    Missing elements: date, time, location, agenda
    Risk factors: None
    Detected tone: Neutral (3)
    
    RESPONSE:
    This email doesn't appear to require a response.
    
    RECOMMENDATION: ignore
    """


class TestDeepseekAnalyzer:
    """
    Comprehensive test suite for the DeepseekAnalyzer class.
    
    Tests initialization, configuration, API interaction, and analysis processing
    capabilities of the DeepseekAnalyzer component, which serves as the second
    stage of the email analysis pipeline.
    """

    def test_initialization(self):
        """
        Test that DeepseekAnalyzer initializes correctly with proper configuration.
        
        Verifies that the analyzer loads configuration parameters correctly and
        sets up the expected default values as per the analyzer_config.py.
        """
        with patch('src.email_processing.analyzers.deepseek.os.getenv', return_value='fake_api_key'):
            analyzer = DeepseekAnalyzer()
            assert analyzer.model_name == "deepseek-reasoner"
            assert analyzer.api_key == "fake_api_key"
            assert analyzer.temperature == 0.7
            assert analyzer.retry_count == 1
            assert analyzer.retry_delay == 3
            assert hasattr(analyzer, 'formality_levels')
    
    async def test_analyze_email_standard_meeting(self, deepseek_analyzer, sample_meeting_email, sample_api_response_standard):
        """
        Test analyzing a standard meeting email with complete information.
        
        Verifies that the analyzer correctly processes a standard meeting email,
        extracts the appropriate analysis data, and generates the expected response.
        """
        # Configure mock to return standard response
        deepseek_analyzer._call_deepseek_api.return_value = sample_api_response_standard
        
        # Call the method
        analysis_data, response_text, recommendation, error = await deepseek_analyzer.analyze_email(sample_meeting_email)
        
        # Assertions
        assert error is None
        assert recommendation == "standard_response"
        assert "Thank you for your meeting request" in response_text
        assert analysis_data["completeness"] == "4/4 elements"
        assert "Missing elements" in analysis_data
        assert analysis_data["detected tone"] == "Neutral (3)"
        assert deepseek_analyzer._call_deepseek_api.called
    
    async def test_analyze_email_missing_info(self, deepseek_analyzer, sample_incomplete_meeting_email, sample_api_response_missing_info):
        """
        Test analyzing a meeting email with missing information.
        
        Verifies that the analyzer correctly identifies missing elements,
        extracts the available data, and generates an appropriate response
        requesting the missing information.
        """
        # Configure mock to return missing info response
        deepseek_analyzer._call_deepseek_api.return_value = sample_api_response_missing_info
        
        # Call the method
        analysis_data, response_text, recommendation, error = await deepseek_analyzer.analyze_email(sample_incomplete_meeting_email)
        
        # Assertions
        assert error is None
        assert recommendation == "standard_response"
        assert "Could you please provide" in response_text
        assert analysis_data["completeness"] == "2/4 elements"
        assert analysis_data["missing elements"] == "time, location"
        assert analysis_data["detected tone"] == "Casual (2)"
    
    async def test_analyze_email_needs_review(self, deepseek_analyzer, sample_complex_meeting_email, sample_api_response_needs_review):
        """
        Test analyzing a complex meeting that requires human review.
        
        Verifies that the analyzer correctly identifies high-risk scenarios,
        extracts risk factors, and recommends human review with an appropriate
        notification response.
        """
        # Configure mock to return needs review response
        deepseek_analyzer._call_deepseek_api.return_value = sample_api_response_needs_review
        
        # Call the method
        analysis_data, response_text, recommendation, error = await deepseek_analyzer.analyze_email(sample_complex_meeting_email)
        
        # Assertions
        assert error is None
        assert recommendation == "needs_review"
        assert "requires additional review" in response_text
        assert analysis_data["completeness"] == "4/4 elements"
        assert "Financial commitments" in analysis_data["risk factors"]
    
    async def test_analyze_email_ignore(self, deepseek_analyzer, sample_meeting_email, sample_api_response_ignore):
        """
        Test analyzing an email that should be ignored.
        
        Verifies that the analyzer correctly identifies emails that don't require
        a response, and recommends ignoring them with appropriate analysis data.
        """
        # Configure mock to return ignore response
        deepseek_analyzer._call_deepseek_api.return_value = sample_api_response_ignore
        
        # Call the method
        analysis_data, response_text, recommendation, error = await deepseek_analyzer.analyze_email(sample_meeting_email)
        
        # Assertions
        assert error is None
        assert recommendation == "ignore"
        assert response_text is not None  # We still get a response text
        assert analysis_data["completeness"] == "0/4 elements"
        assert "missing elements" in analysis_data
    
    async def test_analyze_email_api_error(self, deepseek_analyzer, sample_meeting_email):
        """
        Test handling API call errors during analysis.
        
        Verifies that the analyzer properly handles API errors, returns appropriate
        error information, and follows error handling protocols from error-handling.md.
        """
        # Configure mock to raise an exception
        deepseek_analyzer._call_deepseek_api.side_effect = Exception("API connection failed")
        
        # Call the method
        analysis_data, response_text, recommendation, error = await deepseek_analyzer.analyze_email(sample_meeting_email)
        
        # Assertions
        assert error is not None
        assert "API connection failed" in error
        assert recommendation == "needs_review"  # Default to needs_review on error
        assert response_text == ""
        assert analysis_data == {}
    
    async def test_analyze_email_empty_content(self, deepseek_analyzer):
        """
        Test handling empty email content.
        
        Verifies that the analyzer handles empty content gracefully by still
        attempting to process it, following the error handling guidelines.
        """
        # Configure mock for empty content
        deepseek_analyzer._call_deepseek_api.return_value = "ANALYSIS:\nEmpty content\n\nRECOMMENDATION: needs_review"
        
        # Call the method with empty content
        analysis_data, response_text, recommendation, error = await deepseek_analyzer.analyze_email("")
        
        # The analyzer should still attempt to process it
        assert deepseek_analyzer._call_deepseek_api.called
        assert error is None
        assert recommendation == "needs_review"
    
    async def test_analyze_email_none_content(self, deepseek_analyzer):
        """
        Test handling None email content.
        
        Verifies that the analyzer handles None content gracefully without crashing,
        and returns appropriate error information.
        """
        # Call the method with None content
        analysis_data, response_text, recommendation, error = await deepseek_analyzer.analyze_email(None)
        
        # Assertions - should handle None gracefully
        assert error is not None
        assert recommendation == "needs_review"  # Default to needs_review on error
        assert not deepseek_analyzer._call_deepseek_api.called  # Should not make API call
    
    def test_decide_action_standard_response(self, deepseek_analyzer):
        """
        Test the decide_action method with standard_response recommendation.
        
        Verifies that standard_response recommendation is correctly mapped to
        "respond" action as defined in the classification-categories.md.
        """
        # Create a mock result with standard_response recommendation
        result = MagicMock()
        result.recommendation = "standard_response"
        
        # Call the method
        action = deepseek_analyzer.decide_action(result)
        
        # Assertions
        assert action == "respond"
    
    def test_decide_action_needs_review(self, deepseek_analyzer):
        """
        Test the decide_action method with needs_review recommendation.
        
        Verifies that needs_review recommendation is correctly mapped to
        "flag_for_review" action as defined in the classification-categories.md.
        """
        # Create a mock result with needs_review recommendation
        result = MagicMock()
        result.recommendation = "needs_review"
        
        # Call the method
        action = deepseek_analyzer.decide_action(result)
        
        # Assertions
        assert action == "flag_for_review"
    
    def test_decide_action_ignore(self, deepseek_analyzer):
        """
        Test the decide_action method with ignore recommendation.
        
        Verifies that ignore recommendation is correctly mapped to
        "ignore" action as defined in the classification-categories.md.
        """
        # Create a mock result with ignore recommendation
        result = MagicMock()
        result.recommendation = "ignore"
        
        # Call the method
        action = deepseek_analyzer.decide_action(result)
        
        # Assertions
        assert action == "ignore"
    
    def test_decide_action_unknown(self, deepseek_analyzer):
        """
        Test the decide_action method with unknown recommendation.
        
        Verifies that unknown recommendations are handled safely by defaulting
        to "flag_for_review" action for human intervention.
        """
        # Create a mock result with unknown recommendation
        result = MagicMock()
        result.recommendation = "unknown"
        
        # Call the method
        action = deepseek_analyzer.decide_action(result)
        
        # Assertions - should default to flag_for_review for safety
        assert action == "flag_for_review"
    
    def test_decide_action_dict_input(self, deepseek_analyzer):
        """
        Test the decide_action method with dictionary input instead of object.
        
        Verifies that the method handles different input types gracefully,
        supporting both object and dictionary structures.
        """
        # Create a dictionary with recommendation
        result = {"recommendation": "standard_response"}
        
        # Call the method
        action = deepseek_analyzer.decide_action(result)
        
        # Assertions
        assert action == "respond"
    
    @patch('src.email_processing.analyzers.deepseek.requests')
    async def test_call_deepseek_api_success(self, mock_requests, deepseek_analyzer, sample_meeting_email):
        """
        Test the _call_deepseek_api method with successful response.
        
        Verifies that the API call method correctly handles successful responses,
        properly extracts content, and returns expected results.
        """
        # Restore the original method for this test
        deepseek_analyzer._call_deepseek_api = DeepseekAnalyzer._call_deepseek_api.__get__(deepseek_analyzer)
        
        # Configure mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "ANALYSIS:\nCompleteness: 4/4 elements\n\nRECOMMENDATION: standard_response"
                    }
                }
            ]
        }
        mock_requests.post.return_value = mock_response
        
        # Call the method
        result = await deepseek_analyzer._call_deepseek_api("Test prompt", "request_id")
        
        # Assertions
        assert "ANALYSIS" in result
        assert "standard_response" in result
        assert mock_requests.post.called
        
        # Verify correct API endpoint and headers were used
        call_args = mock_requests.post.call_args
        assert deepseek_analyzer.api_endpoint in call_args[0][0]
        assert "Authorization" in call_args[1]["headers"]
    
    @patch('src.email_processing.analyzers.deepseek.requests')
    async def test_call_deepseek_api_error(self, mock_requests, deepseek_analyzer, sample_meeting_email):
        """
        Test the _call_deepseek_api method handling API errors.
        
        Verifies that the method properly handles error responses, raises
        appropriate exceptions, and includes detailed error information.
        """
        # Restore the original method for this test
        deepseek_analyzer._call_deepseek_api = DeepseekAnalyzer._call_deepseek_api.__get__(deepseek_analyzer)
        
        # Configure mock to return error status
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_requests.post.return_value = mock_response
        
        # Call the method and expect exception
        with pytest.raises(RuntimeError) as excinfo:
            await deepseek_analyzer._call_deepseek_api("Test prompt", "request_id")
        
        # Assertions
        assert "API returned status code 500" in str(excinfo.value)
        assert "Internal server error" in str(excinfo.value)
    
    @patch('src.email_processing.analyzers.deepseek.requests')
    @patch('src.email_processing.analyzers.deepseek.asyncio.sleep')
    async def test_call_deepseek_api_retry(self, mock_sleep, mock_requests, deepseek_analyzer, sample_meeting_email):
        """
        Test the _call_deepseek_api method retry mechanism.
        
        Verifies that the method properly implements retry logic as specified
        in error-handling.md, with appropriate delays and retry attempts.
        """
        # Restore the original method for this test
        deepseek_analyzer._call_deepseek_api = DeepseekAnalyzer._call_deepseek_api.__get__(deepseek_analyzer)
        
        # Configure mock to fail on first call, succeed on second
        mock_failure = MagicMock()
        mock_failure.status_code = 429
        mock_failure.text = "Rate limited"
        
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "ANALYSIS:\nSuccess after retry\n\nRECOMMENDATION: standard_response"
                    }
                }
            ]
        }
        
        mock_requests.post.side_effect = [mock_failure, mock_success]
        
        # Call the method
        result = await deepseek_analyzer._call_deepseek_api("Test prompt", "request_id")
        
        # Assertions
        assert "Success after retry" in result
        assert mock_requests.post.call_count == 2
        assert mock_sleep.called
        # Verify it used the configured retry delay
        assert mock_sleep.call_args[0][0] == deepseek_analyzer.retry_delay
    
    def test_process_analysis_result_standard(self, deepseek_analyzer):
        """
        Test processing a standard analysis result.
        
        Verifies that the method correctly extracts structured analysis data,
        response text, and recommendation from a well-formed analysis result.
        """
        analysis = """
        ANALYSIS:
        Completeness: 4/4 elements
        Missing elements: None
        Risk factors: None
        Detected tone: Neutral (3)
        
        RESPONSE:
        Thank you for your meeting request. I confirm the meeting.
        
        RECOMMENDATION: standard_response
        """
        
        # Call the method
        analysis_data, response_text, recommendation = deepseek_analyzer._process_analysis_result(analysis, "request_id")
        
        # Assertions
        assert analysis_data["completeness"] == "4/4 elements"
        assert "Missing elements" in analysis_data
        assert response_text == "Thank you for your meeting request. I confirm the meeting."
        assert recommendation == "standard_response"
    
    def test_process_analysis_result_missing_parts(self, deepseek_analyzer):
        """
        Test processing an analysis result with missing sections.
        
        Verifies that the method handles incomplete analysis results gracefully,
        extracting available data while providing suitable defaults for missing parts.
        """
        analysis = """
        ANALYSIS:
        Completeness: 2/4 elements
        Missing elements: time, location
        
        RECOMMENDATION: standard_response
        """
        
        # Call the method
        analysis_data, response_text, recommendation = deepseek_analyzer._process_analysis_result(analysis, "request_id")
        
        # Assertions
        assert analysis_data["completeness"] == "2/4 elements"
        assert analysis_data["missing elements"] == "time, location"
        assert response_text == ""  # Empty response text when section is missing
        assert recommendation == "standard_response"
    
    def test_process_analysis_result_malformed(self, deepseek_analyzer):
        """
        Test processing a malformed analysis result.
        
        Verifies that the method handles malformed inputs gracefully, providing
        reasonable defaults and failing safely rather than crashing.
        """
        analysis = """
        This is not a properly formatted analysis result.
        It's missing the expected sections.
        """
        
        # Call the method
        analysis_data, response_text, recommendation = deepseek_analyzer._process_analysis_result(analysis, "request_id")
        
        # Assertions - should handle malformed input gracefully
        assert analysis_data == {}
        assert response_text == ""
        assert recommendation == "needs_review"  # Default to needs_review for safety
    
    def test_create_analysis_prompt(self, deepseek_analyzer, sample_meeting_email):
        """
        Test creating an analysis prompt with proper structure.
        
        Verifies that the method generates a well-structured prompt with all
        required sections and instructions as specified in analysis-pipeline.md.
        """
        # Call the method
        prompt = deepseek_analyzer._create_analysis_prompt(sample_meeting_email, "request_id")
        
        # Assertions
        assert "TASK:" in prompt
        assert "ANALYSIS REQUIREMENTS:" in prompt
        assert "FORMALITY ADJUSTMENT RULES:" in prompt
        assert "RESPONSE REQUIREMENTS:" in prompt
        assert "OUTPUT FORMAT:" in prompt
        assert sample_meeting_email in prompt
        
        # Check for key instruction elements
        assert "time/date" in prompt
        assert "location" in prompt
        assert "agenda" in prompt
        assert "ONE LEVELS MORE FORMAL" in prompt
        assert "RECOMMENDATION" in prompt
