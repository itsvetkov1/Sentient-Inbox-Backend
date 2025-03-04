"""
Authentication Service Implementation

Provides comprehensive authentication services including token generation,
validation, and user credential verification with proper security practices.

Design Considerations:
- Secure token handling with proper cryptographic practices
- Comprehensive error handling and logging
- Clear separation of concerns
- Future extensibility for different authentication methods
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

from jose import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from api.config import get_settings
from api.models.auth import TokenData, UserCredentials, Token

# Configure logging
logger = logging.getLogger(__name__)

# Initialize security components
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class AuthenticationService:
    """
    Comprehensive authentication service with secure token management.
    
    Implements secure user authentication, token generation and validation,
    and comprehensive permission management with proper security practices.
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
        
        # In production, this would be replaced with a database connection
        # This is a simplified example for development
        self.users_db = {
            "admin": {
                "username": "admin",
                "hashed_password": pwd_context.hash("securepassword"),
                "permissions": ["admin", "process", "view"]
            },
            "viewer": {
                "username": "viewer",
                "hashed_password": pwd_context.hash("viewerpass"),
                "permissions": ["view"]
            }
        }
        
        logger.info("Authentication service initialized")
    
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
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
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
        user = self.users_db.get(username)
        if not user:
            logger.warning(f"Authentication attempt for unknown user: {username}")
            return None
        
        if not self.verify_password(password, user["hashed_password"]):
            logger.warning(f"Failed password verification for user: {username}")
            return None
        
        logger.info(f"User authenticated successfully: {username}")
        return user
    
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
        
        # Verify user exists
        user = self.users_db.get(token_data.username)
        if user is None:
            logger.warning(f"Token contains unknown user: {token_data.username}")
            raise credentials_exception
        
        return user
    
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
