"""
EmailAgent Unit Tests

This module provides comprehensive test coverage for the EmailAgent component,
which handles response delivery and email status management in the final stage
of the email processing pipeline.
"""

import pytest
import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock, mock_open, call
from typing import Dict, Any, Optional, Tuple

# Import test infrastructure
from tests.test_infrastructure import (
    create_test_email, mock_gmail_client, test_config
)

# Import component under test
from src.email_processing.handlers.writer import EmailAgent
from src.email_processing.models import EmailMetadata, EmailTopic


class TestEmailAgent:
    """Test suite for the EmailAgent component."""

    @pytest.fixture
    def setup_agent(self, mock_gmail_client):
        """Create a properly configured EmailAgent for testing."""
        # Create a temp response log file
        temp_log = {"responses": []}
        
        # Patch open to avoid file operations
        with patch("builtins.open", mock_open(read_data=json.dumps(temp_log))), \
             patch("os.path.exists", return_value=True), \
             patch("json.dump") as mock_json_dump:
            
            # Create agent with mocked Gmail client
            agent = EmailAgent()
            agent.gmail = mock_gmail_client
            agent.response_log = temp_log
            
            yield agent, mock_json_dump

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test proper initialization of EmailAgent."""
        # Patch file operations
        with patch("builtins.open", mock_open(read_data="{}")), \
             patch("os.path.exists", return_value=True), \
             patch("os.makedirs"):
            
            # Initialize agent
            agent = EmailAgent()
            
            # Assert
            assert agent.client is not None
            assert agent.gmail is not None
            assert agent.groq_client is not None
            assert hasattr(agent, "response_log")

    @pytest.mark.asyncio
    async def test_load_response_log_existing(self):
        """Test loading of existing response log."""
        # Create test log data
        test_log = {
            "responses": [
                {
                    "email_id": "test123",
                    "response_time": datetime.now().isoformat(),
                    "response_data": {"subject": "Test", "response": "Test response"}
                }
            ]
        }
        
        # Patch file operations
        with patch("builtins.open", mock_open(read_data=json.dumps(test_log))), \
             patch("os.path.exists", return_value=True), \
             patch("os.makedirs"):
            
            # Initialize agent to trigger load_response_log
            agent = EmailAgent()
            
            # Assert
            assert isinstance(agent.response_log, dict)
            assert "responses" in agent.response_log
            assert len(agent.response_log["responses"]) == 1
            assert agent.response_log["responses"][0]["email_id"] == "test123"

    @pytest.mark.asyncio
    async def test_load_response_log_new(self):
        """Test creation of new response log when none exists."""
        # Patch file operations to simulate missing file
        with patch("builtins.open", side_effect=[FileNotFoundError, mock_open().return_value]), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("json.dump") as mock_json_dump:
            
            # Initialize agent to trigger load_response_log
            agent = EmailAgent()
            
            # Assert
            assert isinstance(agent.response_log, dict)
            assert "responses" in agent.response_log
            assert len(agent.response_log["responses"]) == 0
            assert mock_json_dump.called  # Should save new empty log

    @pytest.mark.asyncio
    async def test_save_response_log(self, setup_agent):
        """Test saving of response log."""
        # Setup
        agent, mock_json_dump = setup_agent
        
        # Execute
        agent.save_response_log("test456", {"subject": "New Test", "response": "New response"})
        
        # Assert
        assert len(agent.response_log["responses"]) == 1
        assert agent.response_log["responses"][0]["email_id"] == "test456"
        assert mock_json_dump.called  # Should save updated log

    @pytest.mark.asyncio
    async def test_has_responded(self, setup_agent):
        """Test checking if email has already been responded to."""
        # Setup
        agent, _ = setup_agent
        
        # Add a test response
        agent.response_log["responses"].append({
            "email_id": "responded123",
            "response_time": datetime.now().isoformat(),
            "response_data": {"subject": "Test", "response": "Test response"}
        })
        
        # Execute and assert
        assert agent.has_responded("responded123") is True
        assert agent.has_responded("not_responded456") is False

    @pytest.mark.asyncio
    @patch("src.email_processing.handlers.writer.EmailAgent.verify_meeting_parameters_ai")
    async def test_create_response_with_template(self, mock_verify, setup_agent):
        """Test response creation with provided template."""
        # Setup
        agent, _ = setup_agent
        
        # Create metadata with template
        metadata = EmailMetadata(
            message_id="test789",
            subject="Meeting Request",
            sender="sender@example.com",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Let's meet tomorrow at 2pm",
            analysis_data={
                "response_template": "Dear Sender,\n\nI confirm our meeting tomorrow at 2pm.\n\nBest regards,\nAssistant"
            }
        )
        
        # Execute
        response = await agent.create_response(metadata)
        
        # Assert
        assert response is not None
        assert "confirm our meeting" in response
        assert "2pm" in response
        
        # Should not call parameter verification when template exists
        assert not mock_verify.called

    @pytest.mark.asyncio
    async def test_create_response_missing_parameters(self, setup_agent):
        """Test response creation for emails with missing parameters."""
        # Setup
        agent, _ = setup_agent
        
        # Mock parameter verification
        mock_analysis = {
            "parameters": {
                "date": {"found": True, "value": "tomorrow", "confidence": 0.9},
                "time": {"found": True, "value": "2pm", "confidence": 0.9},
                "location": {"found": False, "value": None, "confidence": 0.0},
                "agenda": {"found": True, "value": "project discussion", "confidence": 0.8}
            },
            "missing_parameters": ["location"],
            "has_all_required": False,
            "overall_confidence": 0.6
        }
        
        agent.verify_meeting_parameters_ai = AsyncMock(return_value=(mock_analysis, True))
        
        # Create metadata without template
        metadata = EmailMetadata(
            message_id="test_missing_params",
            subject="Meeting Request",
            sender="John Smith <sender@example.com>",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Let's meet tomorrow at 2pm to discuss the project."
        )
        
        # Execute
        response = await agent.create_response(metadata)
        
        # Assert
        assert response is not None
        assert "location" in response.lower()  # Should request missing location
        assert "John" in response  # Should extract name from sender

    @pytest.mark.asyncio
    async def test_create_response_complete_parameters(self, setup_agent):
        """Test response creation for emails with complete parameters."""
        # Setup
        agent, _ = setup_agent
        
        # Mock parameter verification
        mock_analysis = {
            "parameters": {
                "date": {"found": True, "value": "tomorrow", "confidence": 0.9},
                "time": {"found": True, "value": "2pm", "confidence": 0.9},
                "location": {"found": True, "value": "Conference Room A", "confidence": 0.9},
                "agenda": {"found": True, "value": "project discussion", "confidence": 0.8}
            },
            "missing_parameters": [],
            "has_all_required": True,
            "overall_confidence": 0.9
        }
        
        agent.verify_meeting_parameters_ai = AsyncMock(return_value=(mock_analysis, True))
        
        # Create metadata without template
        metadata = EmailMetadata(
            message_id="test_complete_params",
            subject="Meeting Request",
            sender="Jane Doe <sender@example.com>",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Let's meet tomorrow at 2pm in Conference Room A to discuss the project."
        )
        
        # Execute
        response = await agent.create_response(metadata)
        
        # Assert
        assert response is not None
        assert "confirm" in response.lower()  # Should confirm meeting
        assert "tomorrow" in response
        assert "2pm" in response
        assert "Conference Room A" in response
        assert "Jane" in response  # Should extract name from sender

    @pytest.mark.asyncio
    async def test_create_response_low_confidence(self, setup_agent):
        """Test response creation for emails with parameters detected with low confidence."""
        # Setup
        agent, _ = setup_agent
        
        # Mock parameter verification with low confidence
        mock_analysis = {
            "parameters": {
                "date": {"found": True, "value": "tomorrow", "confidence": 0.5},
                "time": {"found": True, "value": "afternoon", "confidence": 0.4},
                "location": {"found": True, "value": "office", "confidence": 0.6},
                "agenda": {"found": True, "value": "project discussion", "confidence": 0.8}
            },
            "missing_parameters": [],
            "has_all_required": True,
            "overall_confidence": 0.5  # Low overall confidence
        }
        
        agent.verify_meeting_parameters_ai = AsyncMock(return_value=(mock_analysis, True))
        
        # Create metadata without template
        metadata = EmailMetadata(
            message_id="test_low_confidence",
            subject="Meeting Request",
            sender="sender@example.com",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Let's meet soon to discuss the project."
        )
        
        # Execute
        response = await agent.create_response(metadata)
        
        # Assert
        assert response is not None
        assert "confirm" not in response.lower()  # Should not confirm with low confidence
        assert "afternoon" in response  # Should reference uncertain parameter
        assert "please confirm" in response.lower()  # Should ask for confirmation

    @pytest.mark.asyncio
    async def test_extract_meeting_info_fallback(self, setup_agent):
        """Test extraction of meeting info using pattern matching fallback."""
        # Setup
        agent, _ = setup_agent
        
        # Test email content
        content = "Let's meet tomorrow at 3pm in the conference room to discuss the project roadmap."
        
        # Execute
        info = agent.extract_meeting_info(content)
        
        # Assert
        assert info is not None
        assert "location" in info
        assert info["location"] is not None
        assert "conference room" in info["location"].lower()
        
        assert "agenda" in info
        assert info["agenda"] is not None
        assert "project roadmap" in info["agenda"].lower()

    @pytest.mark.asyncio
    async def test_verify_meeting_parameters_ai(self, setup_agent):
        """Test AI-based verification of meeting parameters."""
        # Setup
        agent, _ = setup_agent
        
        # Mock groq client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "parameters": {
                "date": {"found": True, "value": "tomorrow", "confidence": 0.9},
                "time": {"found": True, "value": "2pm", "confidence": 0.9},
                "location": {"found": True, "value": "Conference Room A", "confidence": 0.9},
                "agenda": {"found": True, "value": "project discussion", "confidence": 0.8}
            },
            "missing_parameters": [],
            "has_all_required": True,
            "overall_confidence": 0.9
        })
        
        agent.groq_client.process_with_retry = AsyncMock(return_value=mock_response)
        
        # Test email content
        content = "Let's meet tomorrow at 2pm in Conference Room A to discuss the project."
        subject = "Meeting Request"
        
        # Execute
        result, success = await agent.verify_meeting_parameters_ai(content, subject)
        
        # Assert
        assert success is True
        assert result is not None
        assert "parameters" in result
        assert result["has_all_required"] is True
        assert result["parameters"]["date"]["value"] == "tomorrow"
        assert result["parameters"]["time"]["value"] == "2pm"
        assert result["parameters"]["location"]["value"] == "Conference Room A"
        
        # Verify API call
        assert agent.groq_client.process_with_retry.called
        args, kwargs = agent.groq_client.process_with_retry.call_args
        assert "messages" in kwargs
        assert content in str(kwargs["messages"])
        assert subject in str(kwargs["messages"])

    @pytest.mark.asyncio
    async def test_verify_meeting_parameters_ai_error(self, setup_agent):
        """Test error handling in AI-based parameter verification."""
        # Setup
        agent, _ = setup_agent
        
        # Mock groq client to raise exception
        agent.groq_client.process_with_retry = AsyncMock(side_effect=Exception("API error"))
        
        # Test email content
        content = "Let's meet tomorrow at 2pm."
        subject = "Meeting Request"
        
        # Execute
        result, success = await agent.verify_meeting_parameters_ai(content, subject)
        
        # Assert
        assert success is False
        assert result is not None
        
        # Should fall back to pattern matching
        assert result["has_all_required"] is False
        assert "missing_parameters" in result
        assert "parameters" in result

    @pytest.mark.asyncio
    async def test_fallback_parameter_check(self, setup_agent):
        """Test pattern-based fallback for parameter checking."""
        # Setup
        agent, _ = setup_agent
        
        # Test cases
        test_cases = [
            (
                "Let's meet in the conference room to discuss the project.",
                {"location": True, "agenda": True}
            ),
            (
                "Please review the quarterly report.",
                {"location": False, "agenda": False}
            ),
            (
                "The meeting will be about product strategy.",
                {"location": False, "agenda": True}
            )
        ]
        
        # Execute and assert
        for content, expected in test_cases:
            result = agent._fallback_parameter_check(content)
            
            assert "parameters" in result
            assert "location" in result["parameters"]
            assert "agenda" in result["parameters"]
            
            assert result["parameters"]["location"]["found"] == expected["location"]
            assert result["parameters"]["agenda"]["found"] == expected["agenda"]
            
            # Always missing date and time in the fallback
            assert "date" in result["missing_parameters"]
            assert "time" in result["missing_parameters"]

    @pytest.mark.asyncio
    async def test_send_email(self, setup_agent):
        """Test email sending functionality."""
        # Setup
        agent, _ = setup_agent
        
        # Execute
        success = agent.send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            message_text="Test message content"
        )
        
        # Assert
        assert success is True
        assert agent.gmail.send_email.called
        
        # Verify call parameters
        args, kwargs = agent.gmail.send_email.call_args
        assert args[0] == "recipient@example.com"
        assert args[1] == "Test Subject"
        assert args[2] == "Test message content"

    @pytest.mark.asyncio
    async def test_process_email_with_template(self, setup_agent):
        """Test complete email processing with template."""
        # Setup
        agent, _ = setup_agent
        
        # Create metadata with template
        metadata = EmailMetadata(
            message_id="process_test_template",
            subject="Meeting Request",
            sender="sender@example.com",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Test content",
            analysis_data={
                "response_template": "Dear Sender,\n\nI confirm our meeting.\n\nBest regards,\nAssistant"
            }
        )
        
        # Mock has_responded to return False (new email)
        agent.has_responded = MagicMock(return_value=False)
        
        # Execute
        success = await agent.process_email(metadata)
        
        # Assert
        assert success is True
        assert agent.gmail.send_email.called
        assert agent.has_responded.called

    @pytest.mark.asyncio
    async def test_process_email_already_responded(self, setup_agent):
        """Test email processing for already responded emails."""
        # Setup
        agent, _ = setup_agent
        
        # Create metadata
        metadata = EmailMetadata(
            message_id="already_responded_test",
            subject="Meeting Request",
            sender="sender@example.com",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Test content"
        )
        
        # Mock has_responded to return True (already responded)
        agent.has_responded = MagicMock(return_value=True)
        
        # Execute
        success = await agent.process_email(metadata)
        
        # Assert
        assert success is True
        assert not agent.gmail.send_email.called  # Should not send again
        assert agent.has_responded.called

    @pytest.mark.asyncio
    async def test_process_email_error(self, setup_agent):
        """Test error handling during email processing."""
        # Setup
        agent, _ = setup_agent
        
        # Create metadata
        metadata = EmailMetadata(
            message_id="error_test",
            subject="Meeting Request",
            sender="sender@example.com",
            received_at=datetime.now(),
            topic=EmailTopic.MEETING,
            requires_response=True,
            raw_content="Test content"
        )
        
        # Mock has_responded to return False (new email)
        agent.has_responded = MagicMock(return_value=False)
        
        # Mock create_response to raise exception
        agent.create_response = AsyncMock(side_effect=Exception("Response creation error"))
        
        # Execute
        success = await agent.process_email(metadata)
        
        # Assert
        assert success is False  # Should fail gracefully
        assert not agent.gmail.send_email.called  # Should not attempt to send
