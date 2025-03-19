"""
User Repository Implementation

Provides comprehensive database operations for user management with
robust error handling, transaction management, and optimized queries.

Design Considerations:
- Repository pattern for data access abstraction
- Comprehensive error handling
- Optimized database queries
- Transaction management
- Secure token handling
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from src.storage.models import User, OAuthToken
from src.storage.database import get_db_session
from src.storage.encryption import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)

class UserRepository:
    """
    Repository for user management database operations.
    
    Implements comprehensive data access operations for user management
    with proper security, error handling, and transaction management.
    
    All methods return dictionaries rather than ORM objects to prevent
    session-related issues when objects are accessed after the session closes.
    """
    
    @staticmethod
    async def create_user(
        email: str,
        username: str,
        display_name: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        profile_picture: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new user with specified attributes.
        
        Args:
            email: User email address (unique)
            username: Username (unique)
            display_name: Optional display name
            permissions: Optional list of permissions (defaults to ["view"])
            profile_picture: Optional profile picture URL
            
        Returns:
            Dictionary containing user data
            
        Raises:
            ValueError: If user with email or username already exists
            RuntimeError: If database operation fails
        """
        with get_db_session() as session:
            # Check if user with email or username already exists
            existing_user = session.query(User).filter(
                or_(User.email == email, User.username == username)
            ).first()
            
            if existing_user:
                field = "email" if existing_user.email == email else "username"
                logger.warning(f"Attempted to create duplicate user with {field}: {email if field == 'email' else username}")
                raise ValueError(f"User with this {field} already exists")
            
            # Create new user
            user = User(
                email=email,
                username=username,
                display_name=display_name,
                permissions=json.dumps(permissions or ["view"]),
                profile_picture=profile_picture,
                created_at=datetime.utcnow(),
            )
            
            try:
                session.add(user)
                session.commit()
                
                # Important: Convert to dictionary before returning to avoid session issues
                user_dict = {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "display_name": user.display_name,
                    "permissions": json.loads(user.permissions) if isinstance(user.permissions, str) else user.permissions,
                    "profile_picture": user.profile_picture,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "oauth_providers": []  # No providers yet for a new user
                }
                
                logger.info(f"Created new user: {username} ({email})")
                return user_dict
            except Exception as e:
                logger.error(f"Failed to create user {email}: {str(e)}")
                raise RuntimeError(f"Failed to create user: {str(e)}")
    
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user by email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            Dictionary containing user data if found, None otherwise
        """
        with get_db_session() as session:
            user = session.query(User).filter(User.email == email).first()
            
            if not user:
                return None
                
            # Convert to dictionary before the session closes
            providers = [token.provider for token in user.oauth_tokens]
            
            return {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "display_name": user.display_name,
                "permissions": json.loads(user.permissions) if isinstance(user.permissions, str) else user.permissions,
                "profile_picture": user.profile_picture,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "oauth_providers": providers
            }
    
    @staticmethod
    async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user by username.
        
        Args:
            username: Username to search for
            
        Returns:
            Dictionary containing user data if found, None otherwise
        """
        with get_db_session() as session:
            user = session.query(User).filter(User.username == username).first()
            
            if not user:
                return None
                
            # Convert to dictionary before the session closes
            providers = [token.provider for token in user.oauth_tokens]
            
            return {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "display_name": user.display_name,
                "permissions": json.loads(user.permissions) if isinstance(user.permissions, str) else user.permissions,
                "profile_picture": user.profile_picture,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "oauth_providers": providers
            }
    
    @staticmethod
    async def get_user_by_oauth(provider: str, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user by OAuth provider and provider-specific ID.
        
        Args:
            provider: OAuth provider name (e.g., 'google', 'microsoft')
            provider_user_id: Provider-specific user ID
            
        Returns:
            Dictionary containing user data if found, None otherwise
        """
        with get_db_session() as session:
            token = session.query(OAuthToken).filter(
                and_(
                    OAuthToken.provider == provider,
                    OAuthToken.provider_user_id == provider_user_id
                )
            ).first()
            
            if not token or not token.user:
                return None
                
            user = token.user
            
            # Convert to dictionary before the session closes
            providers = [t.provider for t in user.oauth_tokens]
            
            return {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "display_name": user.display_name,
                "permissions": json.loads(user.permissions) if isinstance(user.permissions, str) else user.permissions,
                "profile_picture": user.profile_picture,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "oauth_providers": providers
            }
    
    @staticmethod
    async def update_user_last_login(user_id: str) -> bool:
        """
        Update user's last login timestamp.
        
        Args:
            user_id: User ID to update
            
        Returns:
            Success flag indicating if update was successful
        """
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"Attempted to update last login for non-existent user: {user_id}")
                return False
                
            user.last_login = datetime.utcnow()
            session.commit()
            return True
    
    @staticmethod
    async def save_oauth_token(
        user_id: str,
        provider: str,
        provider_user_id: str,
        provider_email: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_in: int,
        scopes: List[str]
    ) -> Dict[str, Any]:
        """
        Save or update OAuth token for a user.
        
        Args:
            user_id: User ID to associate the token with
            provider: OAuth provider name (e.g., 'google', 'microsoft')
            provider_user_id: Provider-specific user ID
            provider_email: Provider-specific email address
            access_token: OAuth access token
            refresh_token: OAuth refresh token (may be None)
            expires_in: Token expiration time in seconds
            scopes: List of granted OAuth scopes
            
        Returns:
            Dictionary containing token information
            
        Raises:
            ValueError: If user does not exist
            RuntimeError: If database operation fails
        """
        with get_db_session() as session:
            # Check if user exists
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"Attempted to save OAuth token for non-existent user: {user_id}")
                raise ValueError("User does not exist")
            
            # Calculate expiration timestamp
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Encrypt sensitive token data
            encrypted_access_token = encrypt_value(access_token)
            encrypted_refresh_token = encrypt_value(refresh_token) if refresh_token else None
            
            # Check if token for this provider already exists
            existing_token = session.query(OAuthToken).filter(
                and_(
                    OAuthToken.user_id == user_id,
                    OAuthToken.provider == provider
                )
            ).first()
            
            token_dict = {}
            
            if existing_token:
                # Update existing token
                existing_token.provider_user_id = provider_user_id
                existing_token.provider_email = provider_email
                existing_token.access_token = encrypted_access_token
                if encrypted_refresh_token:
                    existing_token.refresh_token = encrypted_refresh_token
                existing_token.expires_at = expires_at
                existing_token.scopes = ",".join(scopes)
                existing_token.updated_at = datetime.utcnow()
                
                token = existing_token
                logger.info(f"Updated OAuth token for user {user_id} and provider {provider}")
                
                # Build token dictionary
                token_dict = {
                    "id": token.id,
                    "user_id": token.user_id,
                    "provider": token.provider,
                    "provider_user_id": token.provider_user_id,
                    "provider_email": token.provider_email,
                    "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                    "scopes": token.scopes.split(",") if token.scopes else [],
                    "created_at": token.created_at.isoformat() if token.created_at else None,
                    "updated_at": token.updated_at.isoformat() if token.updated_at else None
                }
            else:
                # Create new token
                token = OAuthToken(
                    user_id=user_id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    provider_email=provider_email,
                    access_token=encrypted_access_token,
                    refresh_token=encrypted_refresh_token,
                    token_type="Bearer",
                    expires_at=expires_at,
                    scopes=",".join(scopes),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(token)
                logger.info(f"Created new OAuth token for user {user_id} and provider {provider}")
            
            try:
                session.commit()
                
                # If token_dict wasn't set (for new tokens), build it now
                if not token_dict:
                    token_dict = {
                        "id": token.id,
                        "user_id": token.user_id,
                        "provider": token.provider,
                        "provider_user_id": token.provider_user_id,
                        "provider_email": token.provider_email,
                        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                        "scopes": token.scopes.split(",") if token.scopes else [],
                        "created_at": token.created_at.isoformat() if token.created_at else None,
                        "updated_at": token.updated_at.isoformat() if token.updated_at else None
                    }
                
                return token_dict
            except Exception as e:
                logger.error(f"Failed to save OAuth token for user {user_id}: {str(e)}")
                raise RuntimeError(f"Failed to save OAuth token: {str(e)}")
    
    @staticmethod
    async def get_oauth_tokens(user_id: str, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get OAuth tokens for a user with decrypted values.
        
        Args:
            user_id: User ID to retrieve tokens for
            provider: Optional provider filter
            
        Returns:
            List of token dictionaries with decrypted values
        """
        with get_db_session() as session:
            query = session.query(OAuthToken).filter(OAuthToken.user_id == user_id)
            
            if provider:
                query = query.filter(OAuthToken.provider == provider)
                
            tokens = query.all()
            
            # Decrypt token values and convert to dictionaries
            result = []
            for token in tokens:
                result.append({
                    "id": token.id,
                    "provider": token.provider,
                    "provider_user_id": token.provider_user_id,
                    "provider_email": token.provider_email,
                    "access_token": decrypt_value(token.access_token),
                    "refresh_token": decrypt_value(token.refresh_token) if token.refresh_token else None,
                    "token_type": token.token_type,
                    "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                    "scopes": token.scopes.split(",") if token.scopes else [],
                    "created_at": token.created_at.isoformat() if token.created_at else None,
                    "updated_at": token.updated_at.isoformat() if token.updated_at else None
                })
                
            return result