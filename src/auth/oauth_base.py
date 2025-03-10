"""
Base OAuth Provider Service

Defines the abstract base class for OAuth provider implementations with
standardized interface and comprehensive error handling.

Design Considerations:
- Provider-agnostic abstract interface
- Comprehensive error handling
- Standardized token management
- Common OAuth flow patterns
- Detailed logging for troubleshooting
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

class OAuthProvider(ABC):
    """
    Abstract base class for OAuth provider implementations.
    
    Defines the standard interface that all OAuth provider implementations
    must follow, ensuring consistent behavior across different providers.
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this OAuth provider."""
        pass
    
    @abstractmethod
    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate the authorization URL for the OAuth flow.
        
        Args:
            redirect_uri: URL to redirect to after authorization
            state: Optional state parameter for security
            
        Returns:
            Tuple containing (authorization_url, state)
        """
        pass
    
    @abstractmethod
    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from OAuth provider
            redirect_uri: Redirect URI used in authorization request
            
        Returns:
            Dictionary containing token information
        """
        pass
    
    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: Refresh token to use
            
        Returns:
            Dictionary containing new token information
        """
        pass
    
    @abstractmethod
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Retrieve user information using the access token.
        
        Args:
            access_token: OAuth access token
            
        Returns:
            Dictionary containing user profile information
        """
        pass
    
    @abstractmethod
    async def validate_token(self, access_token: str) -> bool:
        """
        Validate if an access token is still valid.
        
        Args:
            access_token: OAuth access token to validate
            
        Returns:
            Boolean indicating if token is valid
        """
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str, token_type_hint: str = "access_token") -> bool:
        """
        Revoke an access or refresh token.
        
        Args:
            token: Token to revoke
            token_type_hint: Type of token ('access_token' or 'refresh_token')
            
        Returns:
            Boolean indicating if revocation was successful
        """
        pass