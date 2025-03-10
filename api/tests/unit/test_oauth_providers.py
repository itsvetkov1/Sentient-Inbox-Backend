# auth_tests/test_oauth_providers.py

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import aiohttp
import os

from src.auth.oauth_base import OAuthProvider
from src.auth.google_oauth import GoogleOAuthProvider
from src.auth.microsoft_oauth import MicrosoftOAuthProvider
from src.auth.oauth_factory import OAuthProviderFactory


@pytest.fixture
def setup_oauth_environment():
    """Setup environment variables for OAuth testing."""
    # Store original environment variables
    original_env = {
        "GOOGLE_CLIENT_ID": os.environ.get("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "MICROSOFT_CLIENT_ID": os.environ.get("MICROSOFT_CLIENT_ID"),
        "MICROSOFT_CLIENT_SECRET": os.environ.get("MICROSOFT_CLIENT_SECRET"),
    }
    
    # Set test environment variables
    os.environ["GOOGLE_CLIENT_ID"] = "google_test_client_id"
    os.environ["GOOGLE_CLIENT_SECRET"] = "google_test_client_secret"
    os.environ["MICROSOFT_CLIENT_ID"] = "microsoft_test_client_id"
    os.environ["MICROSOFT_CLIENT_SECRET"] = "microsoft_test_client_secret"
    
    yield
    
    # Restore original environment variables
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


@pytest.fixture
def mock_http_client():
    """Mock aiohttp ClientSession for testing OAuth HTTP requests."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock()
    
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.get = AsyncMock(return_value=mock_response)
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        yield {
            "session": mock_session,
            "response": mock_response
        }


class TestGoogleOAuthProvider:
    """Test Google OAuth provider implementation."""
    
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_oauth_environment")
    async def test_provider_initialization(self):
        """Test provider initialization with environment variables."""
        provider = GoogleOAuthProvider()
        
        assert provider.provider_name == "google"
        assert provider.client_id == "google_test_client_id"
        assert provider.client_secret == "google_test_client_secret"
        assert "https://www.googleapis.com/auth/gmail.readonly" in provider.default_scopes
    
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_oauth_environment")
    async def test_get_authorization_url(self):
        """Test generating authorization URL."""
        provider = GoogleOAuthProvider()
        redirect_uri = "http://localhost:8000/callback"
        
        url, state = await provider.get_authorization_url(redirect_uri)
        
        assert "accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=google_test_client_id" in url
        assert f"redirect_uri={redirect_uri}" in url
        assert "response_type=code" in url
        assert "scope=" in url
        assert state is not None
    
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_oauth_environment")
    async def test_exchange_code_for_tokens(self, mock_http_client):
        """Test exchanging authorization code for tokens."""
        provider = GoogleOAuthProvider()
        redirect_uri = "http://localhost:8000/callback"
        code = "test_authorization_code"
        
        # Mock token response
        mock_http_client["response"].json.return_value = {
            "access_token": "google_access_token",
            "refresh_token": "google_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "email profile https://www.googleapis.com/auth/gmail.readonly"
        }
        
        # Mock userinfo response
        mock_userinfo_response = MagicMock()
        mock_userinfo_response.status = 200
        mock_userinfo_response.json = AsyncMock(return_value={
            "sub": "google_user_123",
            "name": "Google Test User",
            "email": "google_user@example.com",
            "picture": "https://example.com/profile.jpg"
        })
        
        # Setup get method to return different responses based on URL
        async def mock_get(url, **kwargs):
            if "userinfo" in url:
                return mock_userinfo_response
            return mock_http_client["response"]
        
        mock_http_client["session"].get = AsyncMock(side_effect=mock_get)
        
        tokens = await provider.exchange_code_for_tokens(code, redirect_uri)
        
        # Check token API call
        mock_http_client["session"].post.assert_called_once()
        args, kwargs = mock_http_client["session"].post.call_args
        assert provider.TOKEN_URL in args
        assert "data" in kwargs
        assert kwargs["data"]["client_id"] == "google_test_client_id"
        assert kwargs["data"]["client_secret"] == "google_test_client_secret"
        assert kwargs["data"]["code"] == code
        assert kwargs["data"]["redirect_uri"] == redirect_uri
        assert kwargs["data"]["grant_type"] == "authorization_code"
        
        # Check userinfo API call
        mock_http_client["session"].get.assert_called_once()
        args, kwargs = mock_http_client["session"].get.call_args
        assert provider.USERINFO_URL in args
        assert "headers" in kwargs
        assert "Authorization" in kwargs["headers"]
        assert "Bearer google_access_token" in kwargs["headers"]["Authorization"]
        
        # Check result
        assert tokens["access_token"] == "google_access_token"
        assert tokens["refresh_token"] == "google_refresh_token"
        assert tokens["expires_in"] == 3600
        assert tokens["provider_user_id"] == "google_user_123"
        assert tokens["provider_email"] == "google_user@example.com"
        assert "profile" in tokens["scopes"]
        assert "email" in tokens["scopes"]
        assert tokens["user_info"]["name"] == "Google Test User"
    
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_oauth_environment")
    async def test_refresh_access_token(self, mock_http_client):
        """Test refreshing access token."""
        provider = GoogleOAuthProvider()
        refresh_token = "google_refresh_token"
        
        # Mock token response
        mock_http_client["response"].json.return_value = {
            "access_token": "new_google_access_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "email profile https://www.googleapis.com/auth/gmail.readonly"
        }
        
        tokens = await provider.refresh_access_token(refresh_token)
        
        # Check token API call
        mock_http_client["session"].post.assert_called_once()
        args, kwargs = mock_http_client["session"].post.call_args
        assert provider.TOKEN_URL in args
        assert "data" in kwargs
        assert kwargs["data"]["client_id"] == "google_test_client_id"
        assert kwargs["data"]["client_secret"] == "google_test_client_secret"
        assert kwargs["data"]["refresh_token"] == refresh_token
        assert kwargs["data"]["grant_type"] == "refresh_token"
        
        # Check result
        assert tokens["access_token"] == "new_google_access_token"
        assert tokens["expires_in"] == 3600
        assert "profile" in tokens["scope"]
        assert "email" in tokens["scope"]
    
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_oauth_environment")
    async def test_validate_token(self, mock_http_client):
        """Test token validation."""
        provider = GoogleOAuthProvider()
        access_token = "google_access_token"
        
        # Mock tokeninfo response
        mock_http_client["response"].json.return_value = {
            "aud": "google_test_client_id",
            "exp": 1643276830,
            "scope": "email profile https://www.googleapis.com/auth/gmail.readonly"
        }
        
        is_valid = await provider.validate_token(access_token)
        
        # Check tokeninfo API call
        mock_http_client["session"].get.assert_called_once()
        args, kwargs = mock_http_client["session"].get.call_args
        assert provider.TOKENINFO_URL in args[0]
        assert f"access_token={access_token}" in args[0]
        
        # Check result
        assert is_valid is True
    
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_oauth_environment")
    async def test_revoke_token(self, mock_http_client):
        """Test token revocation."""
        provider = GoogleOAuthProvider()
        access_token = "google_access_token"
        
        success = await provider.revoke_token(access_token)
        
        # Check revoke API call
        mock_http_client["session"].post.assert_called_once()
        args, kwargs = mock_http_client["session"].post.call_args
        assert provider.REVOKE_URL in args
        assert "data" in kwargs
        assert kwargs["data"]["token"] == access_token
        assert kwargs["data"]["token_type_hint"] == "access_token"
        
        # Check result
        assert success is True


class TestMicrosoftOAuthProvider:
    """Test Microsoft OAuth provider implementation."""
    
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_oauth_environment")
    async def test_provider_initialization(self):
        """Test provider initialization with environment variables."""
        provider = MicrosoftOAuthProvider()
        
        assert provider.provider_name == "microsoft"
        assert provider.client_id == "microsoft_test_client_id"
        assert provider.client_secret == "microsoft_test_client_secret"
        assert "Mail.Read" in provider.default_scopes
    
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_oauth_environment")
    async def test_get_authorization_url(self):
        """Test generating authorization URL."""
        provider = MicrosoftOAuthProvider()
        redirect_uri = "http://localhost:8000/callback"
        
        url, state = await provider.get_authorization_url(redirect_uri)
        
        assert "login.microsoftonline.com/common/oauth2/v2.0/authorize" in url
        assert "client_id=microsoft_test_client_id" in url
        assert f"redirect_uri={redirect_uri}" in url
        assert "response_type=code" in url
        assert "scope=" in url
        assert state is not None

    # Additional Microsoft provider tests similar to Google provider
    # (exchange_code_for_tokens, refresh_access_token, validate_token, revoke_token)
    # Implementaton is similar but with Microsoft-specific endpoints and parameters


class TestOAuthFactory:
    """Test OAuth provider factory implementation."""
    
    @pytest.mark.usefixtures("setup_oauth_environment")
    def test_get_available_providers(self):
        """Test getting available OAuth providers."""
        providers = OAuthProviderFactory.get_available_providers()
        
        assert "google" in providers
        assert "microsoft" in providers
        assert providers["google"] == "Google"
        assert providers["microsoft"] == "Microsoft / Outlook"
    
    @pytest.mark.usefixtures("setup_oauth_environment")
    def test_get_provider(self):
        """Test getting provider by name."""
        google_provider = OAuthProviderFactory.get_provider("google")
        microsoft_provider = OAuthProviderFactory.get_provider("microsoft")
        
        assert isinstance(google_provider, GoogleOAuthProvider)
        assert isinstance(microsoft_provider, MicrosoftOAuthProvider)
    
    @pytest.mark.usefixtures("setup_oauth_environment")
    def test_get_invalid_provider(self):
        """Test handling invalid provider name."""
        with pytest.raises(ValueError):
            OAuthProviderFactory.get_provider("invalid_provider")
    
    @pytest.mark.usefixtures("setup_oauth_environment")
    def test_register_provider(self):
        """Test registering custom provider."""
        # Create a mock provider class
        class MockOAuthProvider(OAuthProvider):
            @property
            def provider_name(self):
                return "mock"
                
            async def get_authorization_url(self, redirect_uri, state=None):
                return "https://mock.auth/url", "mock_state"
                
            async def exchange_code_for_tokens(self, code, redirect_uri):
                return {"access_token": "mock_token"}
                
            async def refresh_access_token(self, refresh_token):
                return {"access_token": "new_mock_token"}
                
            async def get_user_info(self, access_token):
                return {"id": "mock_user", "email": "mock@example.com"}
                
            async def validate_token(self, access_token):
                return True
                
            async def revoke_token(self, token, token_type_hint="access_token"):
                return True
        
        # Register the mock provider
        OAuthProviderFactory.register_provider("mock", MockOAuthProvider)
        
        # Get the registered provider
        mock_provider = OAuthProviderFactory.get_provider("mock")
        
        assert isinstance(mock_provider, MockOAuthProvider)
        assert mock_provider.provider_name == "mock"
        
        # Check updated available providers
        providers = OAuthProviderFactory.get_available_providers()
        assert "mock" in providers