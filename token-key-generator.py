"""
Token Encryption Key Generator

Generates a secure encryption key for use with the TOKEN_ENCRYPTION_KEY
environment variable. This script creates a cryptographically secure
random key of appropriate length and outputs it in the correct format.

Usage:
    python generate_encryption_key.py

The generated key should be added to your .env file as:
    TOKEN_ENCRYPTION_KEY=<generated_key>
"""

import base64
import os
import secrets


def generate_encryption_key(key_length: int = 32) -> str:
    """
    Generate a cryptographically secure encryption key.
    
    Creates a random key of specified length using the secrets module
    for cryptographic security, then encodes it in URL-safe base64 format
    for use with Fernet symmetric encryption.
    
    Args:
        key_length: Length of the key in bytes (default: 32 bytes/256 bits)
        
    Returns:
        URL-safe base64 encoded key string
    """
    # Generate a cryptographically secure random key
    random_bytes = secrets.token_bytes(key_length)
    
    # Encode using URL-safe base64 encoding
    encoded_key = base64.urlsafe_b64encode(random_bytes).decode('utf-8')
    
    return encoded_key


if __name__ == "__main__":
    # Generate the key
    encryption_key = generate_encryption_key()
    
    print("\n=== Secure Encryption Key Generator ===\n")
    print(f"Generated key: {encryption_key}")
    print("\nAdd this key to your .env file as:")
    print(f"TOKEN_ENCRYPTION_KEY={encryption_key}")
    
    # Optional: write directly to .env file if it exists
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Check if TOKEN_ENCRYPTION_KEY already exists
        key_exists = False
        for i, line in enumerate(lines):
            if line.startswith("TOKEN_ENCRYPTION_KEY="):
                lines[i] = f"TOKEN_ENCRYPTION_KEY={encryption_key}\n"
                key_exists = True
                break
        
        # Add the key if it doesn't exist
        if not key_exists:
            lines.append(f"TOKEN_ENCRYPTION_KEY={encryption_key}\n")
        
        # Write the updated content
        with open(env_file, 'w') as f:
            f.writelines(lines)
        
        print(f"\nSuccessfully updated {env_file} with the new encryption key.")
    else:
        print(f"\nNote: {env_file} file not found. Please manually add the key to your environment variables.")
