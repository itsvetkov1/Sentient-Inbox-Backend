"""
Authentication API Routes

Implements comprehensive authentication endpoints with proper
security practices, validation, and error handling.

Design Considerations:
- Robust token generation and validation
- Comprehensive input validation
- Proper error handling and logging
- Clear response formats
"""

import logging
from datetime import timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.auth.service import AuthenticationService, get_auth_service
from api.models.auth import Token, UserCredentials, UserLoginResponse
from api.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Authentication"])


@router.post(
    "/token",
    response_model=Token,
    summary="Generate access token"
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Generate JWT access token for authenticated user.
    
    Implements OAuth2 password flow for API authentication with
    comprehensive validation, error handling, and token generation.
    
    Args:
        form_data: OAuth2 form with username and password
        
    Returns:
        Token response with access token
        
    Raises:
        HTTPException: If authentication fails
    """
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        logger.warning(f"Failed authentication attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Calculate token expiration
    settings = get_settings()
    access_token_expires = timedelta(minutes=settings.JWT_TOKEN_EXPIRE_MINUTES)
    
    # Create access token with proper claims
    access_token = auth_service.create_access_token(
        data={
            "username": user["username"],
            "permissions": user["permissions"]
        },
        expires_delta=access_token_expires,
    )
    
    logger.info(f"Generated access token for user: {user['username']}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )


@router.post(
    "/login",
    response_model=UserLoginResponse,
    summary="User login endpoint"
)
async def login(
    credentials: UserCredentials,
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Login user and return authentication details.
    
    Provides enhanced login endpoint with comprehensive user details
    and proper authentication handling with detailed responses.
    
    Args:
        credentials: User login credentials
        
    Returns:
        User login response with token and permissions
        
    Raises:
        HTTPException: If authentication fails
    """
    user = auth_service.authenticate_user(
        credentials.username, 
        credentials.password.get_secret_value()
    )
    
    if not user:
        logger.warning(f"Failed login attempt for user: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Calculate token expiration
    settings = get_settings()
    access_token_expires = timedelta(minutes=settings.JWT_TOKEN_EXPIRE_MINUTES)
    
    # Create access token with proper claims
    access_token = auth_service.create_access_token(
        data={
            "username": user["username"],
            "permissions": user["permissions"]
        },
        expires_delta=access_token_expires,
    )
    
    # Create token response
    token = Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )
    
    logger.info(f"User successfully logged in: {user['username']}")
    
    return UserLoginResponse(
        token=token,
        username=user["username"],
        permissions=user["permissions"]
    )