"""
Unit tests for user repository functionality.

These tests validate user and OAuth token management operations,
data access patterns, and error handling.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from src.storage.models import User, OAuthToken
from src.storage.user_repository import UserRepository


@pytest.mark.asyncio
class TestUserRepository:
    """Test suite for UserRepository class."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=None)
        return session
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock User object."""
        user = MagicMock(spec=User)
        user.id = "user123"
        user.email = "test@example.com"
        user.username = "testuser"
        user.display_name = "Test User"
        user.permissions = json.dumps(["view"])
        user.created_at = datetime.utcnow()
        user.last_login = None
        return user
    
    @pytest.fixture
    def mock_oauth_token(self):
        """Create a mock OAuthToken object."""
        token = MagicMock(spec=OAuthToken)
        token.id = "token123"
        token.user_id = "user123"
        token.provider = "google"
        token.provider_user_id = "google_user_123"
        token.provider_email = "test@gmail.com"
        token.access_token = "encrypted_access_token"
        token.refresh_token = "encrypted_refresh_token"
        token.token_type = "Bearer"
        token.expires_at = datetime.utcnow() + timedelta(hours=1)
        token.scopes = "email,profile"
        token.created_at = datetime.utcnow()
        token.updated_at = datetime.utcnow()
        return token
    
    @patch('src.storage.user_repository.get_db_session')
    async def test_create_user_success(self, mock_get_db_session, mock_session):
        """Test successful user creation."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None  # No existing user
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        
        # User data
        email = "new@example.com"
        username = "newuser"
        display_name = "New User"
        
        # Call function
        with patch('src.storage.user_repository.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2025, 1, 1, 12, 0, 0)
            
            user = await UserRepository.create_user(
                email=email,
                username=username,
                display_name=display_name
            )
        
        # Verify user was created with expected values
        assert user is not None
        
        # Verify session operations
        mock_session.query.assert_called_once_with(User)
        mock_query.filter.assert_called_once()  # Check for existing user
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        # Verify the added user has the correct attributes
        added_user = mock_session.add.call_args[0][0]
        assert added_user.email == email
        assert added_user.username == username
        assert added_user.display_name == display_name
        assert added_user.permissions == json.dumps(["view"])  # Default permission
        assert added_user.created_at == datetime(2025, 1, 1, 12, 0, 0)
    
    @patch('src.storage.user_repository.get_db_session')
    async def test_create_user_already_exists(self, mock_get_db_session, mock_session, mock_user):
        """Test user creation when user already exists."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks to return an existing user
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_user  # Existing user
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        
        # Call function with same email
        with pytest.raises(ValueError) as excinfo:
            await UserRepository.create_user(
                email=mock_user.email,
                username="newusername"
            )
        
        # Verify error message
        assert "User with this email already exists" in str(excinfo.value)
        
        # Call function with same username but different email
        mock_user.email = "different@example.com"  # Simulate different email but same username
        
        with pytest.raises(ValueError) as excinfo:
            await UserRepository.create_user(
                email="new@example.com",
                username=mock_user.username
            )
        
        # Verify error message
        assert "User with this username already exists" in str(excinfo.value)
        
        # Verify no user was added or committed
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()
    
    @patch('src.storage.user_repository.get_db_session')
    async def test_get_user_by_email(self, mock_get_db_session, mock_session, mock_user):
        """Test retrieving a user by email."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_user  # Return mock user
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        
        # Call function
        user = await UserRepository.get_user_by_email(email=mock_user.email)
        
        # Verify correct user was returned
        assert user is mock_user
        
        # Verify query used the correct filter
        mock_session.query.assert_called_once_with(User)
        mock_query.filter.assert_called_once()
    
    @patch('src.storage.user_repository.get_db_session')
    async def test_get_user_by_username(self, mock_get_db_session, mock_session, mock_user):
        """Test retrieving a user by username."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_user  # Return mock user
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        
        # Call function
        user = await UserRepository.get_user_by_username(username=mock_user.username)
        
        # Verify correct user was returned
        assert user is mock_user
        
        # Verify query used the correct filter
        mock_session.query.assert_called_once_with(User)
        mock_query.filter.assert_called_once()
    
    @patch('src.storage.user_repository.get_db_session')
    async def test_get_user_by_oauth(self, mock_get_db_session, mock_session, mock_user, mock_oauth_token):
        """Test retrieving a user by OAuth provider and provider-specific ID."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_oauth_token.user = mock_user  # Link token to user
        mock_filter.first.return_value = mock_oauth_token  # Return mock token
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        
        # Call function
        user = await UserRepository.get_user_by_oauth(
            provider=mock_oauth_token.provider,
            provider_user_id=mock_oauth_token.provider_user_id
        )
        
        # Verify correct user was returned
        assert user is mock_user
        
        # Verify query used the correct filters
        mock_session.query.assert_called_once_with(OAuthToken)
        mock_query.filter.assert_called_once()
    
    @patch('src.storage.user_repository.get_db_session')
    async def test_update_user_last_login_success(self, mock_get_db_session, mock_session, mock_user):
        """Test successful update of user's last login timestamp."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_user  # Return mock user
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        
        # Call function
        with patch('src.storage.user_repository.datetime') as mock_datetime:
            login_time = datetime(2025, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = login_time
            
            result = await UserRepository.update_user_last_login(user_id=mock_user.id)
        
        # Verify result
        assert result is True
        
        # Verify last_login was updated
        assert mock_user.last_login == login_time
        
        # Verify session operations
        mock_session.query.assert_called_once_with(User)
        mock_query.filter.assert_called_once()
        mock_session.commit.assert_called_once()
    
    @patch('src.storage.user_repository.get_db_session')
    async def test_update_user_last_login_not_found(self, mock_get_db_session, mock_session):
        """Test updating last login for non-existent user."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks to return no user
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None  # No user found
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        
        # Call function
        result = await UserRepository.update_user_last_login(user_id="nonexistent")
        
        # Verify result
        assert result is False
        
        # Verify session was queried but not committed
        mock_session.query.assert_called_once_with(User)
        mock_query.filter.assert_called_once()
        mock_session.commit.assert_not_called()
    
    @patch('src.storage.user_repository.get_db_session')
    @patch('src.storage.user_repository.encrypt_value')
    async def test_save_oauth_token_new(self, mock_encrypt, mock_get_db_session, mock_session, mock_user):
        """Test saving a new OAuth token."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks
        mock_user_query = MagicMock()
        mock_user_filter = MagicMock()
        mock_user_filter.first.return_value = mock_user  # Return mock user
        mock_user_query.filter.return_value = mock_user_filter
        
        mock_token_query = MagicMock()
        mock_token_filter = MagicMock()
        mock_token_filter.first.return_value = None  # No existing token
        mock_token_query.filter.return_value = mock_token_filter
        
        # Configure session to return different query objects
        mock_session.query.side_effect = [mock_user_query, mock_token_query]
        
        # Setup encrypt mock
        mock_encrypt.side_effect = lambda x: f"encrypted_{x}" if x else None
        
        # Token data
        provider = "google"
        provider_user_id = "google_user_123"
        provider_email = "test@gmail.com"
        access_token = "access_token_123"
        refresh_token = "refresh_token_456"
        expires_in = 3600
        scopes = ["email", "profile"]
        
        # Call function
        with patch('src.storage.user_repository.datetime') as mock_datetime:
            now = datetime(2025, 1, 1, 12, 0, 0)
            expires = datetime(2025, 1, 1, 13, 0, 0)  # 1 hour later
            mock_datetime.utcnow.return_value = now
            mock_datetime.utcnow.side_effect = [now, now]  # Multiple calls
            
            token = await UserRepository.save_oauth_token(
                user_id=mock_user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=provider_email,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                scopes=scopes
            )
        
        # Verify token was created
        assert token is not None
        
        # Verify queries
        mock_session.query.assert_called_with(OAuthToken)
        
        # Verify encryption was called
        mock_encrypt.assert_any_call(access_token)
        mock_encrypt.assert_any_call(refresh_token)
        
        # Verify session operations
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        # Verify the added token has the correct attributes
        added_token = mock_session.add.call_args[0][0]
        assert added_token.user_id == mock_user.id
        assert added_token.provider == provider
        assert added_token.provider_user_id == provider_user_id
        assert added_token.provider_email == provider_email
        assert added_token.access_token == f"encrypted_{access_token}"
        assert added_token.refresh_token == f"encrypted_{refresh_token}"
        assert added_token.scopes == "email,profile"
    
    @patch('src.storage.user_repository.get_db_session')
    @patch('src.storage.user_repository.encrypt_value')
    async def test_save_oauth_token_update(self, mock_encrypt, mock_get_db_session, mock_session, mock_user, mock_oauth_token):
        """Test updating an existing OAuth token."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks
        mock_user_query = MagicMock()
        mock_user_filter = MagicMock()
        mock_user_filter.first.return_value = mock_user  # Return mock user
        mock_user_query.filter.return_value = mock_user_filter
        
        mock_token_query = MagicMock()
        mock_token_filter = MagicMock()
        mock_token_filter.first.return_value = mock_oauth_token  # Existing token
        mock_token_query.filter.return_value = mock_token_filter
        
        # Configure session to return different query objects
        mock_session.query.side_effect = [mock_user_query, mock_token_query]
        
        # Setup encrypt mock
        mock_encrypt.side_effect = lambda x: f"encrypted_{x}" if x else None
        
        # Token data (updated values)
        provider = mock_oauth_token.provider
        provider_user_id = "updated_user_id"
        provider_email = "updated@gmail.com"
        access_token = "new_access_token"
        refresh_token = "new_refresh_token"
        expires_in = 3600
        scopes = ["email", "profile", "calendar"]
        
        # Call function
        with patch('src.storage.user_repository.datetime') as mock_datetime:
            now = datetime(2025, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = now
            
            token = await UserRepository.save_oauth_token(
                user_id=mock_user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=provider_email,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                scopes=scopes
            )
        
        # Verify the same token object was returned
        assert token is mock_oauth_token
        
        # Verify token fields were updated
        assert mock_oauth_token.provider_user_id == provider_user_id
        assert mock_oauth_token.provider_email == provider_email
        assert mock_oauth_token.access_token == f"encrypted_{access_token}"
        assert mock_oauth_token.refresh_token == f"encrypted_{refresh_token}"
        assert mock_oauth_token.scopes == "email,profile,calendar"
        assert mock_oauth_token.updated_at == now
        
        # Verify no new token was added
        mock_session.add.assert_not_called()
        
        # Verify session was committed
        mock_session.commit.assert_called_once()
    
    @patch('src.storage.user_repository.get_db_session')
    @patch('src.storage.user_repository.decrypt_value')
    async def test_get_oauth_tokens(self, mock_decrypt, mock_get_db_session, mock_session, mock_oauth_token):
        """Test retrieving OAuth tokens with decrypted values."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [mock_oauth_token]  # Return list with one token
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        
        # Setup decrypt mock
        mock_decrypt.side_effect = lambda x: x.replace("encrypted_", "") if x else None
        
        # Set token attributes for testing
        mock_oauth_token.access_token = "encrypted_access_token_123"
        mock_oauth_token.refresh_token = "encrypted_refresh_token_456"
        mock_oauth_token.expires_at = datetime(2025, 1, 1, 12, 0, 0)
        mock_oauth_token.created_at = datetime(2025, 1, 1, 11, 0, 0)
        mock_oauth_token.updated_at = datetime(2025, 1, 1, 11, 30, 0)
        
        # Call function
        tokens = await UserRepository.get_oauth_tokens(user_id=mock_oauth_token.user_id)
        
        # Verify correct result
        assert len(tokens) == 1
        token_dict = tokens[0]
        
        assert token_dict["id"] == mock_oauth_token.id
        assert token_dict["provider"] == mock_oauth_token.provider
        assert token_dict["provider_user_id"] == mock_oauth_token.provider_user_id
        assert token_dict["provider_email"] == mock_oauth_token.provider_email
        assert token_dict["access_token"] == "access_token_123"  # Decrypted
        assert token_dict["refresh_token"] == "refresh_token_456"  # Decrypted
        assert token_dict["token_type"] == mock_oauth_token.token_type
        assert token_dict["expires_at"] == mock_oauth_token.expires_at.isoformat()
        assert token_dict["scopes"] == ["email", "profile"]  # Split by comma
        assert token_dict["created_at"] == mock_oauth_token.created_at.isoformat()
        assert token_dict["updated_at"] == mock_oauth_token.updated_at.isoformat()
        
        # Verify query and filter
        mock_session.query.assert_called_once_with(OAuthToken)
        mock_query.filter.assert_called_once()
        
        # Verify decrypt was called for tokens
        mock_decrypt.assert_any_call("encrypted_access_token_123")
        mock_decrypt.assert_any_call("encrypted_refresh_token_456")
    
    @patch('src.storage.user_repository.get_db_session')
    async def test_get_oauth_tokens_with_provider_filter(self, mock_get_db_session, mock_session, mock_oauth_token):
        """Test retrieving OAuth tokens filtered by provider."""
        # Setup session mock
        mock_get_db_session.return_value = mock_session
        
        # Setup query mocks
        mock_query = MagicMock()
        mock_filter1 = MagicMock()
        mock_filter2 = MagicMock()
        mock_filter1.filter.return_value = mock_filter2
        mock_filter2.all.return_value = [mock_oauth_token]
        mock_query.filter.return_value = mock_filter1
        mock_session.query.return_value = mock_query
        
        # Mock decrypt to avoid actual decryption
        with patch('src.storage.user_repository.decrypt_value', lambda x: x):
            # Call function with provider filter
            tokens = await UserRepository.get_oauth_tokens(
                user_id=mock_oauth_token.user_id,
                provider=mock_oauth_token.provider
            )
        
        # Verify query was filtered by both user_id and provider
        mock_session.query.assert_called_once_with(OAuthToken)
        mock_query.filter.assert_called_once()  # First filter by user_id
        mock_filter1.filter.assert_called_once()  # Second filter by provider
        
        # Verify non-empty result
        assert len(tokens) == 1


if __name__ == "__main__":
    pytest.main()
