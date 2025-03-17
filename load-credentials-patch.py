"""
Google Credentials Loading Patch

This module provides an enhanced implementation for loading Google OAuth
credentials from either environment variables or a client_secret.json file.
It implements robust error handling and detailed logging for diagnostic purposes.

Usage:
    1. Place this file in your project
    2. Import and call load_google_credentials() before OAuth initialization
"""

import os
import json
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict

# Configure logging
logger = logging.getLogger(__name__)

def load_google_credentials(verbose: bool = True) -> Tuple[bool, Optional[Dict]]:
    """
    Load Google OAuth credentials from client_secret.json or environment.
    
    This function implements a robust credential loading mechanism that:
    1. Checks for existing environment variables first
    2. Searches for client_secret.json in multiple locations
    3. Extracts and sets environment variables from the file if found
    4. Provides detailed logging for troubleshooting
    
    Args:
        verbose: Whether to print detailed status messages
    
    Returns:
        Tuple containing:
        - Success indicator (bool)
        - Credential information dictionary or None if not found
    """
    # Check if environment variables are already set
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    if client_id and client_secret:
        if verbose:
            logger.info("Google OAuth credentials already present in environment variables")
            # Log partial values for verification
            masked_id = client_id[:5] + "..." + client_id[-5:] if len(client_id) > 10 else "***"
            masked_secret = client_secret[:3] + "..." if client_secret else "None"
            logger.info(f"Client ID: {masked_id}")
        return True, {
            "source": "environment",
            "client_id": client_id,
            "client_secret": client_secret
        }
    
    # Environment variables not set, search for the credentials file
    if verbose:
        logger.info("Google OAuth credentials not found in environment, searching for client_secret.json")
    
    # Define potential paths to search
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = Path(current_dir).parent
    
    potential_paths = [
        "client_secret.json",                              # Current working directory
        os.path.join(current_dir, "client_secret.json"),   # Module directory
        os.path.join(project_root, "client_secret.json"),  # Project root
        os.path.join(os.path.expanduser("~"), "client_secret.json")  # User home
    ]
    
    # Search for the file in potential locations
    credentials_file = None
    for path in potential_paths:
        if os.path.exists(path):
            credentials_file = path
            if verbose:
                logger.info(f"Found credentials file at: {path}")
            break
    
    if not credentials_file:
        if verbose:
            logger.error("Google OAuth credentials not found in environment or file system")
        return False, None
    
    # Read credentials from file
    try:
        with open(credentials_file, 'r') as f:
            credentials = json.load(f)
            
        # Extract client ID and secret based on credentials format
        if 'web' in credentials:
            client_id = credentials['web']['client_id']
            client_secret = credentials['web']['client_secret']
            cred_type = 'web'
        elif 'installed' in credentials:
            client_id = credentials['web']['client_id']
            client_secret = credentials['web']['client_secret']
            cred_type = 'installed'
        else:
            if verbose:
                logger.error(f"Unrecognized credentials format. Available keys: {list(credentials.keys())}")
            return False, None
            
        # Ensure we have both values
        if not client_id or not client_secret:
            if verbose:
                logger.error("Client ID or Client Secret missing in credentials file")
            return False, None
            
        # Set environment variables
        os.environ["GOOGLE_CLIENT_ID"] = client_id
        os.environ["GOOGLE_CLIENT_SECRET"] = client_secret
        
        if verbose:
            logger.info(f"Successfully loaded Google {cred_type} credentials from {credentials_file}")
            logger.info("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables")
        
        return True, {
            "source": "file",
            "file_path": credentials_file,
            "client_id": client_id,
            "client_secret": client_secret,
            "type": cred_type
        }
        
    except json.JSONDecodeError:
        if verbose:
            logger.error(f"Invalid JSON in credentials file: {credentials_file}")
        return False, None
    except KeyError as e:
        if verbose:
            logger.error(f"Missing key in credentials file: {e}")
        return False, None
    except Exception as e:
        if verbose:
            logger.error(f"Error loading credentials file: {str(e)}")
        return False, None

# Example usage for testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success, creds = load_google_credentials()
    if success:
        print(f"Successfully loaded credentials from {creds['source']}")
    else:
        print("Failed to load credentials")
