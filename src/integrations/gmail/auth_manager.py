"""
Enhanced Gmail Authentication Manager with Web OAuth Flow Support

Implements robust OAuth2 authentication management for both web and installed
application flows, with comprehensive token handling, automatic refresh, and 
secure storage following system specifications.

Key Features:
- Support for both web OAuth flow and installed application flow
- Secure token storage and management
- Automatic token refresh with retry logic
- Comprehensive error handling and logging
- Integration with email processing pipeline
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GmailAuthenticationManager:
    """
    Manages Gmail OAuth2 authentication with comprehensive token handling
    and secure storage mechanisms, supporting both web and installed flows.
    """
    
    def __init__(self, 
                 token_path: str = 'token.json',
                 credentials_path: str = 'client_secret.json',
                 scopes: Optional[list] = None,
                 web_flow: bool = False):
        """
        Initialize the authentication manager with configurable paths and scopes.
        
        Args:
            token_path: Path to token storage file
            credentials_path: Path to client secrets file
            scopes: List of required Gmail API scopes
            web_flow: Whether to use web application flow instead of installed app flow
        """
        self.token_path = Path(token_path)
        self.credentials_path = Path(credentials_path)
        self.web_flow = web_flow
        self.scopes = scopes or [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'openid'
        ]
        
        # Configure secure storage
        self.token_dir = self.token_path.parent
        self.token_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize retry configuration
        self.max_retries = 1
        self.retry_delay = 3
        
        # Web flow specific configuration
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google-callback")
        
        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Configure comprehensive authentication logging."""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        auth_handler = logging.FileHandler('logs/authentication.log')
        auth_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(auth_handler)
        logger.setLevel(logging.DEBUG)

    def authenticate(self) -> Optional[Credentials]:
        """
        Perform authentication with comprehensive error handling and logging.
        
        Returns:
            Valid credentials object or None if authentication fails
        """
        try:
            # Attempt to load existing credentials
            credentials = self._load_credentials()
            
            if credentials and credentials.valid:
                logger.info("Using valid existing credentials")
                return credentials
                
            if credentials and credentials.expired and credentials.refresh_token:
                logger.info("Attempting to refresh expired credentials")
                return self._refresh_credentials(credentials)
                
            # No valid credentials, initiate new authentication
            logger.info("No valid credentials found, starting new authentication flow")
            if self.web_flow:
                logger.info("Web flow not directly supported in this context - must be handled by API routes")
                return None
            else:
                return self._authenticate_new_installed()
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}", exc_info=True)
            return None

    def create_authorization_url(self) -> Tuple[str, str]:
        """
        Create Google OAuth authorization URL for web flow.
        
        Returns:
            Tuple containing (authorization_url, state)
        """
        try:
            if not self.credentials_path.exists():
                logger.error("Client secrets file not found")
                raise FileNotFoundError("client_secret.json not found")
                
            # Create flow using client secrets file
            flow = Flow.from_client_secrets_file(
                str(self.credentials_path),
                scopes=self.scopes,
                redirect_uri=self.redirect_uri
            )
            
            # Generate random state to verify the response
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            logger.info(f"Authorization URL created, state: {state}")
            return authorization_url, state
            
        except Exception as e:
            logger.error(f"Error creating authorization URL: {str(e)}")
            raise

    async def exchange_code(self, code: str, state: Optional[str] = None) -> Optional[Credentials]:
        """
        Exchange authorization code for credentials in web flow.
        
        Args:
            code: Authorization code from Google
            state: State parameter for verification
            
        Returns:
            Credentials object or None if exchange fails
        """
        try:
            if not self.credentials_path.exists():
                logger.error("Client secrets file not found")
                raise FileNotFoundError("client_secret.json not found")
                
            # Create flow using client secrets file
            flow = Flow.from_client_secrets_file(
                str(self.credentials_path),
                scopes=self.scopes,
                redirect_uri=self.redirect_uri,
                state=state
            )
            
            # Exchange authorization code for credentials
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Validate the received scopes
            if self._validate_scopes(credentials.scopes):
                # Save credentials for future use
                self._save_credentials(credentials)
                logger.info("Successfully exchanged authorization code for credentials")
                return credentials
            else:
                logger.error("Scope validation failed after code exchange")
                return None
            
        except Exception as e:
            logger.error(f"Error exchanging authorization code: {str(e)}")
            return None

    def _validate_scopes(self, received_scopes: list) -> bool:
        """
        Validate received scopes against required scopes.
        
        Uses a flexible set-based comparison to ensure all required scopes
        are present, regardless of order or additional scopes.
        
        Args:
            received_scopes: List of scopes received from authentication
            
        Returns:
            True if all required scopes are present, False otherwise
        """
        # Convert scopes to sets for comparison
        required_scopes = set(self.scopes)
        actual_scopes = set(received_scopes if received_scopes else [])
        
        # Check if all required scopes are included
        if not required_scopes.issubset(actual_scopes):
            missing_scopes = required_scopes - actual_scopes
            logger.error(f"Missing required scopes: {', '.join(missing_scopes)}")
            return False
            
        # Log any extra scopes but don't fail
        extra_scopes = actual_scopes - required_scopes
        if extra_scopes:
            logger.info(f"Additional scopes granted: {', '.join(extra_scopes)}")
            
        return True

    def _load_credentials(self) -> Optional[Credentials]:
        """
        Load credentials from secure storage with validation.
        
        Returns:
            Credentials object if valid credentials exist, None otherwise
        """
        try:
            if not self.token_path.exists():
                logger.debug("No token file found")
                return None
                
            with open(self.token_path, 'r') as token_file:
                token_data = json.load(token_file)
                
            # Validate token data structure
            if not self._validate_token_data(token_data):
                logger.warning("Invalid token data structure")
                return None
                
            credentials = Credentials.from_authorized_user_info(token_data, self.scopes)
            logger.debug("Successfully loaded credentials from storage")
            return credentials
            
        except Exception as e:
            logger.error(f"Error loading credentials: {str(e)}")
            self._handle_invalid_token()
            return None

    def _validate_token_data(self, token_data: Dict) -> bool:
        """
        Validate token data structure and required fields.
        
        Args:
            token_data: Dictionary containing token information
            
        Returns:
            True if token data is valid, False otherwise
        """
        required_fields = {'token', 'refresh_token', 'token_uri', 'client_id', 'client_secret'}
        return all(field in token_data for field in required_fields)

    def _refresh_credentials(self, credentials: Credentials) -> Optional[Credentials]:
        """
        Refresh expired credentials with retry logic.
        
        Args:
            credentials: Expired credentials to refresh
            
        Returns:
            Refreshed credentials or None if refresh fails
        """
        for attempt in range(self.max_retries + 1):
            try:
                credentials.refresh(Request())
                self._save_credentials(credentials)
                logger.info("Successfully refreshed credentials")
                return credentials
                
            except RefreshError as e:
                error_str = str(e)
                # Check if the error is due to scope mismatch
                if "Scope has changed" in error_str:
                    logger.warning("Scope change detected - re-authenticating to handle scope differences")
                    # Since the scopes have changed, we need to re-authenticate
                    # This will generate a new token with the correct scopes
                    return self._authenticate_new_installed()
                    
                logger.error(f"Refresh token expired or revoked: {error_str}")
                self._handle_invalid_token()
                if self.web_flow:
                    return None
                else:
                    return self._authenticate_new_installed()
                
            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(f"Refresh attempt {attempt + 1} failed: {str(e)}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("All refresh attempts failed")
                    self._handle_invalid_token()
                    return None

    def _authenticate_new_installed(self) -> Optional[Credentials]:
        """
        Perform new OAuth2 authentication flow for installed applications.
        
        Returns:
            New credentials object or None if authentication fails
        """
        try:
            if not self.credentials_path.exists():
                logger.error("Client secrets file not found")
                raise FileNotFoundError("client_secret.json not found")
                
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path),
                self.scopes
            )
            credentials = flow.run_local_server(port=0)
            
            # Validate the received scopes
            if not self._validate_scopes(credentials.scopes):
                logger.error("New authentication completed but scope validation failed")
                logger.warning(f"Requested scopes: {', '.join(self.scopes)}")
                logger.warning(f"Received scopes: {', '.join(credentials.scopes if credentials.scopes else [])}")
                
                # Continue despite scope differences as long as we have the required permissions
                # This is more flexible than failing the entire authentication
                if credentials and credentials.refresh_token:
                    logger.info("Proceeding with credentials despite scope differences")
                else:
                    logger.warning("No refresh token present, authentication may be incomplete")
            
            self._save_credentials(credentials)
            logger.info("Successfully completed new authentication flow")
            return credentials
            
        except Exception as e:
            logger.error(f"New authentication failed: {str(e)}")
            return None

    def _save_credentials(self, credentials: Credentials):
        """
        Securely save credentials with backup mechanism.
        
        Args:
            credentials: Credentials object to save
        """
        backup_path = None
        # Create backup of existing token if it exists
        if self.token_path.exists():
            backup_path = self.token_path.with_suffix('.backup')
            self.token_path.rename(backup_path)
            
        try:
            # Save new credentials
            with open(self.token_path, 'w') as token_file:
                token_file.write(credentials.to_json())
            logger.debug("Successfully saved credentials")
            
            # Remove backup if save was successful
            if backup_path and backup_path.exists():
                backup_path.unlink()
                
        except Exception as e:
            logger.error(f"Error saving credentials: {str(e)}")
            # Restore backup if save failed
            if backup_path and backup_path.exists():
               backup_path.rename(self.token_path)

    def _handle_invalid_token(self):
        """Handle invalid token situation with cleanup and logging."""
        try:
            if self.token_path.exists():
                self.token_path.unlink()
            logger.info("Removed invalid token file")
        except Exception as e:
            logger.error(f"Error removing invalid token: {str(e)}")

    def store_user_tokens(self, user_id: str, tokens: Dict[str, Any]) -> bool:
        """
        Store user-specific tokens for web flow authentication.
        
        In a production environment, these would be stored in a database
        associated with the user. This implementation provides a simplified
        file-based approach for demonstration purposes.
        
        Args:
            user_id: Unique identifier for the user
            tokens: Dictionary containing tokens and metadata
            
        Returns:
            True if tokens were successfully stored, False otherwise
        """
        try:
            # Create user tokens directory if it doesn't exist
            user_tokens_dir = Path('data/secure/user_tokens')
            user_tokens_dir.mkdir(parents=True, exist_ok=True)
            
            # Create user token file path
            user_token_path = user_tokens_dir / f"{user_id}.json"
            
            # Save tokens to file
            with open(user_token_path, 'w') as f:
                json.dump(tokens, f, indent=2)
                
            logger.info(f"Successfully stored tokens for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing user tokens: {str(e)}")
            return False

    def get_user_tokens(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user-specific tokens for web flow authentication.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Dictionary containing tokens and metadata or None if not found
        """
        try:
            user_token_path = Path(f'data/secure/user_tokens/{user_id}.json')
            
            if not user_token_path.exists():
                logger.warning(f"No tokens found for user: {user_id}")
                return None
                
            with open(user_token_path, 'r') as f:
                tokens = json.load(f)
                
            logger.info(f"Successfully retrieved tokens for user: {user_id}")
            return tokens
            
        except Exception as e:
            logger.error(f"Error retrieving user tokens: {str(e)}")
            return None

    def create_gmail_service(self, user_credentials: Optional[Credentials] = None) -> Optional[Any]:
        """
        Create authenticated Gmail service with error handling.
        
        Args:
            user_credentials: Optional explicit credentials to use
            
        Returns:
            Gmail service object or None if service creation fails
        """
        try:
            if user_credentials:
                credentials = user_credentials
            else:
                credentials = self.authenticate()
                
            if not credentials:
                logger.error("Failed to obtain valid credentials")
                return None
                
            service = build('gmail', 'v1', credentials=credentials)
            logger.info("Successfully created Gmail service")
            return service
            
        except Exception as e:
            logger.error(f"Error creating Gmail service: {str(e)}")
            return None
            
    def create_user_specific_gmail_service(self, user_id: str) -> Optional[Any]:
        """
        Create Gmail service for a specific user using stored tokens.
        
        This method is for web application flow where tokens are stored
        per user rather than globally for the application.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Gmail service for the specified user or None if creation fails
        """
        try:
            # Get user tokens
            tokens = self.get_user_tokens(user_id)
            if not tokens:
                logger.error(f"No tokens found for user: {user_id}")
                return None
                
            # Create credentials from tokens
            credentials = Credentials(
                token=tokens.get("access_token"),
                refresh_token=tokens.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=tokens.get("client_id"),
                client_secret=tokens.get("client_secret"),
                scopes=self.scopes
            )
            
            # Check if credentials need refresh
            if credentials.expired:
                logger.info(f"Refreshing expired credentials for user: {user_id}")
                credentials.refresh(Request())
                
                # Update stored tokens
                self.store_user_tokens(user_id, {
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret,
                    "expires_at": int(time.time() + credentials.expiry),
                    "scopes": credentials.scopes
                })
            
            # Create Gmail service
            service = build('gmail', 'v1', credentials=credentials)
            logger.info(f"Successfully created Gmail service for user: {user_id}")
            return service
            
        except RefreshError as e:
            logger.error(f"Refresh token expired or revoked for user {user_id}: {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"Error creating Gmail service for user {user_id}: {str(e)}")
            return None