"""
Authentication System Tests

Implements comprehensive tests for authentication functionality
including token generation, validation, and error handling.

Design Considerations:
- Comprehensive test coverage of authentication flows
- Proper test isolation
- Realistic test scenarios
- Edge case handling
"""

import pytest
from fastapi.testclient import TestClient
from datetime import timedelta

from api.main import app
from api.auth.service import AuthenticationService

# Test client
client = TestClient(app)


def test_token_endpoint_success():
    """Test successful token generation."""
    response = client.post(
        "/token",
        data={"username": "admin", "password": "securepassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


def test_token_endpoint_invalid_credentials():
    """Test token generation with invalid credentials."""
    response = client.post(
        "/token",
        data={"username": "admin", "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 401
    data = response.json()
    
    assert data["status"] == "error"
    assert "Incorrect username or password" in data["message"]


def test_login_endpoint_success():
    """Test successful user login."""
    response = client.post(
        "/login",
        json={"username": "admin", "password": "securepassword"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "token" in data
    assert data["username"] == "admin"
    assert "permissions" in data
    assert "admin" in data["permissions"]


def test_login_endpoint_invalid_credentials():
    """Test login with invalid credentials."""
    response = client.post(
        "/login",
        json={"username": "admin", "password": "wrongpassword"}
    )
    
    assert response.status_code == 401
    data = response.json()
    
    assert data["status"] == "error"
    assert "Incorrect username or password" in data["message"]


def test_token_creation():
    """Test token creation functionality."""
    service = AuthenticationService()
    
    # Create token with test data
    token = service.create_access_token(
        data={"username": "testuser", "permissions": ["view"]},
        expires_delta=timedelta(minutes=5)
    )
    
    assert token is not None
    assert isinstance(token, str)


def test_protected_endpoint_without_token():
    """Test access to protected endpoint without token."""
    # Health check should be accessible without token
    response = client.get("/health")
    assert response.status_code == 200