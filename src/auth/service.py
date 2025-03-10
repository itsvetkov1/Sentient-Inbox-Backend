"""
Authentication Service Implementation with OAuth Support

Provides comprehensive authentication services including token generation,
validation, user credential verification, and OAuth authentication.

Design Considerations:
- Secure token handling with proper cryptographic practices
- OAuth integration with multiple providers
- Comprehensive error handling and logging
- Clear separation of concerns
- Future extensibility for different authentication methods
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple

from jose import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import aiohttp

from api.config import get_settings
from api.models.auth import TokenData, UserCredentials, Token
from src.storage.user_repository import UserRepository
from src.auth.oauth_factory import OAuthProviderFactory

# Configure logging
logger = logging.getLogger(__name__)

# Initialize security components
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class AuthenticationService:
    """
    Comprehensive authentication service with secure token management and OAuth integration.
    
    Implements secure user authentication, token generation and validation,
    comprehensive permission management, and OAuth provider integration for
    multiple identity providers.
    """
    
    def __init__(self):
        """
        Initialize authentication service with configuration settings.
        
        Loads security configuration and sets up authentication context
        with proper error handling and validation.
        """
        self.settings = get_settings()
        self.secret_key = self.settings.JWT_SECRET_KEY.get_secret_value()
        self.algorithm = self.settings.JWT_ALGORITHM
        self.access_token_expire_minutes = self.settings.JWT_TOKEN_EXPIRE_MINUTES
        
        # OAuth provider factory
        self.oauth_factory = OAuthProviderFactory
        
        # Load legacy users for backward compatibility
        # These will be migrated to the database on first access
        self.legacy_users_db = {
            "admin": {
                "username": "admin",
                "hashed_password": pwd_context.hash("securepassword"),
                "email": "admin@example.com",
                "permissions": ["admin", "process", "view"]
            },
            "viewer": {
                "username": "viewer",
                "hashed_password": pwd_context.hash("viewerpass"),
                "email": "viewer@example.com",
                "permissions": ["view"]
            }
        }
        
        logger.info("Authentication service initialized with OAuth provider integration")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against stored hash with proper cryptographic verification.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Stored password hash
            
        Returns:
            Boolean indicating if password matches
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """
        Generate secure password hash with proper cryptographic practices.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Secure password hash
        """
        return pwd_context.hash(password)
    
    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user against stored credentials with secure verification.
        
        Implements comprehensive authentication with proper error handling
        and secure password verification using cryptographic best practices.
        
        Args:
            username: Username to authenticate
            password: Password to verify
            
        Returns:
            User data if authenticated, None otherwise
        """
        # First try to get user from database
        user = await UserRepository.get_user_by_username(username)
        
        if not user:
            # Check legacy users
            legacy_user = self.legacy_users_db.get(username)
            if not legacy_user:
                logger.warning(f"Authentication attempt for unknown user: {username}")
                return None
                
            # Verify password for legacy user
            if not self.verify_password(password, legacy_user["hashed_password"]):
                logger.warning(f"Failed password verification for legacy user: {username}")
                return None
                
            # Create user in database
            try:
                user = await UserRepository.create_user(
                    email=legacy_user["email"],
                    username=legacy_user["username"],
                    display_name=legacy_user.get("display_name"),
                    permissions=legacy_user["permissions"],
                    profile_picture=legacy_user.get("profile_picture")
                )
                logger.info(f"Migrated legacy user to database: {username}")
            except Exception as e:
                logger.error(f"Failed to migrate legacy user {username}: {str(e)}")
                # Return legacy user data
                return legacy_user
        else:
            # We don't support password authentication for database users
            # They should use OAuth
            logger.warning(f"Password authentication attempted for OAuth user: {username}")
            return None
        
        logger.info(f"User authenticated successfully: {username}")
        return user.to_dict()
    
    async def get_authorization_url(self, provider: str, redirect_uri: str) -> Tuple[str, str]:
        """
        Get authorization URL for OAuth provider.
        
        Args:
            provider: OAuth provider name
            redirect_uri: Redirect URI for callback
            
        Returns:
            Tuple of (authorization_url, state)
            
        Raises:
            ValueError: If provider is not supported
        """
        try:
            oauth_provider = self.oauth_factory.get_provider(provider)
            return await oauth_provider.get_authorization_url(redirect_uri)
        except Exception as e:
            logger.error(f"Error getting authorization URL for provider {provider}: {str(e)}")
            raise ValueError(f"Failed to get authorization URL: {str(e)}")
    
    async def process_oauth_callback(self, provider: str, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Process OAuth callback and create or update user.
        
        Args:
            provider: OAuth provider name
            code: Authorization code
            redirect_uri: Redirect URI used in authorization request
            
        Returns:
            Dictionary containing user information and access token
            
        Raises:
            ValueError: If OAuth callback processing fails
        """
        try:
            # Get OAuth provider
            oauth_provider = self.oauth_factory.get_provider(provider)
            
            # Exchange code for tokens
            tokens = await oauth_provider.exchange_code_for_tokens(code, redirect_uri)
            
            # Get or create user
            user = await self._get_or_create_oauth_user(provider, tokens)
            
            # Save OAuth tokens
            await UserRepository.save_oauth_token(
                user_id=user["id"],
                provider=provider,
                provider_user_id=tokens["provider_user_id"],
                provider_email=tokens["provider_email"],
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                expires_in=tokens["expires_in"],
                scopes=tokens["scopes"]
            )
            
            # Update last login timestamp
            await UserRepository.update_user_last_login(user["id"])
            
            # Generate JWT token
            access_token = self.create_access_token(
                data={
                    "username": user["username"],
                    "permissions": user["permissions"]
                }
            )
            
            return {
                "user": user,
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": self.access_token_expire_minutes * 60
            }
            
        except Exception as e:
            logger.error(f"Error processing OAuth callback: {str(e)}")
            raise ValueError(f"Failed to process OAuth callback: {str(e)}")
    
    async def _get_or_create_oauth_user(self, provider: str, tokens: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get existing user or create a new one based on OAuth profile.
        
        Args:
            provider: OAuth provider name
            tokens: Token data including user profile
            
        Returns:
            User data dictionary
        """
        provider_user_id = tokens["provider_user_id"]
        provider_email = tokens["provider_email"]
        user_info = tokens["user_info"]
        
        # Try to find user by OAuth provider and ID
        user = await UserRepository.get_user_by_oauth(provider, provider_user_id)
        
        if user:
            # User exists, return data
            logger.info(f"Found existing user for {provider} ID {provider_user_id}")
            return user.to_dict()
            
        # Try to find user by email
        user = await UserRepository.get_user_by_email(provider_email)
        
        if user:
            # User exists with this email, link OAuth account
            logger.info(f"Linking {provider} account to existing user: {user.username}")
            # User will be linked when we save the OAuth token
            return user.to_dict()
            
        # Create new user
        # Generate username from email
        email_username = provider_email.split('@')[0]
        base_username = email_username.lower()
        username = base_username
        
        # Check if username exists
        attempts = 0
        while await UserRepository.get_user_by_username(username):
            attempts += 1
            username = f"{base_username}{attempts}"
            
        # Get display name from provider-specific fields
        display_name = None
        if provider == "google":
            display_name = user_info.get("name")
        elif provider == "microsoft":
            display_name = user_info.get("displayName")
            
        # Create new user with view permission
        try:
            user = await UserRepository.create_user(
                email=provider_email,
                username=username,
                display_name=display_name,
                permissions=["view"],
                profile_picture=user_info.get("picture")
            )
            logger.info(f"Created new user from {provider} authentication: {username}")
            return user.to_dict()
        except Exception as e:
            logger.error(f"Failed to create user from OAuth profile: {str(e)}")
            raise ValueError(f"Failed to create user: {str(e)}")
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token with proper security practices.
        
        Generates secure JWT token with appropriate claims and expiration
        using cryptographic best practices.
        
        Args:
            data: Token payload data
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        # Set token expiration
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        
        # Generate token with proper security
        try:
            encoded_jwt = jwt.encode(
                to_encode, 
                self.secret_key, 
                algorithm=self.algorithm
            )
            return encoded_jwt
        except Exception as e:
            logger.error(f"Token generation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate authentication token"
            )
    
    async def get_current_user(self, token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
        """
        Validate token and extract current user with proper security validation.
        
        Implements comprehensive token validation with proper error handling
        and security verification of token claims.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Validated user data
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            # Decode and validate token
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            
            # Extract user information
            username = payload.get("username")
            if username is None:
                logger.warning("Token missing username claim")
                raise credentials_exception
            
            permissions = payload.get("permissions", [])
            token_data = TokenData(username=username, permissions=permissions, exp=payload["exp"])
            
        except jwt.JWTError as e:
            logger.warning(f"Token validation error: {str(e)}")
            raise credentials_exception
        
        # Verify user exists in database
        user = await UserRepository.get_user_by_username(token_data.username)
        
        if user:
            return user.to_dict()
            
        # Check legacy users (for backward compatibility)
        legacy_user = self.legacy_users_db.get(token_data.username)
        if legacy_user:
            # Create user in database
            try:
                user = await UserRepository.create_user(
                    email=legacy_user["email"],
                    username=legacy_user["username"],
                    display_name=legacy_user.get("display_name"),
                    permissions=legacy_user["permissions"],
                    profile_picture=legacy_user.get("profile_picture")
                )
                logger.info(f"Migrated legacy user to database during token validation: {token_data.username}")
                return user.to_dict()
            except Exception as e:
                logger.error(f"Failed to migrate legacy user {token_data.username}: {str(e)}")
                # Return legacy user data
                return legacy_user
                
        # User not found in database or legacy storage
        logger.warning(f"Token contains unknown user: {token_data.username}")
        raise credentials_exception
    
    async def get_current_user_permissions(self, user: Dict[str, Any] = Depends(get_current_user)) -> List[str]:
        """
        Extract permissions from authenticated user.
        
        Args:
            user: Authenticated user data
            
        Returns:
            List of user permissions
        """
        return user.get("permissions", [])
    
    async def check_permission(self, required_permission: str, user: Dict[str, Any] = Depends(get_current_user)) -> bool:
        """
        Check if user has required permission with proper authorization verification.
        
        Implements comprehensive permission checking with proper error handling
        and security validation.
        
        Args:
            required_permission: Permission to check
            user: Authenticated user data
            
        Returns:
            Boolean indicating if user has permission
            
        Raises:
            HTTPException: If user lacks required permission
        """
        user_permissions = user.get("permissions", [])
        
        if required_permission not in user_permissions:
            logger.warning(
                f"Permission denied: {user['username']} lacks {required_permission} permission"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized for {required_permission}",
            )
        
        return True
    

# Singleton instance for dependency injection
auth_service = AuthenticationService()

# Common dependencies for route handlers
def get_auth_service() -> AuthenticationService:
    """Provide authentication service instance for dependency injection."""
    return auth_service

async def require_admin(
    auth_service: AuthenticationService = Depends(get_auth_service),
    user: Dict[str, Any] = Depends(auth_service.get_current_user)
) -> bool:
    """Require admin permission for route access."""
    return await auth_service.check_permission("admin", user)

async def require_process(
    auth_service: AuthenticationService = Depends(get_auth_service),
    user: Dict[str, Any] = Depends(auth_service.get_current_user)
) -> bool:
    """Require process permission for route access."""
    return await auth_service.check_permission("process", user)

async def require_view(
    auth_service: AuthenticationService = Depends(get_auth_service),
    user: Dict[str, Any] = Depends(auth_service.get_current_user)
) -> bool:
    """Require view permission for route access."""
    return await auth_service.check_permission("view", user)