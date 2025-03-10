"""
Authentication API Routes with Google OAuth Support

Implements comprehensive authentication endpoints with proper
security practices, validation, error handling, and Google OAuth
integration for Gmail access.

Design Considerations:
- Robust token generation and validation
- Google OAuth authorization flow
- Comprehensive input validation
- Proper error handling and logging
- Clear response formats
"""

import logging
from datetime import timedelta
from typing import Dict, Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, JSONResponse

from api.auth.service import AuthenticationService, get_auth_service
from api.models.auth import Token, UserCredentials, UserLoginResponse, GoogleAuthRequest, GoogleCallbackRequest
from api.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Authentication"])

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
    user = auth_service.authenticate_user(form_data.username, form_data.password)
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

@router.post(
    "/google-auth",
    response_model=Token,
    summary="Authenticate with Google OAuth"
)
async def google_auth(
    token_data: GoogleAuthRequest,
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Authenticate user with Google OAuth token.
    
    Verifies Google ID token, creates or updates user record,
    and generates system JWT token for authenticated user.
    
    Args:
        token_data: Google authentication data including ID token
        
    Returns:
        JWT token response with access token
    """
    try:
        # Verify Google ID token with Google's API
        google_user_info = await auth_service.verify_google_token(token_data.id_token)
        
        if not google_user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get or create user from Google information
        user = await auth_service.get_or_create_google_user(google_user_info)
        
        # Create access token
        settings = get_settings()
        access_token_expires = timedelta(minutes=settings.JWT_TOKEN_EXPIRE_MINUTES)
        access_token = auth_service.create_access_token(
            data={
                "username": user["username"],
                "permissions": user["permissions"]
            },
            expires_delta=access_token_expires,
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.JWT_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
        )
        
    except Exception as e:
        logger.error(f"Google authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get(
    "/google-login",
    summary="Initiate Google OAuth login flow"
)
async def google_login(auth_service: AuthenticationService = Depends(get_auth_service)):
    """
    Initiate Google OAuth login flow for Gmail access.
    
    Redirects the user to the Google authorization page with
    appropriate scopes for Gmail access. This is the endpoint
    that the "Login with Google" button should link to.
    
    Returns:
        Redirect to Google authorization page
    """
    try:
        # Generate authorization URL with appropriate scopes
        auth_url = auth_service.get_google_auth_url()
        
        # Redirect to Google authorization page
        return RedirectResponse(auth_url)
        
    except Exception as e:
        logger.error(f"Error initiating Google login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate Google login"
        )

@router.get(
    "/google-callback",
    summary="Handle Google OAuth callback"
)
async def google_callback(
    request: Request,
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Handle Google OAuth callback after user authorization.
    
    Processes the authorization code from Google, exchanges it for
    access and refresh tokens, and creates a user session.
    
    Args:
        request: Request object containing authorization code
        
    Returns:
        Redirect to frontend with authentication information
    """
    try:
        # Extract authorization code from query parameters
        code = request.query_params.get("code")
        error = request.query_params.get("error")
        
        if error:
            logger.error(f"Google OAuth error: {error}")
            return JSONResponse(
                content={"status": "error", "message": f"Google OAuth error: {error}"},
                status_code=400
            )
        
        if not code:
            logger.error("No authorization code provided")
            return JSONResponse(
                content={"status": "error", "message": "No authorization code provided"},
                status_code=400
            )
        
        # Exchange code for tokens
        tokens = await auth_service.exchange_code_for_tokens(code)
        if not tokens:
            logger.error("Failed to exchange code for tokens")
            return JSONResponse(
                content={"status": "error", "message": "Failed to exchange code for tokens"},
                status_code=400
            )
        
        # Extract ID token from tokens response
        id_token = tokens.get("id_token")
        if not id_token:
            logger.error("No ID token in response")
            return JSONResponse(
                content={"status": "error", "message": "No ID token in response"},
                status_code=400
            )
        
        # Verify ID token and get user info
        google_user_info = await auth_service.verify_google_token(id_token)
        if not google_user_info:
            logger.error("Failed to verify ID token")
            return JSONResponse(
                content={"status": "error", "message": "Failed to verify ID token"},
                status_code=400
            )
        
        # Get or create user
        user = await auth_service.get_or_create_google_user(google_user_info)
        
        # Create system access token
        settings = get_settings()
        access_token_expires = timedelta(minutes=settings.JWT_TOKEN_EXPIRE_MINUTES)
        access_token = auth_service.create_access_token(
            data={
                "username": user["username"],
                "permissions": user["permissions"]
            },
            expires_delta=access_token_expires,
        )
        
        # Store Gmail tokens in user session
        # In a real implementation, these would be stored in a secure database
        # associated with the user
        user["gmail_tokens"] = {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type")
        }
        
        # Redirect back to frontend with token
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        redirect_url = f"{frontend_url}/auth/callback?token={access_token}"
        
        return RedirectResponse(redirect_url)
        
    except Exception as e:
        logger.error(f"Error processing Google callback: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500
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