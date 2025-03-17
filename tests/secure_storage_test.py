"""
Comprehensive Test Suite for SecureStorage

This module implements extensive testing for the SecureStorage class,
covering encryption, key rotation, backup mechanisms, data integrity,
and record management functionality.

The tests are designed to verify that the storage component maintains:
1. Data confidentiality through proper encryption
2. Data durability through backup and restore mechanisms
3. Data integrity through validation mechanisms
4. Proper key management through rotation procedures
5. Efficient record management through CRUD operations

Each test function isolates a specific functionality while maintaining
awareness of the complete component behavior.
"""

import pytest
import os
import json
import shutil
import tempfile
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock, mock_open

from cryptography.fernet import Fernet
from src.storage.secure import SecureStorage

class TestSecureStorage:
    """Test suite for SecureStorage component with comprehensive coverage."""

    @pytest.fixture
    def temp_storage_path(self):
        """Create a temporary storage path for isolated testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up after tests
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def storage(self, temp_storage_path):
        """Initialize SecureStorage instance with isolated storage path."""
        storage = SecureStorage(storage_path=temp_storage_path)
        yield storage
        # No additional cleanup needed as temp_storage_path fixture handles it

    def test_initialization(self, temp_storage_path):
        """
        Test proper initialization of SecureStorage.
        
        Verifies:
        - Directory creation
        - Key initialization
        - Default file creation
        """
        # Initialize storage
        storage = SecureStorage(storage_path=temp_storage_path)
        
        # Verify directories were created
        assert Path(temp_storage_path).exists()
        assert Path(temp_storage_path, "backups").exists()
        
        # Verify key file was created
        assert Path(temp_storage_path, "key_history.bin").exists()
        
        # Verify record file was created with default structure
        record_file = Path(temp_storage_path, "encrypted_records.bin")
        assert record_file.exists()
        
        # Decrypt and verify the default structure
        with open(record_file, 'rb') as f:
            encrypted_data = f.read()
            decrypted_data = storage.cipher_suite.decrypt(encrypted_data)
            data = json.loads(decrypted_data)
            
            # Verify expected structure
            assert "records" in data
            assert "metadata" in data
            assert len(data["records"]) == 0
            assert "last_cleanup" in data["metadata"]
            assert "last_key_rotation" in data["metadata"]
            assert "last_backup" in data["metadata"]
            assert "data_version" in data["metadata"]

    @pytest.mark.asyncio
    async def test_add_record(self, storage):
        """
        Test adding records to secure storage.
        
        Verifies:
        - Record addition functionality
        - Proper ID generation
        - Secure storage of data
        - Record retrieval after addition
        """
        # Create test email data
        email_data = {
            "message_id": "test123",
            "subject": "Test Email",
            "sender": "test@example.com",
            "thread_id": "thread123",
            "received_at": datetime.now().isoformat()
        }
        
        # Add record
        record_id, success = await storage.add_record(email_data)
        
        # Verify addition was successful
        assert success is True
        assert record_id != ""
        
        # Verify record can be retrieved
        is_processed, check_success = await storage.is_processed("test123")
        assert check_success is True
        assert is_processed is True
        
        # Verify record count
        count = await storage.get_record_count()
        assert count == 1
        
        # Get decrypted records and verify content
        data = await storage._read_encrypted_data()
        assert len(data["records"]) == 1
        assert data["records"][0]["message_id"] == "test123"
        assert data["records"][0]["processed"] is True

    @pytest.mark.asyncio
    async def test_is_processed(self, storage):
        """
        Test is_processed functionality for various scenarios.
        
        Verifies:
        - Detection of processed messages
        - Detection of unprocessed messages
        - Thread membership detection
        - Edge case handling
        """
        # Create test email data
        email_data1 = {
            "message_id": "test123",
            "subject": "Test Email",
            "sender": "test@example.com",
            "thread_id": "thread123",
            "thread_messages": ["test123", "test456", "test789"],
            "received_at": datetime.now().isoformat()
        }
        
        # Add first record
        await storage.add_record(email_data1)
        
        # Test exact message ID match
        is_processed, success = await storage.is_processed("test123")
        assert success is True
        assert is_processed is True
        
        # Test thread membership match
        is_processed, success = await storage.is_processed("test456")
        assert success is True
        assert is_processed is True
        
        # Test non-existent message
        is_processed, success = await storage.is_processed("nonexistent")
        assert success is True
        assert is_processed is False
        
        # Test empty message ID
        is_processed, success = await storage.is_processed("")
        assert success is True
        assert is_processed is False
        
        # Test None message ID
        is_processed, success = await storage.is_processed(None)
        assert success is True
        assert is_processed is False

    @pytest.mark.asyncio
    async def test_get_record_count(self, storage):
        """
        Test record counting functionality.
        
        Verifies:
        - Accurate counting of records
        - Zero count for empty storage
        - Count incrementation with additions
        """
        # Initially should have zero records
        count = await storage.get_record_count()
        assert count == 0
        
        # Add several records
        for i in range(5):
            email_data = {
                "message_id": f"test{i}",
                "subject": f"Test Email {i}",
                "sender": "test@example.com",
                "received_at": datetime.now().isoformat()
            }
            await storage.add_record(email_data)
        
        # Should now have 5 records
        count = await storage.get_record_count()
        assert count == 5

    @pytest.mark.asyncio
    async def test_encryption_decryption(self, storage, temp_storage_path):
        """
        Test encryption and decryption functionality.
        
        Verifies:
        - Data is properly encrypted in storage
        - Encrypted data can be decrypted correctly
        - Different keys cannot decrypt the data
        """
        # Create test data
        test_data = {
            "records": [{"id": "test1", "message_id": "msg1"}],
            "metadata": {"test": "value"}
        }
        
        # Write encrypted data
        success = storage._write_encrypted_data(test_data)
        assert success is True
        
        # Verify file exists
        record_file = Path(temp_storage_path, "encrypted_records.bin")
        assert record_file.exists()
        
        # Read raw encrypted data
        with open(record_file, 'rb') as f:
            encrypted_data = f.read()
        
        # Verify it's encrypted (should not contain plaintext values)
        encrypted_str = encrypted_data.decode('latin1')  # Just for string search
        assert "test1" not in encrypted_str
        assert "msg1" not in encrypted_str
        
        # Verify we can decrypt with the correct key
        decrypted_data = storage.cipher_suite.decrypt(encrypted_data)
        data = json.loads(decrypted_data)
        assert data["records"][0]["id"] == "test1"
        assert data["records"][0]["message_id"] == "msg1"
        
        # Verify a different key cannot decrypt
        different_key = Fernet.generate_key()
        different_cipher = Fernet(different_key)
        with pytest.raises(Exception):
            different_cipher.decrypt(encrypted_data)
        
        # Verify we can read through the class method
        data = await storage._read_encrypted_data()
        assert data["records"][0]["id"] == "test1"
        assert data["records"][0]["message_id"] == "msg1"

    @pytest.mark.asyncio
    async def test_key_rotation(self, storage, temp_storage_path):
        """
        Test key rotation mechanism.
        
        Verifies:
        - Key rotation creates new key
        - Old data remains accessible after rotation
        - Key history is maintained properly
        - Rotation updates metadata
        """
        # Add initial record
        email_data = {
            "message_id": "test123",
            "subject": "Test Email",
            "sender": "test@example.com",
            "received_at": datetime.now().isoformat()
        }
        await storage.add_record(email_data)
        
        # Get initial key
        initial_key = storage.current_key
        
        # Perform key rotation
        rotation_success = await storage.rotate_key()
        assert rotation_success is True
        
        # Verify key has changed
        assert storage.current_key != initial_key
        
        # Verify original record is still accessible
        is_processed, success = await storage.is_processed("test123")
        assert success is True
        assert is_processed is True
        
        # Verify metadata was updated
        data = await storage._read_encrypted_data()
        assert "last_key_rotation" in data["metadata"]
        
        # Add another record with new key
        email_data2 = {
            "message_id": "test456",
            "subject": "Test Email 2",
            "sender": "test@example.com",
            "received_at": datetime.now().isoformat()
        }
        await storage.add_record(email_data2)
        
        # Verify both records are accessible
        count = await storage.get_record_count()
        assert count == 2
        
        # Verify key history contains both keys
        assert len(storage.keys) >= 2
        assert initial_key in storage.keys
        assert storage.current_key in storage.keys

    @pytest.mark.asyncio
    async def test_backup_restore(self, storage, temp_storage_path):
        """
        Test backup creation and restoration.
        
        Verifies:
        - Backups are created successfully
        - Backups contain correct data
        - Restoration from backup works properly
        - Restoration preserves data integrity
        """
        # Add initial record
        email_data = {
            "message_id": "test123",
            "subject": "Test Email",
            "sender": "test@example.com",
            "received_at": datetime.now().isoformat()
        }
        await storage.add_record(email_data)
        
        # Create backup manually
        backup_success = storage._create_backup()
        assert backup_success is True
        
        # Verify backup was created
        backup_dir = Path(temp_storage_path, "backups")
        backup_files = list(backup_dir.glob("records_backup_*.bin"))
        assert len(backup_files) >= 1
        
        # Corrupt the original file
        record_file = Path(temp_storage_path, "encrypted_records.bin")
        with open(record_file, 'wb') as f:
            f.write(b'corrupted data')
        
        # Verify data is now corrupted
        with pytest.raises(Exception):
            await storage._read_encrypted_data()
        
        # Perform restoration
        restore_success = storage._restore_from_backup()
        assert restore_success is True
        
        # Verify data is now readable again
        data = await storage._read_encrypted_data()
        assert len(data["records"]) == 1
        assert data["records"][0]["message_id"] == "test123"

    @pytest.mark.asyncio
    async def test_cleanup_old_records(self, storage):
        """
        Test cleanup of old records.
        
        Verifies:
        - Old records are properly removed
        - Newer records are preserved
        - Metadata is updated correctly
        - Cleanup honors retention period
        """
        # Add some old records (with backdated timestamps)
        old_date = datetime.now() - timedelta(days=40)
        for i in range(3):
            email_data = {
                "message_id": f"old{i}",
                "subject": f"Old Email {i}",
                "sender": "test@example.com",
                "timestamp": old_date.isoformat()
            }
            await storage.add_record(email_data)
        
        # Add some new records
        for i in range(2):
            email_data = {
                "message_id": f"new{i}",
                "subject": f"New Email {i}",
                "sender": "test@example.com",
                "timestamp": datetime.now().isoformat()
            }
            await storage.add_record(email_data)
        
        # Verify we have 5 records total
        count = await storage.get_record_count()
        assert count == 5
        
        # Perform cleanup with 30 day retention
        cleanup_success = await storage._cleanup_old_records(retention_days=30, force=True)
        assert cleanup_success is True
        
        # Verify old records were removed, keeping only new ones
        count = await storage.get_record_count()
        assert count == 2
        
        # Verify metadata was updated
        data = await storage._read_encrypted_data()
        assert "last_cleanup" in data["metadata"]
        
        # Verify only new records remain
        for record in data["records"]:
            assert record["message_id"].startswith("new")

    @pytest.mark.asyncio
    async def test_data_integrity_verification(self, storage, temp_storage_path):
        """
        Test data integrity verification.
        
        Verifies:
        - Proper validation of data structure
        - Detection of malformed data
        - Handling of corrupted data
        - Recovery mechanisms for integrity failures
        """
        # Test with valid data structure
        valid_data = {
            "records": [],
            "metadata": {
                "last_cleanup": None,
                "last_key_rotation": datetime.now().isoformat(),
                "last_backup": None,
                "data_version": 1
            }
        }
        assert storage._verify_data_structure(valid_data) is True
        
        # Test with missing records
        invalid_data1 = {
            "metadata": {
                "last_cleanup": None,
                "last_key_rotation": datetime.now().isoformat(),
                "last_backup": None,
                "data_version": 1
            }
        }
        assert storage._verify_data_structure(invalid_data1) is False
        
        # Test with missing metadata fields
        invalid_data2 = {
            "records": [],
            "metadata": {
                "last_cleanup": None
                # Missing required fields
            }
        }
        assert storage._verify_data_structure(invalid_data2) is False
        
        # Test with non-list records
        invalid_data3 = {
            "records": "not a list",
            "metadata": {
                "last_cleanup": None,
                "last_key_rotation": datetime.now().isoformat(),
                "last_backup": None,
                "data_version": 1
            }
        }
        assert storage._verify_data_structure(invalid_data3) is False
        
        # Test data integrity during write/read cycle
        storage._write_encrypted_data(valid_data)
        read_data = await storage._read_encrypted_data()
        assert read_data["records"] == valid_data["records"]
        assert read_data["metadata"]["data_version"] == valid_data["metadata"]["data_version"]

    @pytest.mark.asyncio
    async def test_record_filtering(self, storage):
        """
        Test record filtering and retrieval operations.
        
        Verifies:
        - Records can be filtered by timestamp
        - Records can be filtered by category
        - Proper handling of empty results
        - Accurate filtering logic
        """
        # Create records with different timestamps and categories
        # Recent meeting emails
        for i in range(3):
            email_data = {
                "message_id": f"meeting{i}",
                "subject": f"Meeting Email {i}",
                "sender": "test@example.com",
                "timestamp": datetime.now().isoformat(),
                "analysis_results": {
                    "final_category": "meeting"
                }
            }
            await storage.add_record(email_data)
        
        # Older review emails
        old_date = datetime.now() - timedelta(days=5)
        for i in range(2):
            email_data = {
                "message_id": f"review{i}",
                "subject": f"Review Email {i}",
                "sender": "test@example.com",
                "timestamp": old_date.isoformat(),
                "analysis_results": {
                    "final_category": "needs_review"
                }
            }
            await storage.add_record(email_data)
        
        # Very old non-meeting emails
        very_old_date = datetime.now() - timedelta(days=10)
        for i in range(2):
            email_data = {
                "message_id": f"nonmeeting{i}",
                "subject": f"Non-meeting Email {i}",
                "sender": "test@example.com",
                "timestamp": very_old_date.isoformat(),
                "analysis_results": {
                    "final_category": "not_meeting"
                }
            }
            await storage.add_record(email_data)
        
        # Test records_since with different timeframes
        one_day_ago = datetime.now() - timedelta(days=1)
        recent_records = await storage.get_processed_records_since(one_day_ago)
        assert len(recent_records) == 3  # Only the meeting emails
        
        week_ago = datetime.now() - timedelta(days=7)
        week_records = await storage.get_processed_records_since(week_ago)
        assert len(week_records) == 5  # Meeting and review emails
        
        two_weeks_ago = datetime.now() - timedelta(days=14)
        all_records = await storage.get_processed_records_since(two_weeks_ago)
        assert len(all_records) == 7  # All emails
        
        # Test category filtering
        meeting_records = await storage.get_records_by_category("meeting")
        assert len(meeting_records) == 3
        
        review_records = await storage.get_records_by_category("needs_review")
        assert len(review_records) == 2
        
        nonmeeting_records = await storage.get_records_by_category("not_meeting")
        assert len(nonmeeting_records) == 2
        
        # Test getting all records
        all_records = await storage.get_all_processed_records()
        assert len(all_records) == 7
        
        # Test getting category counts
        category_counts = await storage.get_category_counts()
        assert category_counts["meeting"] == 3
        assert category_counts["needs_review"] == 2
        assert category_counts["not_meeting"] == 2

    @pytest.mark.asyncio
    async def test_error_handling(self, storage, temp_storage_path):
        """
        Test error handling during storage operations.
        
        Verifies:
        - Proper handling of file system errors
        - Recovery from corrupted files
        - Handling of invalid keys
        - Robustness against exception propagation
        """
        # Test read error handling
        record_file = Path(temp_storage_path, "encrypted_records.bin")
        
        # Create invalid encrypted data
        with open(record_file, 'wb') as f:
            f.write(b'invalid data that cannot be decrypted')
        
        # Should gracefully handle decryption failure and return default data
        data = await storage._read_encrypted_data()
        assert "records" in data
        assert "metadata" in data
        assert len(data["records"]) == 0
        
        # Test add_record error handling with invalid storage
        with patch.object(storage, '_write_encrypted_data', return_value=False):
            record_id, success = await storage.add_record({"message_id": "test"})
            assert success is False
        
        # Test get_record_count error handling
        with patch.object(storage, '_read_encrypted_data', side_effect=Exception("Test error")):
            count = await storage.get_record_count()
            assert count == 0
        
        # Test is_processed error handling
        with patch.object(storage, '_read_encrypted_data', side_effect=Exception("Test error")):
            is_processed, success = await storage.is_processed("test123")
            assert success is False

    @pytest.mark.asyncio
    async def test_large_dataset_performance(self, storage):
        """
        Test performance with larger datasets.
        
        Verifies:
        - System handles larger record volumes
        - Performance remains acceptable
        - Memory usage remains reasonable
        - Storage access patterns scale appropriately
        """
        record_count = 100  # Large enough to test performance but not too large for unit tests
        
        # Add many records
        start_time = time.time()
        for i in range(record_count):
            email_data = {
                "message_id": f"perf{i}",
                "subject": f"Performance Email {i}",
                "sender": "test@example.com",
                "timestamp": datetime.now().isoformat(),
                "analysis_results": {
                    "final_category": "meeting" if i % 3 == 0 else "needs_review" if i % 3 == 1 else "not_meeting"
                }
            }
            await storage.add_record(email_data)
        
        add_time = time.time() - start_time
        print(f"Time to add {record_count} records: {add_time:.2f} seconds")
        
        # Verify record count
        count = await storage.get_record_count()
        assert count == record_count
        
        # Test retrieval performance
        start_time = time.time()
        all_records = await storage.get_all_processed_records()
        retrieve_time = time.time() - start_time
        print(f"Time to retrieve {record_count} records: {retrieve_time:.2f} seconds")
        
        assert len(all_records) == record_count
        
        # Test category count performance
        start_time = time.time()
        category_counts = await storage.get_category_counts()
        count_time = time.time() - start_time
        print(f"Time to count categories: {count_time:.2f} seconds")
        
        assert category_counts["meeting"] + category_counts["needs_review"] + category_counts["not_meeting"] == record_count
        
        # Test cleanup performance
        start_time = time.time()
        await storage._cleanup_old_records(retention_days=0, force=True)  # Clean all for testing
        cleanup_time = time.time() - start_time
        print(f"Time to cleanup {record_count} records: {cleanup_time:.2f} seconds")
        
        # Performance assertions - these should be adjusted based on actual expected performance
        # but provide a baseline for regression testing
        assert add_time < 5.0  # Should add 100 records in under 5 seconds
        assert retrieve_time < 2.0  # Should retrieve 100 records in under 2 seconds
        assert count_time < 1.0  # Should count categories in under 1 second
        assert cleanup_time < 3.0  # Should clean up 100 records in under 3 seconds
