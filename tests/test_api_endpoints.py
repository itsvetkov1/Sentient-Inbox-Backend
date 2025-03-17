"""
Comprehensive API endpoint tests for the Email Management System.

These tests verify the proper functioning of all API endpoints, including
authentication, email processing, and dashboard functionality. The tests use
FastAPI's TestClient to simulate HTTP requests and validate responses against
expected formats and status codes.

Testing Strategy:
- Verify authentication and authorization flows
- Test email analysis and batch processing endpoints
- Validate dashboard data retrieval
- Confirm proper error responses for invalid requests
- Test rate limiting functionality
"""

import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

# Import API components
from api.main import app
from api.models.emails import EmailAnalysisRequest, EmailAnalysisResponse
from api.models.dashboard import DashboardStats
from api.auth.service import auth_service, get_auth_service

# Create test client
client = TestClient(app)

# Test constants
TEST_USERNAME = "testadmin"
TEST_PASSWORD = "securepassword"
TEST_EMAIL = "test@example.com"


@pytest.fixture
def mock_auth_service():
    """
    Create a mock authentication service for testing.
    
    This fixture patches the get_auth_service dependency to provide a mock
    authentication service that returns predefined tokens and user data.
    """
    # Create mock auth service
    mock_auth = MagicMock()
    
    # Mock authentication method
    async def mock_authenticate(username, password):
        if username == TEST_USERNAME and password == TEST_PASSWORD:
            return {
                "id": "test123",
                "username": TEST_USERNAME,
                "email": TEST_EMAIL,
                "permissions": ["admin", "process", "view"],
                "created_at": datetime.utcnow().isoformat(),
            }
        return None
    
    # Mock token creation
    def mock_create_token(data, expires_delta=None):
        return "mock_access_token_for_testing"
    
    # Mock current user
    async def mock_get_current_user(token=None):
        return {
            "id": "test123",
            "username": TEST_USERNAME,
            "email": TEST_EMAIL,
            "permissions": ["admin", "process", "view"],
            "created_at": datetime.utcnow().isoformat(),
        }
    
    # Set up mock methods
    mock_auth.authenticate_user = AsyncMock(side_effect=mock_authenticate)
    mock_auth.create_access_token = mock_create_token
    mock_auth.get_current_user = AsyncMock(side_effect=mock_get_current_user)
    
    # Patch the auth service dependency
    with patch("api.auth.service.get_auth_service", return_value=mock_auth):
        with patch("api.main.get_auth_service", return_value=mock_auth):
            yield mock_auth


@pytest.fixture
def mock_email_service():
    """
    Create a mock email service for testing.
    
    This fixture patches the email_service dependency to provide mock implementations
    of email analysis, batch processing, and statistics retrieval.
    """
    # Create mock email service
    mock_service = MagicMock()
    
    # Mock email analysis
    async def mock_analyze_email(content, subject, sender):
        return EmailAnalysisResponse(
            is_meeting_related=True,
            category="meeting",
            recommended_action="respond",
            meeting_details={
                "date": "tomorrow",
                "time": "2pm",
                "location": "Conference Room A",
                "agenda": "Project discussion",
                "missing_elements": []
            },
            suggested_response="I confirm our meeting tomorrow at 2pm.",
            metadata={
                "analyzed_at": datetime.utcnow(),
                "model_version": "1.0.0",
                "confidence_score": 0.95,
                "processing_time_ms": 250
            }
        )
    
    # Mock batch processing
    async def mock_process_batch(batch_size):
        return batch_size - 1, 1, ["Error processing email: test_error"]
    
    # Mock get emails
    async def mock_get_emails(limit, offset, category):
        return [], 0
    
    # Set up mock methods
    mock_service.analyze_email = AsyncMock(side_effect=mock_analyze_email)
    mock_service.process_batch = AsyncMock(side_effect=mock_process_batch)
    mock_service.get_emails = AsyncMock(side_effect=mock_get_emails)
    mock_service.get_current_timestamp = MagicMock(return_value=datetime.utcnow().isoformat())
    
    # Patch the email service
    with patch("api.routes.emails.get_email_service", return_value=mock_service):
        with patch("api.main.get_email_service", return_value=mock_service):
            yield mock_service


@pytest.fixture
def mock_dashboard_service():
    """
    Create a mock dashboard service for testing.
    
    This fixture patches the dashboard_service dependency to provide mock implementations
    of dashboard data retrieval methods.
    """
    # Create mock dashboard service
    mock_service = MagicMock()
    
    # Mock dashboard stats
    async def mock_get_dashboard_stats(period):
        return DashboardStats(
            total_emails=100,
            meeting_emails=70,
            response_rate=85.5,
            avg_processing_time=245.3,
            success_rate=95.2,
            volume_trend=[],
            category_distribution=[],
            performance_metrics=[],
            agent_metrics=[],
            last_updated=datetime.utcnow()
        )
    
    # Set up mock methods
    mock_service.get_dashboard_stats = AsyncMock(side_effect=mock_get_dashboard_stats)
    mock_service.get_dashboard_summary = AsyncMock(return_value={
        "stats": await mock_get_dashboard_stats("day"),
        "user_activity": {"total_users": 5, "active_users": 3},
        "email_accounts": [],
        "period": "day"
    })
    
    # Patch the dashboard service
    with patch("api.routes.dashboard.get_dashboard_service", return_value=mock_service):
        yield mock_service


@pytest.fixture
def auth_headers(mock_auth_service):
    """
    Generate authentication headers with a valid token.
    
    Returns:
        Dict containing authorization header with bearer token
    """
    return {"Authorization": f"Bearer mock_access_token_for_testing"}


class TestAuthEndpoints:
    """
    Test authentication-related API endpoints.
    
    Verifies login functionality, token generation, and user information retrieval
    with proper validation of authentication responses.
    """
    
    def test_login_success(self, mock_auth_service):
        """Test successful login with valid credentials."""
        response = client.post(
            "/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["token"]["access_token"] == "mock_access_token_for_testing"
        assert data["token"]["token_type"] == "bearer"
        assert data["username"] == TEST_USERNAME
        assert "permissions" in data
        assert "admin" in data["permissions"]
    
    def test_login_invalid_credentials(self, mock_auth_service):
        """Test login failure with invalid credentials."""
        # Mock auth service to return None for invalid credentials
        mock_auth_service.authenticate_user.return_value = AsyncMock(return_value=None)
        
        response = client.post(
            "/login",
            json={"username": "invalid", "password": "invalid"}
        )
        
        # Verify response
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Incorrect username or password" in data["detail"]
    
    def test_get_current_user(self, mock_auth_service, auth_headers):
        """Test retrieval of current user information."""
        response = client.get("/me", headers=auth_headers)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == TEST_USERNAME
        assert data["email"] == TEST_EMAIL
        assert "admin" in data["permissions"]


class TestEmailEndpoints:
    """
    Test email processing API endpoints.
    
    Verifies email analysis, batch processing, and email listing functionality
    with proper validation of request parameters and response formats.
    """
    
    def test_analyze_email(self, mock_email_service, auth_headers):
        """Test email analysis endpoint with valid request."""
        response = client.post(
            "/emails/analyze",
            headers=auth_headers,
            json={
                "content": "Let's meet tomorrow at 2pm to discuss the project.",
                "subject": "Meeting Request",
                "sender": "test@example.com"
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["is_meeting_related"] is True
        assert data["category"] == "meeting"
        assert data["recommended_action"] == "respond"
        assert "meeting_details" in data
        assert "suggested_response" in data
        assert "metadata" in data
    
    def test_analyze_email_unauthorized(self, mock_email_service):
        """Test email analysis endpoint without authentication."""
        response = client.post(
            "/emails/analyze",
            json={
                "content": "Let's meet tomorrow at 2pm to discuss the project.",
                "subject": "Meeting Request",
                "sender": "test@example.com"
            }
        )
        
        # Verify response
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Not authenticated" in data["detail"]
    
    def test_process_batch(self, mock_email_service, auth_headers):
        """Test batch processing endpoint with valid request."""
        response = client.post(
            "/emails/process-batch?batch_size=20",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 19  # batch_size - 1 from mock
        assert data["errors"] == 1
        assert "success_rate" in data
        assert "timestamp" in data
    
    def test_get_emails(self, mock_email_service, auth_headers):
        """Test email listing endpoint with pagination."""
        response = client.get(
            "/emails/?limit=10&offset=0",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "emails" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data


class TestDashboardEndpoints:
    """
    Test dashboard API endpoints.
    
    Verifies dashboard statistics, user activity, and summary data retrieval
    with proper validation of response formats and authorization requirements.
    """
    
    def test_get_dashboard_stats(self, mock_dashboard_service, auth_headers):
        """Test dashboard statistics endpoint with valid request."""
        response = client.get(
            "/dashboard/stats?period=day",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "total_emails" in data
        assert "meeting_emails" in data
        assert "response_rate" in data
        assert "avg_processing_time" in data
        assert "success_rate" in data
        assert "last_updated" in data
    
    def test_get_dashboard_summary(self, mock_dashboard_service, auth_headers):
        """Test dashboard summary endpoint with valid request."""
        response = client.get(
            "/dashboard/summary?period=week",
            headers=auth_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "user_activity" in data
        assert "email_accounts" in data
        assert "period" in data
    
    def test_dashboard_unauthorized(self, mock_dashboard_service):
        """Test dashboard endpoint without authentication."""
        response = client.get("/dashboard/stats")
        
        # Verify response
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Not authenticated" in data["detail"]


class TestRateLimiting:
    """
    Test rate limiting middleware functionality.
    
    Verifies that the rate limiting middleware correctly throttles requests
    and provides appropriate headers and responses when limits are exceeded.
    """
    
    @patch("api.middleware.rate_limiter.RateLimiter._get_client_identifier")
    def test_rate_limit_headers(self, mock_get_client, auth_headers):
        """Test rate limit headers are included in responses."""
        # Force client ID to be consistent for testing
        mock_get_client.return_value = "test_client"
        
        response = client.get("/health", headers=auth_headers)
        
        # Verify rate limit headers
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
    
    @patch("api.middleware.rate_limiter.RateLimiter._get_client_identifier")
    @patch("api.middleware.rate_limiter.RateLimiter.max_requests", 3)  # Override for testing
    def test_rate_limit_exceeded(self, mock_get_client, auth_headers):
        """Test rate limiting when exceeding the request limit."""
        # Force client ID to be consistent for testing
        mock_get_client.return_value = "test_client"
        
        # Make requests until limit is exceeded
        for _ in range(3):
            response = client.get("/health", headers=auth_headers)
            assert response.status_code == 200
        
        # This request should be rate limited
        response = client.get("/health", headers=auth_headers)
        
        # Verify rate limit response
        assert response.status_code == 429
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in response.headers


class TestErrorHandling:
    """
    Test API error handling functionality.
    
    Verifies that the API returns properly formatted error responses
    with appropriate status codes and error details.
    """
    
    def test_validation_error(self, auth_headers):
        """Test validation error response for invalid request data."""
        # Missing required fields
        response = client.post(
            "/emails/analyze",
            headers=auth_headers,
            json={"content": "Hello"}  # Missing subject and sender
        )
        
        # Verify validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["status"] == "error"
        assert "error_code" in data
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "validation_errors" in data
    
    def test_not_found_error(self, auth_headers):
        """Test 404 error response for non-existent endpoint."""
        response = client.get("/non_existent_endpoint", headers=auth_headers)
        
        # Verify not found error response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Not Found" in data["detail"]
    
    @patch("api.routes.emails.get_email_service")
    def test_internal_server_error(self, mock_get_service, auth_headers):
        """Test 500 error response for internal server errors."""
        # Mock service to raise exception
        mock_service = AsyncMock()
        mock_service.analyze_email = AsyncMock(side_effect=Exception("Test internal error"))
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/emails/analyze",
            headers=auth_headers,
            json={
                "content": "Hello",
                "subject": "Test",
                "sender": "test@example.com"
            }
        )
        
        # Verify internal error response
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "INTERNAL_SERVER_ERROR"
        assert "timestamp" in data


if __name__ == "__main__":
    pytest.main(["-xvs", "test_api_endpoints.py"])
"""
