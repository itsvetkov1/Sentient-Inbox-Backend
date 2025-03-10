"""
Authentication Data Models with OAuth Support

Defines comprehensive data models for authentication operations
including token generation, validation, user credential management,
and OAuth authentication for multiple providers.

Design Considerations:
- Proper data validation and constraints
- Type safety with comprehensive annotations
- Clear documentation of data requirements
- Security-focused constraints
- Support for multiple OAuth providers
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator, SecretStr


class Token(BaseModel):
    """
    JWT token response model with comprehensive metadata.
    
    Provides structured representation of authentication token
    with relevant expiration and type information.
    """
    access_token: str = Field(
        ...,
        description="JWT access token for API authentication"
    )
    token_type: str = Field(
        ...,
        description="Token type, typically 'bearer'"
    )
    expires_in: int = Field(
        ...,
        description="Token expiration time in seconds"
    )


class TokenData(BaseModel):
    """
    Decoded token data model with user and permission information.
    
    Maintains structured representation of token contents with
    comprehensive user context and permission details.
    """
    username: str = Field(
        ...,
        description="Username identifier"
    )
    permissions: List[str] = Field(
        default=[],
        description="List of permissions granted to the user"
    )
    exp: int = Field(
        ...,
        description="Token expiration timestamp"
    )
    
    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: List[str]) -> List[str]:
        """Validate permissions contain only allowed values."""
        valid_permissions = {"admin", "process", "view"}
        if not all(perm in valid_permissions for perm in value):
            raise ValueError(f"Permissions must be one of: {', '.join(valid_permissions)}")
        return value


class UserCredentials(BaseModel):
    """
    User credentials model for authentication validation.
    
    Implements comprehensive validation for login credentials
    with proper security constraints and format validation.
    """
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username for authentication"
    )
    password: SecretStr = Field(
        ...,
        min_length=8,
        description="Password for authentication"
    )
    
    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, value: str) -> str:
        """Validate username contains only allowed characters."""
        if not value.isalnum():
            raise ValueError("Username must only contain alphanumeric characters")
        return value


class UserLoginResponse(BaseModel):
    """
    Comprehensive user login response with authentication details.
    
    Provides token information and basic user context for the client.
    """
    token: Token = Field(
        ...,
        description="Authentication token details"
    )
    username: str = Field(
        ...,
        description="Authenticated username"
    )
    permissions: List[str] = Field(
        ...,
        description="User permissions"
    )


class GoogleAuthRequest(BaseModel):
    """
    Google authentication request model with ID token.
    
    Contains the ID token returned from Google's OAuth flow
    for verification and user authentication.
    """
    id_token: str = Field(
        ...,
        description="Google OAuth ID token"
    )


class GoogleCallbackRequest(BaseModel):
    """
    Google OAuth callback request model.
    
    Contains the authorization code returned from Google's OAuth
    flow for exchanging with access and refresh tokens.
    """
    code: str = Field(
        ...,
        description="Google OAuth authorization code"
    )
    state: Optional[str] = Field(
        None,
        description="State parameter for security verification"
    )


class OAuthLoginRequest(BaseModel):
    """
    OAuth login request model.
    
    Contains the provider name for initiating the OAuth flow.
    """
    provider: str = Field(
        ...,
        description="OAuth provider name (e.g., 'google', 'microsoft')"
    )
    redirect_uri: str = Field(
        ...,
        description="URI to redirect to after authentication"
    )


class OAuthCallbackRequest(BaseModel):
    """
    OAuth callback request model.
    
    Contains the provider name, authorization code, and optional state
    for processing the OAuth callback.
    """
    provider: str = Field(
        ...,
        description="OAuth provider name (e.g., 'google', 'microsoft')"
    )
    code: str = Field(
        ...,
        description="OAuth authorization code"
    )
    state: Optional[str] = Field(
        None,
        description="State parameter for security verification"
    )
    redirect_uri: str = Field(
        ...,
        description="URI used in authorization request"
    )


class OAuthUserInfo(BaseModel):
    """
    User information from OAuth provider.
    
    Contains user profile information from the OAuth provider.
    """
    provider: str = Field(
        ...,
        description="OAuth provider name"
    )
    provider_user_id: str = Field(
        ...,
        description="Provider-specific user ID"
    )
    email: EmailStr = Field(
        ...,
        description="User email address"
    )
    name: Optional[str] = Field(
        None,
        description="User display name"
    )
    picture: Optional[str] = Field(
        None,
        description="URL to user profile picture"
    )
    

class User(BaseModel):
    """
    User model with comprehensive profile information.
    
    Contains user profile details, permissions, and OAuth provider
    information.
    """
    id: str = Field(
        ...,
        description="Unique user identifier"
    )
    username: str = Field(
        ...,
        description="Unique username"
    )
    email: EmailStr = Field(
        ...,
        description="User email address"
    )
    display_name: Optional[str] = Field(
        None,
        description="User display name"
    )
    permissions: List[str] = Field(
        ...,
        description="User permissions"
    )
    profile_picture: Optional[str] = Field(
        None,
        description="URL to user profile picture"
    )
    is_active: bool = Field(
        ...,
        description="Whether the user is active"
    )
    created_at: str = Field(
        ...,
        description="User creation timestamp"
    )
    last_login: Optional[str] = Field(
        None,
        description="Last login timestamp"
    )
    oauth_providers: List[str] = Field(
        default=[],
        description="List of linked OAuth providers"
    )


class OAuthLoginResponse(BaseModel):
    """
    OAuth login response model.
    
    Contains the authorization URL for the OAuth flow.
    """
    authorization_url: str = Field(
        ...,
        description="URL to redirect the user to for OAuth authorization"
    )
    state: str = Field(
        ...,
        description="State parameter for security verification"
    )
    

class OAuthCallbackResponse(BaseModel):
    """
    OAuth callback response model.
    
    Contains the user information and access token after successful
    OAuth authentication.
    """
    user: User = Field(
        ...,
        description="User information"
    )
    access_token: str = Field(
        ...,
        description="JWT access token"
    )
    token_type: str = Field(
        ...,
        description="Token type, typically 'bearer'"
    )
    expires_in: int = Field(
        ...,
        description="Token expiration time in seconds"
    )


class AvailableProvidersResponse(BaseModel):
    """
    Available OAuth providers response model.
    
    Contains the list of available OAuth providers for login.
    """
    providers: Dict[str, str] = Field(
        ...,
        description="Mapping of provider codes to display names"
    )