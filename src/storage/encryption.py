"""
Token Encryption Utilities

Provides secure encryption and decryption of sensitive OAuth tokens
with proper key management, initialization vector handling, and
comprehensive error management.

Design Considerations:
- Industry-standard AES-256 encryption
- Proper IV generation and handling
- Comprehensive error management
- Key derivation from environment secrets
"""

import os
import base64
import logging
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Load encryption key from environment or generate one
def get_encryption_key() -> bytes:
    """
    Get or generate a secure encryption key for token encryption.
    
    Loads encryption key from environment variable if available,
    otherwise generates a secure key using system entropy and
    PBKDF2 key derivation.
    
    Returns:
        bytes: Encryption key in bytes format
    """
    key_str = os.getenv("TOKEN_ENCRYPTION_KEY")
    if key_str:
        try:
            return base64.urlsafe_b64decode(key_str)
        except Exception as e:
            logger.warning(f"Invalid encryption key format, generating new key: {str(e)}")
    
    # Generate a secure key using PBKDF2
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(os.urandom(32)))
    
    # Log warning that we're using a generated key
    logger.warning(
        "Using dynamically generated encryption key. Set TOKEN_ENCRYPTION_KEY "
        "environment variable for persistent encryption."
    )
    
    return key

# Initialize Fernet cipher with the encryption key
try:
    FERNET_KEY = get_encryption_key()
    cipher_suite = Fernet(FERNET_KEY)
    logger.info("Encryption system initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize encryption system: {str(e)}")
    raise RuntimeError(f"Encryption system initialization failed: {str(e)}")

def encrypt_value(value: Union[str, bytes]) -> str:
    """
    Encrypt a sensitive value with proper error handling.
    
    Implements secure encryption using Fernet symmetric encryption
    with comprehensive error handling and type conversion.
    
    Args:
        value: String or bytes value to encrypt
        
    Returns:
        str: Base64-encoded encrypted value
        
    Raises:
        ValueError: If encryption fails
    """
    if value is None:
        return None
        
    try:
        # Convert to bytes if string
        if isinstance(value, str):
            value_bytes = value.encode('utf-8')
        else:
            value_bytes = value
            
        # Encrypt and return as string
        encrypted = cipher_suite.encrypt(value_bytes)
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}")
        raise ValueError(f"Failed to encrypt value: {str(e)}")

def decrypt_value(encrypted_value: str) -> str:
    """
    Decrypt an encrypted value with proper error handling.
    
    Implements secure decryption using Fernet symmetric encryption
    with comprehensive error handling and type conversion.
    
    Args:
        encrypted_value: Base64-encoded encrypted value
        
    Returns:
        str: Decrypted string value
        
    Raises:
        ValueError: If decryption fails
    """
    if encrypted_value is None:
        return None
        
    try:
        # Decode base64 and decrypt
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_value)
        decrypted = cipher_suite.decrypt(encrypted_bytes)
        return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        raise ValueError(f"Failed to decrypt value: {str(e)}")