import os
import json
import logging
from pathlib import Path

# Configure logging
logger = logging.getLogger("credentials_loader")

def load_google_credentials():
    """
    Load Google OAuth credentials from client_secret.json.
    
    This function reads credentials from the file and sets them
    as environment variables for OAuth providers to use.
    """
    try:
        # Print current working directory to help with path issues
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Specify the exact path to your credentials file
        credentials_path = "client_secret.json"
        logger.info(f"Attempting to load credentials from: {credentials_path}")
        
        # Check if file exists
        if not os.path.exists(credentials_path):
            logger.error(f"ERROR: Credentials file not found at {credentials_path}")
            return False
            
        with open(credentials_path, 'r') as file:
            credentials = json.load(file)
            logger.info("Successfully loaded JSON file")
            
        # Log the structure to verify it contains what we expect
        logger.info(f"JSON structure keys: {list(credentials.keys())}")
            
        # Extract and set environment variables
        if 'web' in credentials:
            logger.info("Found 'web' configuration in credentials")
            os.environ["GOOGLE_CLIENT_ID"] = credentials['web']['client_id']
            os.environ["GOOGLE_CLIENT_SECRET"] = credentials['web']['client_secret']
            logger.info(f"Set GOOGLE_CLIENT_ID: {os.environ.get('GOOGLE_CLIENT_ID')[:5]}...")
            logger.info(f"Set GOOGLE_CLIENT_SECRET: {os.environ.get('GOOGLE_CLIENT_SECRET')[:5]}...")
            return True
        elif 'installed' in credentials:
            logger.info("Found 'installed' configuration in credentials")
            os.environ["GOOGLE_CLIENT_ID"] = credentials['installed']['client_id']
            os.environ["GOOGLE_CLIENT_SECRET"] = credentials['installed']['client_secret']
            logger.info(f"Set GOOGLE_CLIENT_ID: {os.environ.get('GOOGLE_CLIENT_ID')[:5]}...")
            logger.info(f"Set GOOGLE_CLIENT_SECRET: {os.environ.get('GOOGLE_CLIENT_SECRET')[:5]}...")
            return True
        else:
            logger.error(f"WARNING: Unrecognized credentials format. Available keys: {list(credentials.keys())}")
            return False
            
    except Exception as e:
        logger.error(f"Error loading Google credentials: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False