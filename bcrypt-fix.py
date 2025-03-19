"""
Bcrypt Version Compatibility Module

This module addresses bcrypt version compatibility issues by providing
a standardized interface for password hashing operations regardless of
the installed bcrypt version. It handles the warning about missing
__about__ attribute in newer bcrypt versions.

Usage:
    from bcrypt_compatibility import hash_password, verify_password
    
    # Hash a password
    hashed = hash_password("secure_password")
    
    # Verify a password
    is_valid = verify_password("secure_password", hashed)
"""

import logging
import os
from typing import Union, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Import bcrypt while handling potential import errors
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    logger.warning("bcrypt module not found, falling back to placeholder implementation")
    BCRYPT_AVAILABLE = False


def get_bcrypt_version() -> Optional[str]:
    """
    Get the bcrypt version in a version-agnostic way.
    
    Handles different bcrypt package structures to retrieve the version
    without causing attribute errors.
    
    Returns:
        String version number or None if not available
    """
    if not BCRYPT_AVAILABLE:
        return None
        
    # Try different approaches to get the version
    try:
        # Modern bcrypt versions may have __version__
        if hasattr(bcrypt, "__version__"):
            return bcrypt.__version__
        
        # Older bcrypt versions might have __about__.__version__
        if hasattr(bcrypt, "__about__") and hasattr(bcrypt.__about__, "__version__"):
            return bcrypt.__about__.__version__
            
        # Some versions store it differently
        if hasattr(bcrypt, "_bcrypt") and hasattr(bcrypt._bcrypt, "__version__"):
            return bcrypt._bcrypt.__version__
            
        return "unknown"
        
    except Exception as e:
        logger.warning(f"Error determining bcrypt version: {e}")
        return "unknown"


def hash_password(password: str, rounds: int = 12) -> str:
    """
    Hash a password using bcrypt with version compatibility handling.
    
    Creates a secure password hash using bcrypt, handling different
    bcrypt versions and function signatures.
    
    Args:
        password: Plain text password to hash
        rounds: Number of rounds for bcrypt (default: 12)
        
    Returns:
        Hashed password string
    """
    if not BCRYPT_AVAILABLE:
        logger.warning("bcrypt not available, using placeholder hash (INSECURE)")
        return f"MOCK_HASH_{password}"
        
    # Ensure password is in bytes format
    if isinstance(password, str):
        password_bytes = password.encode('utf-8')
    else:
        password_bytes = password
        
    try:
        # Modern bcrypt interface
        salt = bcrypt.gensalt(rounds=rounds)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        raise


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a hash with version compatibility handling.
    
    Compares a plain text password against a bcrypt hash, handling
    different bcrypt versions and function signatures.
    
    Args:
        password: Plain text password to verify
        hashed: Hashed password to compare against
        
    Returns:
        Boolean indicating if password matches hash
    """
    if not BCRYPT_AVAILABLE:
        logger.warning("bcrypt not available, using placeholder verification (INSECURE)")
        return hashed == f"MOCK_HASH_{password}"
        
    # Ensure inputs are in correct format
    if isinstance(password, str):
        password_bytes = password.encode('utf-8')
    else:
        password_bytes = password
        
    if isinstance(hashed, str):
        hashed_bytes = hashed.encode('utf-8')
    else:
        hashed_bytes = hashed
        
    try:
        # Use bcrypt's checkpw function for comparison
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


# Print diagnostic information when module is imported
bcrypt_version = get_bcrypt_version()
logger.info(f"Bcrypt compatibility module initialized (version: {bcrypt_version})")

if __name__ == "__main__":
    # Run diagnostics if executed directly
    logging.basicConfig(level=logging.INFO)
    
    print(f"Bcrypt available: {BCRYPT_AVAILABLE}")
    print(f"Bcrypt version: {bcrypt_version}")
    
    # Test password hashing and verification
    if BCRYPT_AVAILABLE:
        test_password = "secure_test_password"
        hashed = hash_password(test_password)
        verified = verify_password(test_password, hashed)
        
        print(f"Password hashing test: {'Success' if verified else 'Failed'}")
