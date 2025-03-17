"""
Unit tests for SecureStorage functionality.

These tests verify the secure storage features including key management,
encryption/decryption, record management, and recovery mechanisms.
"""

import os
import json
import base64
import pytest
import asyncio
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
from pathlib import Path
from cryptography.fernet import Fernet

from src.storage.secure import SecureStorage


class TestSecureStorage:
    """Test suite for SecureStorage class functionality."""
    
    @pytest.fixture
    def mock_fernet(self):
        """Create a mock Fernet instance for testing."""
        mock = MagicMock()
        mock.encrypt.side_effect = lambda data: b"encrypted_" + (data if isinstance(data, bytes) else data.encode())
        mock.decrypt.side_effect = lambda data: b"decrypted_data"
        return mock
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create a temporary directory for storage testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up after tests
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def secure_storage(self, temp_storage_path, mock_fernet):
        """Create a SecureStorage instance with mocked encryption for testing."""
        with patch('src.storage.secure.Fernet', return_value=mock_fernet):
            storage = SecureStorage(storage_path=temp_storage_path)
            storage.cipher_suite = mock_fernet
            return storage
    
    def test_init_creates_directories(self, temp_storage_path):
        """Test that initialization creates necessary directories."""
        with patch('src.storage.secure.Fernet'):
            storage = SecureStorage(storage_path=temp_storage_path)
            
            # Verify directories were created
            assert Path(temp_storage_path).exists()
            assert (Path(temp_storage_path) / "backups").exists()
    
    def test_init_creates_new_storage_if_needed(self, temp_storage_path, mock_fernet):
        """Test initialization creates a new storage file if none exists."""
        with patch('src.storage.secure.Fernet', return_value=mock_fernet):
            with patch.object(SecureStorage, '_write_encrypted_data') as mock_write:
                storage = SecureStorage(storage_path=temp_storage_path)
                
                # Verify _write_encrypted_data was called with initial empty structure
                mock_write.assert_called_once()
                data = mock_write.call_args[0][0]
                assert "records" in data
                assert "metadata" in data
                assert len(data["records"]) == 0
    
    def test_generate_secure_key(self, secure_storage):
        """Test generation of secure encryption keys."""
        with patch('os.urandom', return_value=b'x' * 32):
            key = secure_storage._generate_secure_key()
            assert isinstance(key, bytes)
            assert len(key) > 0
    
    def test_generate_secure_key_with_entropy(self, secure_storage):
        """Test key generation with additional entropy."""
        with patch('os.urandom', return_value=b'x' * 32):
            key1 = secure_storage._generate_secure_key()
            key2 = secure_storage._generate_secure_key(extra_entropy=b'extra')
            
            # Keys should be different with different entropy
            assert key1 != key2
    
    def test_generate_record_id(self, secure_storage):
        """Test generation of unique record IDs."""
        record1 = {"message_id": "msg1", "timestamp": "2023-01-01T12:00:00"}
        record2 = {"message_id": "msg2", "timestamp": "2023-01-01T12:00:00"}
        
        id1 = secure_storage._generate_record_id(record1)
        id2 = secure_storage._generate_record_id(record2)
        
        # IDs should be strings of correct length
        assert isinstance(id1, str)
        assert len(id1) == 32
        
        # Different records should have different IDs
        assert id1 != id2
        
        # Same record should always have same ID (deterministic)
        id1_again = secure_storage._generate_record_id(record1)
        assert id1 == id1_again
    
    def test_initialize_keys_new(self, temp_storage_path):
        """Test initialization of keys when no previous keys exist."""
        keys_path = Path(temp_storage_path) / "key_history.bin"
        
        with patch('os.urandom', return_value=b'x' * 32):
            with patch('src.storage.secure.Fernet'):
                storage = SecureStorage(storage_path=temp_storage_path)
                
                # Key file should have been created
                assert keys_path.exists()
                
                # Read the key file to verify format
                with open(keys_path, 'r') as f:
                    key_data = json.load(f)
                    assert "keys" in key_data
                    assert isinstance(key_data["keys"], list)
                    assert len(key_data["keys"]) > 0
    
    def test_initialize_keys_existing(self, temp_storage_path):
        """Test loading existing keys during initialization."""
        keys_path = Path(temp_storage_path) / "key_history.bin"
        
        # Create a key file before initializing
        test_key = base64.urlsafe_b64encode(b'test_key_data').decode()
        os.makedirs(temp_storage_path, exist_ok=True)
        with open(keys_path, 'w') as f:
            json.dump({"keys": [test_key]}, f)
        
        with patch('src.storage.secure.Fernet'):
            storage = SecureStorage(storage_path=temp_storage_path)
            
            # The test key should have been loaded
            assert len(storage.keys) == 1
            assert storage.keys[0] == b'test_key_data'
    
    def test_initialize_keys_error_recovery(self, temp_storage_path):
        """Test recovery from key initialization errors."""
        keys_path = Path(temp_storage_path) / "key_history.bin"
        
        # Create an invalid key file
        os.makedirs(temp_storage_path, exist_ok=True)
        with open(keys_path, 'w') as f:
            f.write("invalid json")
        
        with patch('src.storage.secure.Fernet'):
            with patch('os.urandom', return_value=b'x' * 32):
                storage = SecureStorage(storage_path=temp_storage_path)
                
                # Should recover by generating a new key
                assert len(storage.keys) == 1
    
    def test_save_keys(self, secure_storage):
        """Test saving encryption keys."""
        test_keys = [b'key1', b'key2']
        
        with patch('builtins.open', mock_open()) as mock_file:
            result = secure_storage._save_keys(test_keys)
            
            assert result is True
            mock_file.assert_called_once()
            
            # Verify the written data
            write_data = mock_file().write.call_args[0][0]
            data = json.loads(write_data)
            assert "keys" in data
            assert len(data["keys"]) == 2
    
    def test_save_keys_error_handling(self, secure_storage):
        """Test error handling during key saving."""
        with patch('builtins.open', side_effect=Exception("Write error")):
            result = secure_storage._save_keys([b'key1'])
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_read_encrypted_data_new_file(self, secure_storage):
        """Test reading encrypted data when file doesn't exist."""
        with patch.object(Path, 'exists', return_value=False):
            data = await secure_storage._read_encrypted_data()
            
            assert "records" in data
            assert "metadata" in data
            assert len(data["records"]) == 0
    
    @pytest.mark.asyncio
    async def test_read_encrypted_data_empty_file(self, secure_storage):
        """Test reading encrypted data from an empty file."""
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=b'')):
                data = await secure_storage._read_encrypted_data()
                
                assert "records" in data
                assert "metadata" in data
                assert len(data["records"]) == 0
    
    @pytest.mark.asyncio
    async def test_read_encrypted_data_valid_file(self, secure_storage, mock_fernet):
        """Test reading and decrypting data from a valid file."""
        # Setup mock encrypted data
        mock_data = {"records": [{"id": "test1"}], "metadata": {"data_version": 1}}
        encrypted_data = b"encrypted_data"
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=encrypted_data)):
                with patch.object(mock_fernet, 'decrypt', return_value=json.dumps(mock_data).encode()):
                    data = await secure_storage._read_encrypted_data()
                    
                    assert data == mock_data
    
    @pytest.mark.asyncio
    async def test_read_encrypted_data_decryption_failures(self, secure_storage, mock_fernet):
        """Test handling decryption failures with multiple keys."""
        encrypted_data = b"encrypted_data"
        
        # First key fails, second key works
        secure_storage.keys = [b'key1', b'key2']
        secure_storage.current_key = b'key1'
        
        # Setup mock to fail on first key, succeed on second
        side_effects = [
            Exception("Decryption error"),  # First key fails
            json.dumps({"records": [], "metadata": {"data_version": 1}}).encode()  # Second key works
        ]
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=encrypted_data)):
                with patch.object(Fernet, '__call__') as mock_fernet_init:
                    # Create mocks for each Fernet instance
                    fernet1 = MagicMock()
                    fernet1.decrypt.side_effect = side_effects[0]
                    
                    fernet2 = MagicMock()
                    fernet2.decrypt.return_value = side_effects[1]
                    
                    mock_fernet_init.side_effect = [fernet1, fernet2]
                    
                    # Mock _write_encrypted_data since we'll reencrypt with current key
                    with patch.object(secure_storage, '_write_encrypted_data', return_value=True):
                        data = await secure_storage._read_encrypted_data()
                        
                        # Should have valid data structure even after first key fails
                        assert "records" in data
                        assert "metadata" in data
    
    @pytest.mark.asyncio
    async def test_read_encrypted_data_all_keys_fail(self, secure_storage, mock_fernet):
        """Test handling when all decryption keys fail."""
        encrypted_data = b"encrypted_data"
        
        # Setup both keys to fail
        secure_storage.keys = [b'key1', b'key2']
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=encrypted_data)):
                with patch.object(Fernet, '__call__') as mock_fernet_init:
                    # Create mocks for each Fernet instance to fail
                    fernet1 = MagicMock()
                    fernet1.decrypt.side_effect = Exception("Key 1 fail")
                    
                    fernet2 = MagicMock()
                    fernet2.decrypt.side_effect = Exception("Key 2 fail")
                    
                    mock_fernet_init.side_effect = [fernet1, fernet2]
                    
                    # Mock restore attempt (fails)
                    with patch.object(secure_storage, '_restore_from_backup', return_value=False):
                        data = await secure_storage._read_encrypted_data()
                        
                        # Should return empty data structure
                        assert "records" in data
                        assert "metadata" in data
                        assert len(data["records"]) == 0
    
    @pytest.mark.asyncio
    async def test_read_encrypted_data_with_restore(self, secure_storage):
        """Test restoring from backup when primary file is corrupted."""
        # Make read fail first time, then succeed after restore
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', side_effect=Exception("Read error")):
                # Mock successful restore
                with patch.object(secure_storage, '_restore_from_backup', return_value=True):
                    # After restore, second read works
                    mock_data = {"records": [{"id": "restored"}], "metadata": {"data_version": 1}}
                    
                    with patch.object(secure_storage, '_read_encrypted_data', 
                                     side_effect=[
                                         # Original call passes through to our mocked implementation
                                         RuntimeError("should not see this"),  
                                         # Recursive call after restore returns good data
                                         mock_data
                                     ]):
                        # Call the real method, but we're patching the recursive call
                        original_method = secure_storage._read_encrypted_data
                        secure_storage._read_encrypted_data = AsyncMock(side_effect=[mock_data])
                        
                        data = await original_method()
                        
                        # Should get the restored data
                        assert data == mock_data
    
    def test_write_encrypted_data(self, secure_storage, mock_fernet):
        """Test writing and encrypting data to storage."""
        mock_data = {"records": [], "metadata": {"data_version": 1}}
        
        # Mock file operations
        mock_file = mock_open()
        
        with patch('builtins.open', mock_file):
            with patch.object(secure_storage, '_create_backup', return_value=True):
                with patch.object(Path, 'stat') as mock_stat:
                    # For temp file verification
                    mock_stat.return_value.st_size = 100
                    
                    with patch('os.replace') as mock_replace:
                        result = secure_storage._write_encrypted_data(mock_data)
                        
                        assert result is True
                        mock_fernet.encrypt.assert_called_once()
                        mock_replace.assert_called_once()
    
    def test_write_encrypted_data_validation_failure(self, secure_storage):
        """Test data validation during write operations."""
        invalid_data = {"bad_structure": True}
        
        with patch.object(secure_storage, '_create_backup'):
            result = secure_storage._write_encrypted_data(invalid_data)
            
            assert result is False
    
    def test_write_encrypted_data_verification_failure(self, secure_storage, mock_fernet):
        """Test file verification failure during write."""
        mock_data = {"records": [], "metadata": {"data_version": 1}}
        
        # Setup mocks for verification failure
        def fake_write(data):
            # Write different data than what we meant to
            return len(b"corrupted")
        
        m = mock_open()
        m().write.side_effect = fake_write
        m().read.return_value = b"corrupted"  # Verification reads different data
        
        with patch('builtins.open', m):
            with patch.object(secure_storage, '_create_backup', return_value=True):
                with patch('os.path.exists', return_value=True):
                    result = secure_storage._write_encrypted_data(mock_data)
                    
                    # Should fail due to verification mismatch
                    assert result is False
    
    def test_verify_data_structure_valid(self, secure_storage):
        """Test validation of data structure."""
        valid_data = {
            "records": [], 
            "metadata": {
                "last_cleanup": None,
                "last_key_rotation": "2023-01-01T12:00:00",
                "last_backup": None,
                "data_version": 1
            }
        }
        
        assert secure_storage._verify_data_structure(valid_data) is True
    
    def test_verify_data_structure_invalid(self, secure_storage):
        """Test rejection of invalid data structures."""
        invalid_cases = [
            # Missing records
            {"metadata": {"last_cleanup": None, "last_key_rotation": "", "last_backup": None, "data_version": 1}},
            # Missing metadata
            {"records": []},
            # Records not a list
            {"records": {}, "metadata": {"last_cleanup": None, "last_key_rotation": "", "last_backup": None, "data_version": 1}},
            # Missing metadata fields
            {"records": [], "metadata": {"last_cleanup": None}},
            # Not a dict
            "not a dict",
            None
        ]
        
        for case in invalid_cases:
            assert secure_storage._verify_data_structure(case) is False
    
    def test_get_default_metadata(self, secure_storage):
        """Test generation of default metadata."""
        metadata = secure_storage._get_default_metadata()
        
        assert "last_cleanup" in metadata
        assert "last_key_rotation" in metadata
        assert "last_backup" in metadata
        assert "data_version" in metadata
        assert metadata["data_version"] == 1
    
    def test_create_backup(self, secure_storage, temp_storage_path):
        """Test creation of data backups."""
        # Create a record file
        record_file = Path(temp_storage_path) / "encrypted_records.bin"
        with open(record_file, 'wb') as f:
            f.write(b"test data")
        
        # Mock backup verification
        with patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value.st_size = len(b"test data")
            
            with patch.object(secure_storage, '_cleanup_old_backups'):
                result = secure_storage._create_backup()
                
                assert result is True
                
                # Check that a backup file was created
                backup_files = list(Path(temp_storage_path).glob("backups/records_backup_*.bin"))
                assert len(backup_files) == 1
    
    def test_create_backup_no_file(self, secure_storage):
        """Test backup behavior when no record file exists."""
        with patch.object(Path, 'exists', return_value=False):
            result = secure_storage._create_backup()
            
            assert result is False
    
    def test_create_backup_verification_failure(self, secure_storage, temp_storage_path):
        """Test backup verification failure handling."""
        # Create a record file
        record_file = Path(temp_storage_path) / "encrypted_records.bin"
        with open(record_file, 'wb') as f:
            f.write(b"test data")
        
        # Mock stats to make verification fail (different sizes)
        with patch.object(Path, 'stat') as mock_stat:
            # Return different sizes for original and backup
            mock_stat.side_effect = [
                MagicMock(st_size=10),  # Original file
                MagicMock(st_size=5)    # Backup file (different size)
            ]
            
            with patch.object(secure_storage, '_cleanup_old_backups'):
                with pytest.raises(ValueError):
                    secure_storage._create_backup()
    
    def test_cleanup_old_backups(self, secure_storage, temp_storage_path):
        """Test cleanup of old backups."""
        backup_dir = Path(temp_storage_path) / "backups"
        
        # Create some backup files with different timestamps
        now = datetime.now()
        
        # Recent backup (should be kept)
        recent_file = backup_dir / "records_backup_recent.bin"
        recent_file.touch()
        os.utime(recent_file, (now.timestamp(), now.timestamp()))
        
        # Old backup (should be removed)
        old_time = (now - timedelta(days=10)).timestamp()
        old_file = backup_dir / "records_backup_old.bin"
        old_file.touch()
        os.utime(old_file, (old_time, old_time))
        
        # Run cleanup
        secure_storage._cleanup_old_backups()
        
        # Check which files remain
        remaining_files = list(backup_dir.glob("records_backup_*.bin"))
        assert len(remaining_files) == 1
        assert remaining_files[0].name == "records_backup_recent.bin"
    
    def test_restore_from_backup_no_backups(self, secure_storage, temp_storage_path):
        """Test restore behavior when no backups exist."""
        backup_dir = Path(temp_storage_path) / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        result = secure_storage._restore_from_backup()
        
        assert result is False
    
    def test_restore_from_backup_success(self, secure_storage, temp_storage_path, mock_fernet):
        """Test successful restoration from backup."""
        # Create a mock backup file
        backup_dir = Path(temp_storage_path) / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_file = backup_dir / "records_backup_test.bin"
        
        with open(backup_file, 'wb') as f:
            f.write(b"encrypted_backup_data")
        
        # Setup decryption mock
        valid_data = {"records": [], "metadata": {"data_version": 1, "last_cleanup": None, "last_key_rotation": "2023-01-01", "last_backup": None}}
        mock_fernet.decrypt.return_value = json.dumps(valid_data).encode()
        
        result = secure_storage._restore_from_backup()
        
        assert result is True
        
        # Check that data was written to the record file
        record_file = Path(temp_storage_path) / "encrypted_records.bin"
        assert record_file.exists()
    
    def test_restore_from_backup_decryption_failure(self, secure_storage, temp_storage_path, mock_fernet):
        """Test backup restoration with decryption failures."""
        # Create a mock backup file
        backup_dir = Path(temp_storage_path) / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_file = backup_dir / "records_backup_test.bin"
        
        with open(backup_file, 'wb') as f:
            f.write(b"encrypted_backup_data")
        
        # Setup decryption to fail
        mock_fernet.decrypt.side_effect = Exception("Decryption error")
        
        result = secure_storage._restore_from_backup()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_rotate_key_not_needed(self, secure_storage):
        """Test key rotation when not needed (recent rotation)."""
        mock_data = {
            "records": [],
            "metadata": {
                "last_key_rotation": datetime.now().isoformat(),  # Just rotated
                "last_backup": None,
                "last_cleanup": None,
                "data_version": 1
            }
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            result = await secure_storage.rotate_key()
            
            assert result is True
            # Key should not have changed
            assert len(secure_storage.keys) == 1
    
    @pytest.mark.asyncio
    async def test_rotate_key_with_rotation(self, secure_storage):
        """Test key rotation process."""
        # Set up old rotation date to trigger rotation
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        mock_data = {
            "records": [],
            "metadata": {
                "last_key_rotation": old_date,
                "last_backup": None,
                "last_cleanup": None,
                "data_version": 1
            }
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            with patch.object(secure_storage, '_generate_secure_key', return_value=b'new_key'):
                with patch.object(secure_storage, '_create_backup', return_value=True):
                    with patch.object(secure_storage, '_write_encrypted_data', return_value=True):
                        with patch.object(secure_storage, '_save_keys', return_value=True):
                            result = await secure_storage.rotate_key()
                            
                            assert result is True
                            # Should have a new key at the front
                            assert secure_storage.keys[0] == b'new_key'
                            assert secure_storage.current_key == b'new_key'
    
    @pytest.mark.asyncio
    async def test_cleanup_old_records(self, secure_storage):
        """Test cleanup of old records."""
        now = datetime.now()
        recent_record = {"id": "recent", "timestamp": now.isoformat()}
        old_record = {"id": "old", "timestamp": (now - timedelta(days=60)).isoformat()}
        
        mock_data = {
            "records": [recent_record, old_record],
            "metadata": {
                "last_cleanup": None,
                "last_key_rotation": now.isoformat(),
                "last_backup": None,
                "data_version": 1
            }
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            with patch.object(secure_storage, '_write_encrypted_data') as mock_write:
                result = await secure_storage._cleanup_old_records(retention_days=30, force=True)
                
                assert result is True
                
                # Verify that only recent record remains
                written_data = mock_write.call_args[0][0]
                assert len(written_data["records"]) == 1
                assert written_data["records"][0]["id"] == "recent"
    
    @pytest.mark.asyncio
    async def test_cleanup_old_records_skips_if_recent(self, secure_storage):
        """Test cleanup skipping when recently performed."""
        now = datetime.now()
        recent_cleanup = (now - timedelta(hours=12)).isoformat()
        
        mock_data = {
            "records": [{"id": "record1"}, {"id": "record2"}],
            "metadata": {
                "last_cleanup": recent_cleanup,
                "last_key_rotation": now.isoformat(),
                "last_backup": None,
                "data_version": 1
            }
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            with patch.object(secure_storage, '_write_encrypted_data') as mock_write:
                result = await secure_storage._cleanup_old_records(retention_days=30)
                
                assert result is True
                # Should skip writing since cleanup is recent
                mock_write.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_add_record(self, secure_storage):
        """Test adding a new record."""
        mock_data = {
            "records": [],
            "metadata": {
                "last_cleanup": None,
                "last_key_rotation": datetime.now().isoformat(),
                "last_backup": None,
                "data_version": 1
            }
        }
        
        email_data = {
            "message_id": "test123",
            "subject": "Test Email",
            "sender": "test@example.com",
            "recipients": ["user@example.com"],
            "thread_id": "thread1"
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            with patch.object(secure_storage, '_write_encrypted_data', return_value=True):
                with patch.object(secure_storage, '_cleanup_old_records', return_value=True):
                    with patch.object(secure_storage, 'rotate_key', return_value=True):
                        record_id, success = await secure_storage.add_record(email_data)
                        
                        assert success is True
                        assert isinstance(record_id, str)
                        assert len(record_id) == 32
    
    @pytest.mark.asyncio
    async def test_add_record_with_validation(self, secure_storage):
        """Test record validation during addition."""
        # Invalid record (None)
        record_id, success = await secure_storage.add_record(None)
        
        assert success is False
        assert record_id == ""
        
        # Invalid record (not a dict)
        record_id, success = await secure_storage.add_record("not a dict")
        
        assert success is False
        assert record_id == ""
    
    @pytest.mark.asyncio
    async def test_is_processed(self, secure_storage):
        """Test checking if an email has been processed."""
        mock_data = {
            "records": [
                {"message_id": "processed1", "thread_messages": ["thread1a", "thread1b"]},
                {"message_id": "processed2", "thread_messages": ["thread2a"]}
            ],
            "metadata": {"data_version": 1}
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            # Direct message ID match
            is_processed, success = await secure_storage.is_processed("processed1")
            assert is_processed is True
            assert success is True
            
            # Thread message match
            is_processed, success = await secure_storage.is_processed("thread1a")
            assert is_processed is True
            assert success is True
            
            # No match
            is_processed, success = await secure_storage.is_processed("unknown")
            assert is_processed is False
            assert success is True
            
            # Empty message ID
            is_processed, success = await secure_storage.is_processed("")
            assert is_processed is False
            assert success is True
    
    @pytest.mark.asyncio
    async def test_get_record_count(self, secure_storage):
        """Test retrieving record count."""
        mock_data = {
            "records": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
            "metadata": {"data_version": 1}
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            count = await secure_storage.get_record_count()
            
            assert count == 3
    
    @pytest.mark.asyncio
    async def test_get_processed_records_since(self, secure_storage):
        """Test retrieving records since a specific time."""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        
        mock_data = {
            "records": [
                {"id": "recent", "timestamp": now.isoformat()},
                {"id": "day_old", "timestamp": yesterday.isoformat()},
                {"id": "old", "timestamp": two_days_ago.isoformat()}
            ],
            "metadata": {"data_version": 1}
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            # Get records from yesterday onwards
            records = await secure_storage.get_processed_records_since(yesterday)
            
            assert len(records) == 2
            assert records[0]["id"] == "recent"
            assert records[1]["id"] == "day_old"
    
    @pytest.mark.asyncio
    async def test_get_records_by_category(self, secure_storage):
        """Test retrieving records by category."""
        mock_data = {
            "records": [
                {"id": "1", "analysis_results": {"final_category": "meeting"}},
                {"id": "2", "analysis_results": {"final_category": "needs_review"}},
                {"id": "3", "analysis_results": {"final_category": "meeting"}}
            ],
            "metadata": {"data_version": 1}
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            # Get meeting records
            meeting_records = await secure_storage.get_records_by_category("meeting")
            
            assert len(meeting_records) == 2
            assert meeting_records[0]["id"] == "1"
            assert meeting_records[1]["id"] == "3"
            
            # Get needs_review records
            review_records = await secure_storage.get_records_by_category("needs_review")
            
            assert len(review_records) == 1
            assert review_records[0]["id"] == "2"
    
    @pytest.mark.asyncio
    async def test_get_all_processed_records(self, secure_storage):
        """Test retrieving all processed records."""
        mock_data = {
            "records": [
                {"id": "1", "message_id": "msg1"},
                {"id": "2", "message_id": "msg2"},
                {"id": "3", "message_id": "msg3"}
            ],
            "metadata": {"data_version": 1}
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            records = await secure_storage.get_all_processed_records()
            
            assert len(records) == 3
            assert records[0]["message_id"] == "msg1"
            assert records[1]["message_id"] == "msg2"
            assert records[2]["message_id"] == "msg3"
    
    @pytest.mark.asyncio
    async def test_get_category_counts(self, secure_storage):
        """Test getting counts of records by category."""
        mock_data = {
            "records": [
                {"id": "1", "analysis_results": {"final_category": "meeting"}},
                {"id": "2", "analysis_results": {"final_category": "needs_review"}},
                {"id": "3", "analysis_results": {"final_category": "meeting"}},
                {"id": "4", "analysis_results": {"final_category": "not_actionable"}},
                {"id": "5", "analysis_results": {"final_category": "unknown_category"}}
            ],
            "metadata": {"data_version": 1}
        }
        
        with patch.object(secure_storage, '_read_encrypted_data', return_value=mock_data):
            counts = await secure_storage.get_category_counts()
            
            assert counts["meeting"] == 2
            assert counts["needs_review"] == 1
            assert counts["not_actionable"] == 1
            assert counts["not_meeting"] == 0
            assert counts["unknown"] == 1  # The unknown_category gets counted as "unknown"
