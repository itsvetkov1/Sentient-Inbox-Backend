"""
Authentication Service Implementation with Google OAuth Support

Provides comprehensive authentication services including token generation,
validation, user credential verification, and Google OAuth authentication.

Design Considerations:
- Secure token handling with proper cryptographic practices
- Google OAuth integration with proper security measures
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
import httpx
from google.oauth2 import id_token
from google.auth.transport import requests

from api.config import get_settings
from api.models.auth import TokenData, UserCredentials, Token

# Configure logging
logger = logging.getLogger(__name__)

# Initialize security components
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class AuthenticationService:
    """
    Comprehensive authentication service with secure token management and Google OAuth.
    
    Implements secure user authentication, token generation and validation,
    comprehensive permission management, and Google OAuth integration.
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
        
        # Google OAuth configuration
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google-callback")
        
        # In production, this would be replaced with a database connection
        # This is a simplified example for development
        self.users_db = {
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
        
        logger.info("Authentication service initialized with Google OAuth support")
    
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
    
    async def verify_google_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify Google ID token and extract user information.
        
        Validates the token with Google's servers and extracts
        user profile information for authentication purposes.
        
        Args:
            token: Google ID token to verify
            
        Returns:
            Dictionary with user information or None if verification fails
        """
        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                self.google_client_id
            )

            # Verify issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                logger.warning(f"Invalid token issuer: {idinfo['iss']}")
                return None
                
            # Extract user information
            user_info = {
                'email': idinfo['email'],
                'name': idinfo.get('name', ''),
                'picture': idinfo.get('picture', ''),
                'given_name': idinfo.get('given_name', ''),
                'family_name': idinfo.get('family_name', ''),
                'locale': idinfo.get('locale', ''),
                'google_id': idinfo['sub']
            }
            
            logger.info(f"Successfully verified Google token for: {user_info['email']}")
            return user_info
            
        except ValueError as e:
            # Invalid token
            logger.error(f"Google token validation error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error verifying Google token: {str(e)}")
            return None
    
    async def get_or_create_google_user(self, google_user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get existing user or create a new one based on Google profile.
        
        Handles user creation and update based on Google authentication,
        ensuring proper permission assignment and profile synchronization.
        
        Args:
            google_user_info: User information from Google
            
        Returns:
            User data dictionary with permissions
        """
        email = google_user_info['email']
        
        # Check if user exists by email
        for username, user_data in self.users_db.items():
            if user_data.get('email') == email:
                # Update user info with latest from Google
                user_data['google_id'] = google_user_info['google_id']
                user_data['name'] = google_user_info.get('name', user_data.get('name', ''))
                logger.info(f"Updated existing user from Google login: {username}")
                return user_data
        
        # Create new user if not found
        username = email.split('@')[0]
        # Ensure username is unique
        base_username = username
        counter = 1
        while username in self.users_db:
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create user with default view permissions
        new_user = {
            "username": username,
            "email": email,
            "google_id": google_user_info['google_id'],
            "name": google_user_info.get('name', ''),
            "permissions": ["view"],  # Default to view permission only
            "hashed_password": None  # Google-authenticated users don't need passwords
        }
        
        self.users_db[username] = new_user
        logger.info(f"Created new user from Google login: {username}")
        return new_user
    
    async def exchange_code_for_tokens(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Implements OAuth 2.0 authorization code exchange with Google's
        token endpoint, securely obtaining access tokens with appropriate scopes.
        
        Args:
            code: Authorization code from Google OAuth flow
            
        Returns:
            Dictionary with tokens or None if exchange fails
        """
        try:
            token_url = "https://oauth2.googleapis.com/token"
            
            # Prepare token request
            data = {
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
                "code": code,
                "redirect_uri": self.google_redirect_uri,
                "grant_type": "authorization_code"
            }
            
            # Make request to Google token endpoint
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                
                if response.status_code != 200:
                    logger.error(f"Token exchange error: {response.text}")
                    return None
                    
                token_data = response.json()
                logger.info("Successfully exchanged code for tokens")
                return token_data
                
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {str(e)}")
            return None
    
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
    
    def get_google_auth_url(self) -> str:
        """
        Generate Google OAuth authorization URL with required scopes.
        
        Creates a properly formatted authorization URL that requests
        the necessary Gmail access scopes for the application.
        
        Returns:
            Google authorization URL string
        """
        # Define required Gmail scopes
        gmail_scopes = [
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify"
        ]
        
        # Encode scopes for URL
        scopes_str = "%20".join(gmail_scopes)
        
        # Build authorization URL
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={self.google_client_id}"
            f"&redirect_uri={self.google_redirect_uri}"
            f"&response_type=code"
            f"&scope={scopes_str}"
            f"&access_type=offline"
            f"&prompt=consent"
        )
        
        return auth_url


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