"""
Authentication Data Models

Defines comprehensive data models for authentication operations
including token generation, validation, and user credential management.

Design Considerations:
- Proper data validation and constraints
- Type safety with comprehensive annotations
- Clear documentation of data requirements
- Security-focused constraints
"""

from datetime import datetime
from typing import List, Optional
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