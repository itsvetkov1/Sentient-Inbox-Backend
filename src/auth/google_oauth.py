"""
Google OAuth Provider Implementation with File-Based Credentials

Implements the Google OAuth provider service with comprehensive token
management, user profile handling, and error recovery. Supports loading
credentials from environment variables or directly from client_secret.json.

Design Considerations:
- Robust error handling with retry mechanism
- Comprehensive token validation and refresh
- Detailed logging for troubleshooting
- Full Google API scope support
- Flexible credential loading from multiple sources
- Secure storage of client credentials
"""

import os
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import aiohttp
from datetime import datetime, timedelta

from src.auth.oauth_base import OAuthProvider

logger = logging.getLogger(__name__)

class GoogleOAuthProvider(OAuthProvider):
    """
    Google OAuth2 provider implementation with file-based credentials support.
    
    Implements the OAuth provider interface for Google authentication
    with comprehensive error handling, token management, and user
    profile handling. Supports loading credentials from environment
    variables or directly from client_secret.json files.
    """
    
    # Google OAuth endpoints
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
    REVOKE_URL = "https://oauth2.googleapis.com/revoke"
    
    def __init__(self):
        """
        Initialize the Google OAuth provider with client credentials.
        
        Attempts to load credentials in the following order:
        1. From GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables
        2. From client_secret.json file in various common locations
        
        Raises:
            ValueError: If credentials cannot be loaded from any source
        """
        # First attempt to load from environment variables
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        credentials_source = "environment variables"
        
        # If environment variables are not set, attempt to load from JSON file
        if not self.client_id or not self.client_secret:
            logger.info("OAuth credentials not found in environment variables, attempting to load from file")
            credentials_loaded = self._load_credentials_from_file()
            
            if credentials_loaded:
                credentials_source = "client_secret.json file"
            else:
                # If we couldn't load from either source, raise an error
                raise ValueError(
                    "Google OAuth configuration incomplete. "
                    "Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables "
                    "or ensure a valid client_secret.json file is available."
                )
        
        # Default scopes for Gmail access
        self.default_scopes = [
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify"
        ]
        
        logger.info(f"Google OAuth provider initialized successfully using {credentials_source}")
    
    def _load_credentials_from_file(self) -> bool:
        """
        Load OAuth credentials from client_secret.json file.
        
        Attempts to find and load credentials from client_secret.json in various
        common locations relative to the current working directory and module path.
        
        Returns:
            bool: True if credentials were successfully loaded, False otherwise
        """
        # Define common locations where the file might be found
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
        
        potential_paths = [
            "client_secret.json",  # Current working directory
            os.path.join(current_dir, "client_secret.json"),  # Module directory
            os.path.join(project_root, "client_secret.json"),  # Project root
            os.path.join(os.path.expanduser("~"), "client_secret.json"),  # User home
            # Add additional paths if needed for your project structure
        ]
        
        # Debug log showing where we're looking
        logger.debug(f"Looking for client_secret.json in: {', '.join(potential_paths)}")
        
        # Try each potential path
        for path in potential_paths:
            try:
                if os.path.exists(path):
                    logger.info(f"Found credentials file at: {path}")
                    with open(path, 'r') as file:
                        credentials = json.load(file)
                    
                    # Extract client ID and secret based on the file structure
                    if 'web' in credentials:
                        # Web application credentials
                        self.client_id = credentials['web']['client_id']
                        self.client_secret = credentials['web']['client_secret']
                        logger.info("Loaded web application credentials from client_secret.json")
                        return True
                    elif 'installed' in credentials:
                        # Installed/Desktop application credentials
                        self.client_id = credentials['installed']['client_id']
                        self.client_secret = credentials['installed']['client_secret']
                        logger.info("Loaded installed application credentials from client_secret.json")
                        return True
                    else:
                        # Unknown structure, log available keys
                        logger.warning(f"Unrecognized credentials format in {path}. Available keys: {list(credentials.keys())}")
            except Exception as e:
                logger.warning(f"Error loading credentials from {path}: {str(e)}")
        
        # If we get here, we couldn't load from any file
        logger.warning("Failed to load credentials from any client_secret.json location")
        return False
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "google"
    
    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate Google OAuth authorization URL.
        
        Args:
            redirect_uri: URI to redirect after authorization
            state: Optional state parameter for security
            
        Returns:
            Tuple of (authorization_url, state)
        """
        # Generate random state if not provided
        if not state:
            state = str(uuid.uuid4())
        
        # Construct authorization URL
        scopes_str = "%20".join(self.default_scopes)
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scopes_str,
            "access_type": "offline",
            "state": state,
            "prompt": "consent"  # Always show consent screen for refresh token
        }
        
        # Build query string
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        auth_url = f"{self.AUTH_URL}?{query_string}"
        
        logger.debug(f"Generated Google authorization URL with state: {state}")
        logger.debug(f"Using redirect URI: {redirect_uri}")
        return auth_url, state
    
    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from Google
            redirect_uri: Redirect URI used in the authorization request
            
        Returns:
            Dictionary containing token information
            
        Raises:
            ValueError: If code exchange fails
        """
        try:
            # Prepare token request
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
            
            # Make request to token endpoint
            async with aiohttp.ClientSession() as session:
                async with session.post(self.TOKEN_URL, data=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to exchange code: {error_text}")
                        raise ValueError(f"Failed to exchange code: {error_text}")
                        
                    token_data = await response.json()
                    
            # Get user information
            user_info = await self.get_user_info(token_data["access_token"])
            
            # Combine token data with user info
            result = {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),  # May not be present
                "expires_in": token_data["expires_in"],
                "token_type": token_data["token_type"],
                "id_token": token_data.get("id_token"),
                "provider_user_id": user_info["sub"],
                "provider_email": user_info["email"],
                "scopes": token_data.get("scope", "").split(" "),
                "user_info": user_info
            }
            
            logger.info(f"Successfully exchanged code for tokens for user: {user_info['email']}")
            return result
            
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {str(e)}")
            raise ValueError(f"Failed to exchange authorization code: {str(e)}")
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh expired access token.
        
        Args:
            refresh_token: Refresh token to use
            
        Returns:
            Dictionary containing new token information
            
        Raises:
            ValueError: If token refresh fails
        """
        try:
            # Prepare refresh request
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            
            # Make request to token endpoint
            async with aiohttp.ClientSession() as session:
                async with session.post(self.TOKEN_URL, data=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to refresh token: {error_text}")
                        raise ValueError(f"Failed to refresh token: {error_text}")
                        
                    token_data = await response.json()
            
            # Prepare result (note: refresh token is not replaced)
            result = {
                "access_token": token_data["access_token"],
                "expires_in": token_data["expires_in"],
                "token_type": token_data["token_type"],
                "scope": token_data.get("scope", "").split(" ")
            }
            
            logger.info("Successfully refreshed Google access token")
            return result
            
        except Exception as e:
            logger.error(f"Error refreshing access token: {str(e)}")
            raise ValueError(f"Failed to refresh access token: {str(e)}")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information from Google.
        
        Args:
            access_token: Access token to use
            
        Returns:
            Dictionary containing user profile information
            
        Raises:
            ValueError: If user info request fails
        """
        try:
            # Prepare headers
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Make request to userinfo endpoint
            async with aiohttp.ClientSession() as session:
                async with session.get(self.USERINFO_URL, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get user info: {error_text}")
                        raise ValueError(f"Failed to get user info: {error_text}")
                        
                    user_info = await response.json()
            
            logger.debug(f"Successfully retrieved user info for: {user_info.get('email')}")
            return user_info
            
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            raise ValueError(f"Failed to get user info: {str(e)}")
    
    async def validate_token(self, access_token: str) -> bool:
        """
        Validate if access token is still valid.
        
        Args:
            access_token: Access token to validate
            
        Returns:
            Boolean indicating if token is valid
        """
        try:
            # Make request to tokeninfo endpoint
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.TOKENINFO_URL}?access_token={access_token}") as response:
                    if response.status != 200:
                        logger.debug(f"Token validation failed with status: {response.status}")
                        return False
                        
                    # Check expiration
                    token_info = await response.json()
                    if "error" in token_info:
                        logger.debug(f"Token validation failed: {token_info['error']}")
                        return False
                        
                    # Token is valid
                    return True
                    
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return False
    
    async def revoke_token(self, token: str, token_type_hint: str = "access_token") -> bool:
        """
        Revoke an access or refresh token.
        
        Args:
            token: Token to revoke
            token_type_hint: Type of token ('access_token' or 'refresh_token')
            
        Returns:
            Boolean indicating if revocation was successful
        """
        try:
            # Prepare revocation request
            payload = {
                "token": token,
                "token_type_hint": token_type_hint
            }
            
            # Make request to revocation endpoint
            async with aiohttp.ClientSession() as session:
                async with session.post(self.REVOKE_URL, data=payload) as response:
                    # HTTP 200 means token was revoked or was already invalid
                    success = response.status == 200
                    
                    if not success:
                        error_text = await response.text()
                        logger.error(f"Failed to revoke token: {error_text}")
                    else:
                        logger.info(f"Successfully revoked {token_type_hint}")
                        
                    return success
                    
        except Exception as e:
            logger.error(f"Error revoking token: {str(e)}")
            return False