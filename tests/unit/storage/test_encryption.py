"""
Unit tests for storage encryption utilities.

These tests validate the security and functionality of the encryption module,
including key derivation, encryption, decryption and error handling.
"""

import os
import base64
import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet

from src.storage.encryption import (
    get_encryption_key,
    encrypt_value,
    decrypt_value,
)


class TestEncryption:
    """
    Test suite for the encryption module.
    
    Tests the encryption functionality including key management,
    value encryption/decryption, and proper error handling.
    """
    
    def test_get_encryption_key_from_env(self):
        """Test retrieving encryption key from environment variable."""
        test_key = Fernet.generate_key()
        test_key_str = base64.urlsafe_b64encode(test_key).decode()
        
        with patch.dict(os.environ, {"TOKEN_ENCRYPTION_KEY": test_key_str}):
            result = get_encryption_key()
            assert result == test_key
    
    def test_get_encryption_key_generates_new(self):
        """Test generating a new encryption key when not in environment."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.urandom', return_value=b'x' * 32):
                result = get_encryption_key()
                assert isinstance(result, bytes)
                assert len(result) > 0
    
    def test_get_encryption_key_handles_invalid_env(self):
        """Test handling invalid environment key value."""
        with patch.dict(os.environ, {"TOKEN_ENCRYPTION_KEY": "invalid_base64"}):
            with patch('os.urandom', return_value=b'x' * 32):
                result = get_encryption_key()
                assert isinstance(result, bytes)
                assert len(result) > 0
    
    @patch('src.storage.encryption.cipher_suite')
    def test_encrypt_value_string_input(self, mock_cipher):
        """Test encrypting string values."""
        mock_cipher.encrypt.return_value = b'encrypted_value'
        
        result = encrypt_value('test_value')
        
        mock_cipher.encrypt.assert_called_once()
        assert isinstance(result, str)
        assert base64.urlsafe_b64decode(result) == b'encrypted_value'
    
    @patch('src.storage.encryption.cipher_suite')
    def test_encrypt_value_bytes_input(self, mock_cipher):
        """Test encrypting bytes values."""
        mock_cipher.encrypt.return_value = b'encrypted_bytes'
        
        result = encrypt_value(b'test_bytes')
        
        mock_cipher.encrypt.assert_called_once_with(b'test_bytes')
        assert isinstance(result, str)
    
    @patch('src.storage.encryption.cipher_suite')
    def test_encrypt_value_none_input(self, mock_cipher):
        """Test encrypting None values."""
        mock_cipher.encrypt.return_value = b'encrypted_value'
        
        result = encrypt_value(None)
        
        mock_cipher.encrypt.assert_not_called()
        assert result is None
    
    @patch('src.storage.encryption.cipher_suite')
    def test_encrypt_value_error_handling(self, mock_cipher):
        """Test error handling during encryption."""
        mock_cipher.encrypt.side_effect = Exception("Encryption error")
        
        with pytest.raises(ValueError) as excinfo:
            encrypt_value('test_value')
        
        assert "Failed to encrypt value" in str(excinfo.value)
    
    @patch('src.storage.encryption.cipher_suite')
    def test_decrypt_value(self, mock_cipher):
        """Test decrypting values."""
        mock_cipher.decrypt.return_value = b'decrypted_value'
        
        # Create base64 encoded test value
        test_encrypted = base64.urlsafe_b64encode(b'test_encrypted').decode()
        
        result = decrypt_value(test_encrypted)
        
        mock_cipher.decrypt.assert_called_once_with(b'test_encrypted')
        assert result == 'decrypted_value'
    
    @patch('src.storage.encryption.cipher_suite')
    def test_decrypt_value_none_input(self, mock_cipher):
        """Test decrypting None values."""
        result = decrypt_value(None)
        
        mock_cipher.decrypt.assert_not_called()
        assert result is None
    
    @patch('src.storage.encryption.cipher_suite')
    def test_decrypt_value_error_handling(self, mock_cipher):
        """Test error handling during decryption."""
        mock_cipher.decrypt.side_effect = Exception("Decryption error")
        
        test_encrypted = base64.urlsafe_b64encode(b'test_encrypted').decode()
        
        with pytest.raises(ValueError) as excinfo:
            decrypt_value(test_encrypted)
        
        assert "Failed to decrypt value" in str(excinfo.value)
    
    def test_end_to_end_encryption_decryption(self):
        """Test end-to-end encryption and decryption process."""
        # Create a test value
        test_value = "sensitive data"
        
        # Use the real functions (not mocked)
        with patch('src.storage.encryption.cipher_suite', Fernet(Fernet.generate_key())):
            # Encrypt the value
            encrypted = encrypt_value(test_value)
            
            # Make sure it's encrypted (different from original)
            assert encrypted != test_value
            assert isinstance(encrypted, str)
            
            # Decrypt the value
            decrypted = decrypt_value(encrypted)
            
            # Verify we got back the original value
            assert decrypted == test_value
