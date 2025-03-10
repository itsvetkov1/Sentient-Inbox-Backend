# auth_tests/test_authentication_flow.py

import pytest
import asyncio
import json
import os
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from jose import jwt

from api.main import app
from api.auth.service import AuthenticationService
from api.models.auth import Token, UserLoginResponse, OAuthLoginResponse, OAuthCallbackResponse
from src.auth.oauth_factory import OAuthProviderFactory
from src.auth.google_oauth import GoogleOAuthProvider
from src.auth.microsoft_oauth import MicrosoftOAuthProvider
from src.storage.user_repository import UserRepository
from src.storage.models import User, OAuthToken

# Initialize test client
client = TestClient(app)

# Test configuration
TEST_CONFIG = {
    "jwt_secret": "test_secret_key_for_testing_purposes_only_not_for_production",
    "jwt_algorithm": "HS256",
    "jwt_expire_minutes": 30,
    "test_users": {
        "admin": {
            "username": "admin",
            "password": "securepassword",
            "email": "admin@example.com",
            "permissions": ["admin", "process", "view"]
        },
        "viewer": {
            "username": "viewer",
            "password": "viewerpass",
            "email": "viewer@example.com", 
            "permissions": ["view"]
        }
    },
    "oauth": {
        "google": {
            "client_id": "google_test_client_id",
            "client_secret": "google_test_client_secret",
            "redirect_uri": "http://localhost:8000/api/auth/google-callback",
        },
        "microsoft": {
            "client_id": "microsoft_test_client_id",
            "client_secret": "microsoft_test_client_secret",
            "redirect_uri": "http://localhost:8000/api/auth/microsoft-callback",
        }
    }
}

# Setup and teardown fixtures
@pytest.fixture(scope="module")
def setup_test_environment():
    """Setup test environment with necessary configuration and mocks."""
    # Create test directories if they don't exist
    os.makedirs("data/secure/user_tokens", exist_ok=True)
    os.makedirs("data/secure/backups", exist_ok=True)
    
    # Create an in-memory database for testing
    original_db_path = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    
    # Store original environment variables
    original_env = {
        "GOOGLE_CLIENT_ID": os.environ.get("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "MICROSOFT_CLIENT_ID": os.environ.get("MICROSOFT_CLIENT_ID"),
        "MICROSOFT_CLIENT_SECRET": os.environ.get("MICROSOFT_CLIENT_SECRET"),
        "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY"),
    }
    
    # Set test environment variables
    os.environ["GOOGLE_CLIENT_ID"] = TEST_CONFIG["oauth"]["google"]["client_id"]
    os.environ["GOOGLE_CLIENT_SECRET"] = TEST_CONFIG["oauth"]["google"]["client_secret"]
    os.environ["MICROSOFT_CLIENT_ID"] = TEST_CONFIG["oauth"]["microsoft"]["client_id"]
    os.environ["MICROSOFT_CLIENT_SECRET"] = TEST_CONFIG["oauth"]["microsoft"]["client_secret"]
    os.environ["JWT_SECRET_KEY"] = TEST_CONFIG["jwt_secret"]
    
    yield
    
    # Restore original environment variables
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
    
    if original_db_path:
        os.environ["DATABASE_URL"] = original_db_path
    else:
        os.environ.pop("DATABASE_URL", None)
    
    # Clean up test files
    for test_file in Path("data/secure/user_tokens").glob("*.json"):
        test_file.unlink()


@pytest.fixture
def mock_oauth_providers():
    """Mock OAuth provider interactions for testing."""
    with patch.object(GoogleOAuthProvider, "get_authorization_url", new_callable=AsyncMock) as mock_google_auth_url, \
         patch.object(GoogleOAuthProvider, "exchange_code_for_tokens", new_callable=AsyncMock) as mock_google_exchange, \
         patch.object(MicrosoftOAuthProvider, "get_authorization_url", new_callable=AsyncMock) as mock_ms_auth_url, \
         patch.object(MicrosoftOAuthProvider, "exchange_code_for_tokens", new_callable=AsyncMock) as mock_ms_exchange:
        
        # Mock Google OAuth
        mock_google_auth_url.return_value = (
            "https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id=test_client_id&redirect_uri=test_redirect_uri",
            "test_state_123"
        )
        
        mock_google_exchange.return_value = {
            "access_token": "google_test_access_token",
            "refresh_token": "google_test_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "provider_user_id": "google_user_123",
            "provider_email": "google_user@example.com",
            "scopes": ["email", "profile", "https://www.googleapis.com/auth/gmail.readonly"],
            "user_info": {
                "sub": "google_user_123",
                "name": "Google Test User",
                "email": "google_user@example.com",
                "picture": "https://example.com/profile.jpg"
            }
        }
        
        # Mock Microsoft OAuth
        mock_ms_auth_url.return_value = (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?response_type=code&client_id=test_client_id&redirect_uri=test_redirect_uri",
            "test_state_456"
        )
        
        mock_ms_exchange.return_value = {
            "access_token": "microsoft_test_access_token",
            "refresh_token": "microsoft_test_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "provider_user_id": "microsoft_user_456",
            "provider_email": "microsoft_user@example.com",
            "scopes": ["User.Read", "Mail.Read"],
            "user_info": {
                "id": "microsoft_user_456",
                "displayName": "Microsoft Test User",
                "userPrincipalName": "microsoft_user@example.com"
            }
        }
        
        yield {
            "google": {
                "auth_url": mock_google_auth_url,
                "exchange": mock_google_exchange
            },
            "microsoft": {
                "auth_url": mock_ms_auth_url,
                "exchange": mock_ms_exchange
            }
        }


@pytest.fixture
def mock_user_repository():
    """Mock user repository operations for testing."""
    with patch.object(UserRepository, "get_user_by_username", new_callable=AsyncMock) as mock_get_by_username, \
         patch.object(UserRepository, "get_user_by_email", new_callable=AsyncMock) as mock_get_by_email, \
         patch.object(UserRepository, "get_user_by_oauth", new_callable=AsyncMock) as mock_get_by_oauth, \
         patch.object(UserRepository, "create_user", new_callable=AsyncMock) as mock_create_user, \
         patch.object(UserRepository, "update_user_last_login", new_callable=AsyncMock) as mock_update_login, \
         patch.object(UserRepository, "save_oauth_token", new_callable=AsyncMock) as mock_save_token:
        
        # Setup mock implementations
        async def mock_get_user_by_username_impl(username):
            if username == "admin":
                return create_test_user(
                    id="admin_id_123",
                    username="admin",
                    email="admin@example.com",
                    permissions=["admin", "process", "view"]
                )
            elif username == "viewer":
                return create_test_user(
                    id="viewer_id_456",
                    username="viewer",
                    email="viewer@example.com",
                    permissions=["view"]
                )
            elif username == "google_user":
                return create_test_user(
                    id="google_user_id_789",
                    username="google_user",
                    email="google_user@example.com",
                    permissions=["view"],
                    oauth_tokens=[create_test_oauth_token(
                        provider="google",
                        provider_user_id="google_user_123"
                    )]
                )
            elif username == "microsoft_user":
                return create_test_user(
                    id="microsoft_user_id_789",
                    username="microsoft_user",
                    email="microsoft_user@example.com",
                    permissions=["view"],
                    oauth_tokens=[create_test_oauth_token(
                        provider="microsoft",
                        provider_user_id="microsoft_user_456"
                    )]
                )
            return None
        
        mock_get_by_username.side_effect = mock_get_user_by_username_impl
        
        async def mock_get_user_by_email_impl(email):
            if email == "admin@example.com":
                return create_test_user(
                    id="admin_id_123",
                    username="admin",
                    email="admin@example.com",
                    permissions=["admin", "process", "view"]
                )
            elif email == "viewer@example.com":
                return create_test_user(
                    id="viewer_id_456",
                    username="viewer",
                    email="viewer@example.com",
                    permissions=["view"]
                )
            elif email == "google_user@example.com":
                return create_test_user(
                    id="google_user_id_789",
                    username="google_user",
                    email="google_user@example.com",
                    permissions=["view"]
                )
            elif email == "microsoft_user@example.com":
                return create_test_user(
                    id="microsoft_user_id_789",
                    username="microsoft_user",
                    email="microsoft_user@example.com",
                    permissions=["view"]
                )
            return None
            
        mock_get_by_email.side_effect = mock_get_user_by_email_impl
        
        async def mock_get_user_by_oauth_impl(provider, provider_user_id):
            if provider == "google" and provider_user_id == "google_user_123":
                return create_test_user(
                    id="google_user_id_789",
                    username="google_user",
                    email="google_user@example.com",
                    permissions=["view"],
                    oauth_tokens=[create_test_oauth_token(
                        provider="google",
                        provider_user_id="google_user_123"
                    )]
                )
            elif provider == "microsoft" and provider_user_id == "microsoft_user_456":
                return create_test_user(
                    id="microsoft_user_id_789",
                    username="microsoft_user",
                    email="microsoft_user@example.com",
                    permissions=["view"],
                    oauth_tokens=[create_test_oauth_token(
                        provider="microsoft",
                        provider_user_id="microsoft_user_456"
                    )]
                )
            return None
            
        mock_get_by_oauth.side_effect = mock_get_user_by_oauth_impl
        
        async def mock_create_user_impl(email, username, display_name=None, permissions=None, profile_picture=None):
            user_id = f"{username}_id_{hash(email) % 1000}"
            return create_test_user(
                id=user_id,
                username=username,
                email=email,
                display_name=display_name,
                permissions=permissions or ["view"],
                profile_picture=profile_picture
            )
            
        mock_create_user.side_effect = mock_create_user_impl
        
        # Update login timestamp simply returns True
        mock_update_login.return_value = True
        
        # Save OAuth token returns a dummy token
        async def mock_save_oauth_token_impl(user_id, provider, provider_user_id, provider_email, 
                                           access_token, refresh_token, expires_in, scopes):
            return create_test_oauth_token(
                provider=provider,
                provider_user_id=provider_user_id,
                user_id=user_id
            )
            
        mock_save_token.side_effect = mock_save_oauth_token_impl
        
        yield {
            "get_by_username": mock_get_by_username,
            "get_by_email": mock_get_by_email,
            "get_by_oauth": mock_get_by_oauth,
            "create_user": mock_create_user,
            "update_login": mock_update_login,
            "save_token": mock_save_token
        }


# Helper functions
def create_test_user(id, username, email, permissions=None, display_name=None, profile_picture=None, oauth_tokens=None):
    """Create a test user object for mock responses."""
    user = MagicMock(spec=User)
    user.id = id
    user.username = username
    user.email = email
    user.display_name = display_name
    user.permissions = json.dumps(permissions or ["view"])
    user.profile_picture = profile_picture
    user.is_active = True
    user.created_at = datetime.now()
    user.last_login = datetime.now()
    user.oauth_tokens = oauth_tokens or []
    
    # Add to_dict method to mimic User model behavior
    user.to_dict.return_value = {
        "id": id,
        "username": username,
        "email": email,
        "display_name": display_name,
        "is_active": True,
        "permissions": permissions or ["view"],
        "profile_picture": profile_picture,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "oauth_providers": [token.provider for token in user.oauth_tokens]
    }
    
    return user


def create_test_oauth_token(provider, provider_user_id, user_id="test_user_id"):
    """Create a test OAuth token for mock responses."""
    token = MagicMock(spec=OAuthToken)
    token.id = f"token_{provider}_{hash(provider_user_id) % 1000}"
    token.user_id = user_id
    token.provider = provider
    token.provider_user_id = provider_user_id
    token.provider_email = f"{provider}_user@example.com"
    token.access_token = "encrypted_access_token"
    token.refresh_token = "encrypted_refresh_token"
    token.token_type = "Bearer"
    token.expires_at = datetime.now() + timedelta(hours=1)
    token.scopes = "profile,email,openid"
    token.created_at = datetime.now()
    token.updated_at = datetime.now()
    
    return token


def decode_response_token(token_str):
    """Decode JWT token for validation in tests."""
    # For test purposes, we use the test secret to decode
    return jwt.decode(
        token_str,
        TEST_CONFIG["jwt_secret"],
        algorithms=[TEST_CONFIG["jwt_algorithm"]]
    )


# Test cases

@pytest.mark.usefixtures("setup_test_environment", "mock_user_repository")
class TestAuthorizationAndPermissions:
    """Test authorization and permission-based access control."""
    
    def get_auth_token(self, username, permissions):
        """Helper to generate authentication token with specific permissions."""
        auth_service = AuthenticationService()
        token = auth_service.create_access_token({
            "username": username,
            "permissions": permissions
        })
        return token
    
    def test_admin_required(self, mock_user_repository):
        """Test endpoint requiring admin permission."""
        # Create a mock endpoint for testing
        @app.get("/test/admin-only", dependencies=[Depends(app.routes[0].dependencies[0])])
        async def admin_only_endpoint():
            return {"message": "Admin access granted"}
        
        # Test with admin token
        admin_token = self.get_auth_token("admin", ["admin", "process", "view"])
        response = client.get(
            "/test/admin-only",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        
        # Test with non-admin token
        viewer_token = self.get_auth_token("viewer", ["view"])
        response = client.get(
            "/test/admin-only",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        
        assert response.status_code == 403
        assert "Not authorized for admin" in response.json()["detail"]
    
    def test_process_required(self, mock_user_repository):
        """Test endpoint requiring process permission."""
        # Create a mock endpoint for testing
        @app.get("/test/process-only", dependencies=[Depends(app.routes[1].dependencies[0])])
        async def process_only_endpoint():
            return {"message": "Process access granted"}
        
        # Test with admin token (admin should have process permission)
        admin_token = self.get_auth_token("admin", ["admin", "process", "view"])
        response = client.get(
            "/test/process-only",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        
        # Test with process token
        process_token = self.get_auth_token("processor", ["process", "view"])
        response = client.get(
            "/test/process-only",
            headers={"Authorization": f"Bearer {process_token}"}
        )
        
        assert response.status_code == 200
        
        # Test with viewer token (should not have process permission)
        viewer_token = self.get_auth_token("viewer", ["view"])
        response = client.get(
            "/test/process-only",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        
        assert response.status_code == 403
        assert "Not authorized for process" in response.json()["detail"]
    
    def test_view_required(self, mock_user_repository):
        """Test endpoint requiring view permission."""
        # Create a mock endpoint for testing
        @app.get("/test/view-only", dependencies=[Depends(app.routes[2].dependencies[0])])
        async def view_only_endpoint():
            return {"message": "View access granted"}
        
        # Test with admin token (admin should have view permission)
        admin_token = self.get_auth_token("admin", ["admin", "process", "view"])
        response = client.get(
            "/test/view-only",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        
        # Test with viewer token
        viewer_token = self.get_auth_token("viewer", ["view"])
        response = client.get(
            "/test/view-only",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        
        assert response.status_code == 200
        
        # Test with no token
        response = client.get("/test/view-only")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]