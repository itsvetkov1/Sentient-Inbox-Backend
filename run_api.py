"""
API Server Runner with OAuth Credential Management

Provides a comprehensive entry point for running the FastAPI server
with proper configuration, environment setup, and OAuth credential management.
This implementation ensures Google OAuth credentials are properly loaded
from client_secret.json before any OAuth-dependent components are initialized.

Design Considerations:
- Robust credential loading with comprehensive error handling
- Early environment setup to ensure proper configuration
- Directory structure validation and creation
- Detailed logging for operational visibility
- Graceful error management and reporting
"""

import argparse
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api_runner")
credentials_logger = logging.getLogger("oauth_credentials")

def parse_arguments():
    """Parse command line arguments for the API server with comprehensive validation."""
    parser = argparse.ArgumentParser(description="Run the Email Management API server")
    
    parser.add_argument(
        "--host", 
        type=str, 
        default="127.0.0.1", 
        help="Host to bind the server to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to bind the server to (default: 8000)"
    )
    
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="Enable auto-reload for development"
    )
    
    parser.add_argument(
        "--env", 
        type=str, 
        choices=["development", "testing", "production"],
        default="development",
        help="Environment to run in (default: development)"
    )
    
    parser.add_argument(
        "--credentials", 
        type=str, 
        default="client_secret.json",
        help="Path to Google OAuth credentials file (default: client_secret.json)"
    )
    
    return parser.parse_args()

def setup_environment(env):
    """
    Set up comprehensive environment variables and directory structure.
    
    Configures environment variables based on deployment context and ensures
    all required directories exist with proper permissions. Implements
    comprehensive logging for operational visibility.
    
    Args:
        env: Environment name (development, testing, production)
    """
    os.environ["ENVIRONMENT"] = env
    
    # Set debug mode for development and testing
    if env in ["development", "testing"]:
        os.environ["DEBUG"] = "true"
    else:
        os.environ["DEBUG"] = "false"
    
    # Ensure required directories exist with proper structure
    required_dirs = [
        "data/config",
        "data/metrics",
        "data/secure",
        "data/secure/backups",
        "data/cache",
        "logs"
    ]
    
    for directory in required_dirs:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")

def load_google_oauth_credentials(credentials_path: str = "client_secret.json") -> bool:
    """
    Load Google OAuth credentials from file with comprehensive error handling.
    
    Reads the client_secret.json file and sets appropriate environment variables
    to ensure OAuth providers can access the credentials. Implements detailed
    validation and error handling for operational reliability.
    
    Args:
        credentials_path: Path to the OAuth credentials file
        
    Returns:
        bool: True if credentials were successfully loaded, False otherwise
    """
    try:
        # Check current environment variables first
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        
        if client_id and client_secret:
            credentials_logger.info("Google OAuth credentials already present in environment")
            # Show partial IDs for verification without exposing full credentials
            masked_id = client_id[:5] + "..." + client_id[-5:] if len(client_id) > 10 else "***"
            masked_secret = client_secret[:3] + "..." if client_secret else "***"
            credentials_logger.info(f"Using GOOGLE_CLIENT_ID: {masked_id}")
            credentials_logger.info(f"Using GOOGLE_CLIENT_SECRET: {masked_secret}")
            return True
            
        # Environment variables not set, attempt to load from file
        credentials_logger.info(f"Attempting to load OAuth credentials from: {credentials_path}")
        
        # Verify file existence
        if not os.path.exists(credentials_path):
            credentials_logger.error(f"Credentials file not found: {credentials_path}")
            credentials_logger.error("Google OAuth features will not work without valid credentials")
            # List current directory contents to help with troubleshooting
            dir_contents = [f for f in os.listdir('.') if os.path.isfile(f)]
            credentials_logger.info(f"Current directory contains these files: {dir_contents}")
            return False
            
        # Read and parse credentials file
        with open(credentials_path, 'r') as file:
            try:
                credentials = json.load(file)
                credentials_logger.info("Successfully loaded OAuth credentials JSON")
            except json.JSONDecodeError as e:
                credentials_logger.error(f"Invalid JSON in credentials file: {e}")
                return False
                
        # Validate credentials format and extract configuration
        if 'web' in credentials:
            credentials_logger.info("Found 'web' application credentials")
            os.environ["GOOGLE_CLIENT_ID"] = credentials['web']['client_id']
            os.environ["GOOGLE_CLIENT_SECRET"] = credentials['web']['client_secret']
            
            # Log masked values for verification
            client_id = credentials['web']['client_id']
            client_secret = credentials['web']['client_secret']
            masked_id = client_id[:5] + "..." + client_id[-5:] if len(client_id) > 10 else "***"
            masked_secret = client_secret[:3] + "..." if client_secret else "***"
            
            credentials_logger.info(f"Set GOOGLE_CLIENT_ID: {masked_id}")
            credentials_logger.info(f"Set GOOGLE_CLIENT_SECRET: {masked_secret}")
            return True
            
        elif 'installed' in credentials:
            credentials_logger.info("Found 'installed' application credentials")
            os.environ["GOOGLE_CLIENT_ID"] = credentials['installed']['client_id']
            os.environ["GOOGLE_CLIENT_SECRET"] = credentials['installed']['client_secret']
            
            # Log masked values for verification
            client_id = credentials['installed']['client_id']
            client_secret = credentials['installed']['client_secret']
            masked_id = client_id[:5] + "..." + client_id[-5:] if len(client_id) > 10 else "***"
            masked_secret = client_secret[:3] + "..." if client_secret else "***"
            
            credentials_logger.info(f"Set GOOGLE_CLIENT_ID: {masked_id}")
            credentials_logger.info(f"Set GOOGLE_CLIENT_SECRET: {masked_secret}")
            return True
            
        else:
            credentials_logger.error(f"Unrecognized credentials format. Found keys: {list(credentials.keys())}")
            credentials_logger.error("Expected 'web' or 'installed' as the top-level key")
            return False
            
    except Exception as e:
        credentials_logger.error(f"Error loading Google OAuth credentials: {str(e)}")
        credentials_logger.error(traceback.format_exc())
        return False

def verify_oauth_environment():
    """
    Verify OAuth environment configuration and log issues.
    
    Performs comprehensive verification of OAuth-related environment variables
    and logs detailed information for operational visibility and troubleshooting.
    """
    credentials_logger.info("Verifying OAuth environment configuration...")
    
    # Check required variables
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    if client_id and client_secret:
        credentials_logger.info("✅ OAuth environment verified: Credentials are properly configured")
        
        # Show partial values for verification
        masked_id = client_id[:5] + "..." + client_id[-5:] if len(client_id) > 10 else "***"
        masked_secret = client_secret[:3] + "..." if client_secret else "***"
        credentials_logger.info(f"   GOOGLE_CLIENT_ID: {masked_id}")
        credentials_logger.info(f"   GOOGLE_CLIENT_SECRET: {masked_secret}")
    else:
        missing = []
        if not client_id:
            missing.append("GOOGLE_CLIENT_ID")
        if not client_secret:
            missing.append("GOOGLE_CLIENT_SECRET")
            
        credentials_logger.error(f"❌ OAuth environment verification failed: Missing {', '.join(missing)}")
        credentials_logger.error("Google OAuth functionality will not work properly")

def main():
    """
    Run the API server with comprehensive initialization and configuration.
    
    Implements complete server lifecycle management including:
    - Command-line argument parsing and validation
    - Environment setup and directory structure verification
    - OAuth credential loading and validation
    - Server configuration and startup with proper error handling
    """
    # Parse command-line arguments
    args = parse_arguments()
    
    # Setup environment and directory structure
    setup_environment(args.env)
    
    # Load OAuth credentials before any server components initialize
    credentials_logger.info("=== LOADING GOOGLE OAUTH CREDENTIALS ===")
    success = load_google_oauth_credentials(args.credentials)
    
    if success:
        credentials_logger.info("=== GOOGLE OAUTH CREDENTIALS LOADED SUCCESSFULLY ===")
    else:
        credentials_logger.error("=== FAILED TO LOAD GOOGLE OAUTH CREDENTIALS ===")
        credentials_logger.warning("OAuth authentication features will not work properly")
    
    # Verify OAuth environment configuration
    verify_oauth_environment()
    
    # Log server startup information
    logger.info(f"Starting API server in {args.env} mode")
    logger.info(f"Server will be available at http://{args.host}:{args.port}")
    
    if args.env == "development":
        logger.info(f"API documentation will be available at http://{args.host}:{args.port}/docs")
    
    # Run the server with the specified configuration
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info" if args.env == "production" else "debug"
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)