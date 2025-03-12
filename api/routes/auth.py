"""
Authentication API Routes with Multi-Provider OAuth Support

Implements comprehensive authentication endpoints with proper
security practices, validation, error handling, and multi-provider
OAuth integration for Gmail and Outlook access.

Design Considerations:
- Robust token generation and validation
- Multi-provider OAuth authorization flow
- Comprehensive input validation
- Proper error handling and logging
- Clear response formats
"""

import os
import logging
from datetime import timedelta
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, JSONResponse

from api.auth.service import AuthenticationService, get_auth_service
from api.models.auth import (
    Token, UserCredentials, UserLoginResponse, 
    OAuthLoginRequest, OAuthCallbackRequest, OAuthLoginResponse,
    OAuthCallbackResponse, User, AvailableProvidersResponse
)
from api.config import get_settings
from src.auth.oauth_factory import OAuthProviderFactory
from src.storage.user_repository import UserRepository
from src.storage.database import init_db

auth_service = get_auth_service()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Authentication"])

# Initialize database on startup
init_db()

@router.post(
    "/token",
    response_model=Token,
    summary="OAuth2 token endpoint"
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Generate access token from username and password.
    
    Standard OAuth2 token endpoint for password-based authentication
    with proper token generation and security validation.
    
    Args:
        form_data: OAuth2 form with username and password
        
    Returns:
        Token response with access token
        
    Raises:
        HTTPException: If authentication fails
    """
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"Failed authentication attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token with appropriate expiration
    settings = get_settings()
    access_token_expires = timedelta(minutes=settings.JWT_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"username": user["username"], "permissions": user["permissions"]},
        expires_delta=access_token_expires,
    )
    
    logger.info(f"Access token generated for user: {user['username']}")
    
    return Token(
        access_token=access_token, 
        token_type="bearer",
        expires_in=settings.JWT_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )

@router.get(
    "/oauth/providers",
    response_model=AvailableProvidersResponse,
    summary="Get available OAuth providers"
)
async def get_available_providers():
    """
    Get list of available OAuth providers for login.
    
    Returns a list of available OAuth providers that can be used
    for authentication with their display names.
    
    Returns:
        Dictionary of provider codes to display names
    """
    providers = OAuthProviderFactory.get_available_providers()
    return AvailableProvidersResponse(providers=providers)

@router.post(
    "/oauth/login",
    response_model=OAuthLoginResponse,
    summary="Initiate OAuth login flow"
)
async def oauth_login(
    request: OAuthLoginRequest,
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Initiate OAuth login flow for specified provider.
    
    Generates an authorization URL for the specified OAuth provider
    that the client should redirect the user to for authorization.
    
    Args:
        request: OAuth login request with provider and redirect URI
        
    Returns:
        Authorization URL and state for the OAuth flow
        
    Raises:
        HTTPException: If provider is not supported or configuration is invalid
    """
    try:
        authorization_url, state = await auth_service.get_authorization_url(
            request.provider, 
            request.redirect_uri
        )
        
        logger.info(f"Generated OAuth authorization URL for provider: {request.provider}")
        
        return OAuthLoginResponse(
            authorization_url=authorization_url,
            state=state
        )
        
    except ValueError as e:
        logger.error(f"Error generating OAuth login URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in OAuth login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate OAuth login"
        )

@router.post(
    "/oauth/callback",
    response_model=OAuthCallbackResponse,
    summary="Handle OAuth callback"
)
async def oauth_callback(
    request: OAuthCallbackRequest,
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Process OAuth callback after user authorization.
    
    Exchanges the authorization code for access and refresh tokens,
    creates or updates the user in the database, and returns a JWT token
    for API authentication.
    
    Args:
        request: OAuth callback request with code and state
        
    Returns:
        User information and JWT access token
        
    Raises:
        HTTPException: If OAuth callback processing fails
    """
    try:
        # Process OAuth callback
        result = await auth_service.process_oauth_callback(
            request.provider,
            request.code,
            request.redirect_uri
        )
        
        # Extract user and token information
        user_dict = result["user"]
        user = User(
            id=user_dict["id"],
            username=user_dict["username"],
            email=user_dict["email"],
            display_name=user_dict.get("display_name"),
            permissions=user_dict["permissions"],
            profile_picture=user_dict.get("profile_picture"),
            is_active=user_dict.get("is_active", True),
            created_at=user_dict["created_at"],
            last_login=user_dict.get("last_login"),
            oauth_providers=user_dict.get("oauth_providers", [])
        )
        
        logger.info(f"Successfully processed OAuth callback for user: {user.username}")
        
        return OAuthCallbackResponse(
            user=user,
            access_token=result["access_token"],
            token_type=result["token_type"],
            expires_in=result["expires_in"]
        )
        
    except ValueError as e:
        logger.error(f"Error processing OAuth callback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in OAuth callback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process OAuth callback"
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
    user = await auth_service.authenticate_user(
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

@router.get(
    "/me",
    response_model=User,
    summary="Get current user information"
)
async def get_current_user(
    auth_service: AuthenticationService = Depends(get_auth_service),
    user: Dict[str, Any] = Depends(auth_service.get_current_user)
):
    """
    Get current authenticated user information.
    
    Returns comprehensive profile information for the currently
    authenticated user with OAuth provider details.
    
    Args:
        user: Current authenticated user from JWT token
        
    Returns:
        User profile information
    """
    # Convert raw user dictionary to User model
    return User(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        display_name=user.get("display_name"),
        permissions=user["permissions"],
        profile_picture=user.get("profile_picture"),
        is_active=user.get("is_active", True),
        created_at=user["created_at"],
        last_login=user.get("last_login"),
        oauth_providers=user.get("oauth_providers", [])
    )

@router.get(
    "/oauth/redirect/{provider}",
    summary="OAuth redirect shortcut"
)
async def oauth_redirect(
    provider: str,
    redirect_uri: str = Query(...),
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Redirect user to OAuth provider authorization page.
    
    Convenience endpoint for redirecting users directly to the
    OAuth authorization page without a client-side redirect.
    
    Args:
        provider: OAuth provider name
        redirect_uri: URI to redirect after authorization
        
    Returns:
        Redirect to OAuth provider authorization page
    """
    try:
        authorization_url, state = await auth_service.get_authorization_url(
            provider, 
            redirect_uri
        )
        
        logger.info(f"Redirecting to {provider} OAuth authorization page")
        return RedirectResponse(url=authorization_url)
        
    except Exception as e:
        logger.error(f"Error in OAuth redirect: {str(e)}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=400
        )