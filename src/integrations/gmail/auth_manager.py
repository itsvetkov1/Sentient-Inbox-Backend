"""
Enhanced Gmail Authentication Manager

Implements robust OAuth2 authentication management with comprehensive token
handling, automatic refresh, and secure storage following system specifications
from existing-infrastructure.md and error-handling.md.

Key Features:
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
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GmailAuthenticationManager:
    """
    Manages Gmail OAuth2 authentication with comprehensive token handling
    and secure storage mechanisms.
    """
    
    def __init__(self, 
                 token_path: str = 'token.json',
                 credentials_path: str = 'client_secret.json',
                 scopes: Optional[list] = None):
        """
        Initialize the authentication manager with configurable paths and scopes.
        
        Args:
            token_path: Path to token storage file
            credentials_path: Path to client secrets file
            scopes: List of required Gmail API scopes
        """
        self.token_path = Path(token_path)
        self.credentials_path = Path(credentials_path)
        self.scopes = scopes or [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify'
        ]
        
        # Configure secure storage
        self.token_dir = self.token_path.parent
        self.token_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize retry configuration
        self.max_retries = 1
        self.retry_delay = 3
        
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
            return self._authenticate_new()
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}", exc_info=True)
            return None

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
                logger.error(f"Refresh token expired or revoked: {str(e)}")
                self._handle_invalid_token()
                return self._authenticate_new()
                
            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(f"Refresh attempt {attempt + 1} failed: {str(e)}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("All refresh attempts failed")
                    self._handle_invalid_token()
                    return None

    def _authenticate_new(self) -> Optional[Credentials]:
        """
        Perform new OAuth2 authentication flow.
        
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
            if backup_path.exists():
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

    def create_gmail_service(self) -> Optional[Any]:
        """
        Create authenticated Gmail service with error handling.
        
        Returns:
            Gmail service object or None if service creation fails
        """
        try:
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