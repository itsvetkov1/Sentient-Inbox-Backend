"""
OAuth Configuration Diagnostic Tool

This script diagnoses issues with Google OAuth credential configuration.
It verifies environment variables and attempts to locate and validate
the client_secret.json file using the same logic as the application.

Usage:
    python oauth_diagnostic.py
"""

import os
import sys
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("oauth-diagnostic")

def check_environment_variables():
    """
    Check if required OAuth environment variables are set.
    
    Verifies both GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are
    available in the environment and logs their status.
    
    Returns:
        bool: True if both variables are set, False otherwise
    """
    logger.info("=== Checking Environment Variables ===")
    
    # Check for client ID
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if client_id:
        logger.info("✅ GOOGLE_CLIENT_ID is set")
        # Show a few characters for verification, hiding most of it
        masked_id = client_id[:5] + "..." + client_id[-5:] if len(client_id) > 10 else "***"
        logger.info(f"   Value starts with: {masked_id}")
    else:
        logger.error("❌ GOOGLE_CLIENT_ID is NOT set")
    
    # Check for client secret
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if client_secret:
        logger.info("✅ GOOGLE_CLIENT_SECRET is set")
        # Show only first few characters for security
        masked_secret = client_secret[:3] + "..." if client_secret else "None"
        logger.info(f"   Value starts with: {masked_secret}")
    else:
        logger.error("❌ GOOGLE_CLIENT_SECRET is NOT set")
    
    return bool(client_id and client_secret)

def find_client_secret_file():
    """
    Search for client_secret.json in various common locations.
    
    Uses the same search logic as GoogleOAuthProvider._load_credentials_from_file()
    to find the credentials file and verify its content structure.
    
    Returns:
        tuple: (found_path, client_id, client_secret) or (None, None, None) if not found
    """
    logger.info("=== Searching for client_secret.json ===")
    
    # Get the current directory and project root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    script_dir = os.path.dirname(os.path.realpath(__file__))
    
    # Define potential locations to search
    potential_paths = [
        "client_secret.json",  # Current working directory
        os.path.join(current_dir, "client_secret.json"),  # Script directory
        os.path.join(script_dir, "client_secret.json"),  # Script directory (alternative)
        os.path.join(project_root, "client_secret.json"),  # Project root
        os.path.join(os.path.expanduser("~"), "client_secret.json"),  # User home
    ]
    
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Script directory: {script_dir}")
    logger.info(f"Potential project root: {project_root}")
    
    logger.info("Searching in the following locations:")
    for path in potential_paths:
        logger.info(f" - {os.path.abspath(path)}")
    
    # Search each location
    for path in potential_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            logger.info(f"✅ Found file at: {abs_path}")
            
            # Check file permissions
            try:
                # Verify we can read the file
                with open(abs_path, 'r') as file:
                    try:
                        credentials = json.load(file)
                        logger.info("✅ File contains valid JSON")
                        
                        # Extract credentials based on file structure
                        client_id = None
                        client_secret = None
                        
                        if 'web' in credentials:
                            logger.info("✅ Found 'web' credentials structure")
                            client_id = credentials['web'].get('client_id')
                            client_secret = credentials['web'].get('client_secret')
                        elif 'installed' in credentials:
                            logger.info("✅ Found 'installed' credentials structure")
                            client_id = credentials['installed'].get('client_id')
                            client_secret = credentials['installed'].get('client_secret')
                        else:
                            logger.error(f"❌ Unknown credentials structure. Available keys: {list(credentials.keys())}")
                            continue
                        
                        # Verify credentials exist
                        if client_id and client_secret:
                            logger.info("✅ Found valid credentials in file")
                            # Show partial values for verification
                            masked_id = client_id[:5] + "..." + client_id[-5:] if len(client_id) > 10 else "***"
                            masked_secret = client_secret[:3] + "..." if client_secret else "None"
                            logger.info(f"   Client ID: {masked_id}")
                            logger.info(f"   Client Secret: {masked_secret}")
                            return abs_path, client_id, client_secret
                        else:
                            logger.error("❌ Missing client_id or client_secret in file")
                    except json.JSONDecodeError:
                        logger.error(f"❌ File contains invalid JSON: {abs_path}")
            except PermissionError:
                logger.error(f"❌ Permission denied reading file: {abs_path}")
            except Exception as e:
                logger.error(f"❌ Error reading file {abs_path}: {str(e)}")
        else:
            logger.info(f"❌ File not found at: {abs_path}")
    
    logger.error("❌ Could not find a valid client_secret.json file")
    return None, None, None

def verify_credentials_usable():
    """
    Verify that credentials from either source can be used.
    
    Checks both environment variables and client_secret.json to determine
    if valid credentials are available from either source.
    
    Returns:
        bool: True if usable credentials are found, False otherwise
    """
    env_configured = check_environment_variables()
    file_path, file_client_id, file_client_secret = find_client_secret_file()
    
    if env_configured:
        logger.info("✅ Environment variables are properly configured")
        return True
    elif file_path and file_client_id and file_client_secret:
        logger.info(f"✅ Valid credentials found in: {file_path}")
        logger.info("⚠️ Environment variables are NOT set, but file credentials can be used")
        return True
    else:
        logger.error("❌ No usable credentials found from any source")
        return False

def suggest_solutions(env_vars_present, file_credentials_found):
    """
    Suggest solutions based on diagnostic results.
    
    Args:
        env_vars_present: Whether environment variables are set
        file_credentials_found: Whether file credentials are found
    """
    logger.info("=== Suggested Solutions ===")
    
    if not env_vars_present and not file_credentials_found:
        logger.info("1. Create a client_secret.json file from Google Cloud Console:")
        logger.info("   - Go to https://console.cloud.google.com/")
        logger.info("   - Navigate to APIs & Services > Credentials")
        logger.info("   - Create an OAuth client ID credential")
        logger.info("   - Download the JSON file and save as client_secret.json in project root")
        logger.info("")
        logger.info("2. Set environment variables:")
        logger.info("   - Add to .env file:")
        logger.info("     GOOGLE_CLIENT_ID=your_client_id_here")
        logger.info("     GOOGLE_CLIENT_SECRET=your_client_secret_here")
        logger.info("   - Or set directly in your environment/deployment system")
    elif file_credentials_found and not env_vars_present:
        logger.info("Your client_secret.json file appears valid, but environment variables are not set.")
        logger.info("You have two options:")
        logger.info("")
        logger.info("1. Let the application use the file (may require path adjustments):")
        logger.info("   - Ensure the file is in the correct location")
        logger.info("   - Verify file permissions allow the application to read it")
        logger.info("")
        logger.info("2. Set environment variables from file contents:")
        logger.info("   - Add to .env file or set directly in environment")
    elif env_vars_present and not file_credentials_found:
        logger.info("Environment variables are set, but application may be configured to prefer file.")
        logger.info("Verify that the application's OAuth provider factory is properly loading from environment.")
    
    logger.info("")
    logger.info("For environment variables, you can add this to your startup script:")
    logger.info("""
    import os
    import json
    
    def load_google_credentials():
        try:
            # Specify the exact path to your credentials file
            credentials_path = "client_secret.json"  # Update this to your exact path
            
            # Check if file exists
            if not os.path.exists(credentials_path):
                print(f"ERROR: Credentials file not found at {credentials_path}")
                return
                
            with open(credentials_path, 'r') as file:
                credentials = json.load(file)
                
            # Extract and set environment variables
            if 'web' in credentials:
                os.environ["GOOGLE_CLIENT_ID"] = credentials['web']['client_id']
                os.environ["GOOGLE_CLIENT_SECRET"] = credentials['web']['client_secret']
            elif 'installed' in credentials:
                os.environ["GOOGLE_CLIENT_ID"] = credentials['installed']['client_id']
                os.environ["GOOGLE_CLIENT_SECRET"] = credentials['installed']['client_secret']
                
        except Exception as e:
            print(f"Error loading Google credentials: {e}")
    
    # Call this function before OAuth initialization
    load_google_credentials()
    """)

if __name__ == "__main__":
    print("=== OAuth Configuration Diagnostic Tool ===")
    print("This tool will diagnose issues with Google OAuth credentials configuration.")
    print("")
    
    # Run diagnostics
    env_vars_present = check_environment_variables()
    file_path, _, _ = find_client_secret_file()
    
    print("\n=== Diagnostic Summary ===")
    if env_vars_present:
        print("✅ Environment variables: CONFIGURED")
    else:
        print("❌ Environment variables: MISSING")
    
    if file_path:
        print(f"✅ Client secret file: FOUND at {file_path}")
    else:
        print("❌ Client secret file: NOT FOUND")
    
    # Verify overall usability
    credentials_usable = verify_credentials_usable()
    
    # Suggest solutions
    suggest_solutions(env_vars_present, bool(file_path))
    
    # Exit with status code
    sys.exit(0 if credentials_usable else 1)
