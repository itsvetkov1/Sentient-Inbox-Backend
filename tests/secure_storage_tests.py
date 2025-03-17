"""
Unit tests for SecureStorage component.

These tests verify the secure storage functionality including encryption,
key rotation, backup/restore mechanisms, and record management with proper
error handling and data integrity validation.

Design Considerations:
- Tests both the encryption/decryption core functionality
- Validates key rotation and backup mechanisms
- Verifies data integrity checks and record management
- Tests error handling and recovery procedures
"""

import os
import pytest
import asyncio
import json
import logging
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Import the component to test
from src.storage.secure import SecureStorage

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestSecureStorage:
    """
    Unit tests for the SecureStorage component.
    
    Tests the secure storage system with encryption, key rotation,
    backup/restore functionality, and record management.
    
    Focuses on data security, integrity, and proper error handling.
    """
    
    @pytest.fixture
    def temp_storage_path(self):
        """
        Create a temporary directory for test storage.
        
        Creates a clean test directory for each test and cleans up
        afterward to ensure test isolation.
        
        Yields:
            Path object pointing to temporary storage directory
        """
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        yield temp_path
        
        # Cleanup after test
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    async def secure_storage(self, temp_storage_path):
        """
        Initialize a clean SecureStorage instance for testing.
        
        Creates a SecureStorage instance with a clean test directory
        and returns it for test use.
        
        Args:
            temp_storage_path: Temporary storage directory path
            
        Returns:
            Initialized SecureStorage instance
        """
        storage = SecureStorage(str(temp_storage_path))
        return storage
    
    @pytest.mark.asyncio
    async def test_add_and_retrieve_record(self, secure_storage):
        """
        Test adding and retrieving a record.
        
        Verifies that records can be correctly added, encrypted,
        and later retrieved with proper decryption.
        
        Args:
            secure_storage: SecureStorage instance
        """
        # Create test record
        test_record = {
            "message_id": "test_record_123",
            "subject": "Test Subject",
            "sender": "test@example.com",
            "timestamp": datetime.now().isoformat(),
            "content": "This is a test email content",
            "analysis_results": {
                "is_meeting": True,
                "final_category": "standard_response"
            }
        }
        
        # Add record
        record_id, success = await secure_storage.add_record(test_record)
        
        # Verify success
        assert success is True
        assert record_id != ""
        
        # Check if record is marked as processed
        is_processed, check_success = await secure_storage.is_processed(test_record["message_id"])
        assert check_success is True
        assert is_processed is True
        
        # Verify record exists in encrypted storage
        # We can't directly access the encrypted data, but we can check the file exists
        assert secure_storage.record_file.exists()
    
    @pytest.mark.asyncio
    async def test_get_record_count(self, secure_storage):
        """
        Test getting record count from storage.
        
        Verifies that the record count accurately reflects the
        number of records in the storage.
        
        Args:
            secure_storage: SecureStorage instance
        """
        # Check initial count (should be 0)
        initial_count = await secure_storage.get_record_count()
        assert initial_count == 0
        
        # Add three test records
        test_records = [
            {
                "message_id": f"test_record_{i}",
                "subject": f"Test Subject {i}",
                "sender": "test@example.com",
                "timestamp": datetime.now().isoformat(),
                "content": f"This is test email content {i}",
                "analysis_results": {
                    "is_meeting": i % 2 == 0,
                    "final_category": "standard_response" if i % 2 == 0 else "not_meeting"
                }
            }
            for i in range(3)
        ]
        
        for record in test_records:
            await secure_storage.add_record(record)
        
        # Check updated count
        updated_count = await secure_storage.get_record_count()
        assert updated_count == 3
    
    @pytest.mark.asyncio
    async def test_weekly_history_deduplication(self, secure_storage):
        """
        Test weekly history and deduplication functionality.
        
        Verifies that the weekly rolling history correctly prevents
        duplicate processing of the same email.
        
        Args:
            secure_storage: SecureStorage instance
        """
        # Add a test record
        test_record = {
            "message_id": "duplicate_test_123",
            "subject": "Test Subject",
            "sender": "test@example.com",
            "timestamp": datetime.now().isoformat(),
            "content": "This is a test email content",
            "analysis_results": {
                "is_meeting": True,
                "final_category": "standard_response"
            }
        }
        
        # Add record first time
        record_id, success = await secure_storage.add_record(test_record)
        assert success is True
        
        # Check if record is processed
        is_processed, check_success = await secure_storage.is_processed(test_record["message_id"])
        assert is_processed is True
        
        # Try to add the same record again
        record_id_2, success_2 = await secure_storage.add_record(test_record)
        
        # The record should still be added (for storage purposes), 
        # but marked as a duplicate in the logs
        assert success_2 is True
        
        # Record count should still increase (both additions are stored)
        count = await secure_storage.get_record_count()
        assert count == 2
        
        # But is_processed should still return True for deduplication purposes
        is_processed_2, check_success_2 = await secure_storage.is_processed(test_record["message_id"])
        assert is_processed_2 is True
    
    @pytest.mark.asyncio
    async def test_key_rotation(self, secure_storage):
        """
        Test encryption key rotation functionality.
        
        Verifies that encryption keys can be rotated while maintaining
        access to previously encrypted data.
        
        Args:
            secure_storage: SecureStorage instance
        """
        # Add a test record before rotation
        test_record = {
            "message_id": "pre_rotation_123",
            "subject": "Pre-Rotation",
            "sender": "test@example.com",
            "timestamp": datetime.now().isoformat(),
            "content": "This is a test email content before key rotation",
            "analysis_results": {
                "is_meeting": True,
                "final_category": "standard_response"
            }
        }
        
        # Add record with original key
        record_id, success = await secure_storage.add_record(test_record)
        assert success is True
        
        # Perform key rotation
        rotation_success = await secure_storage.rotate_key()
        assert rotation_success is True
        
        # Verify we can still access the record after rotation
        is_processed, check_success = await secure_storage.is_processed(test_record["message_id"])
        assert is_processed is True
        
        # Add another record after rotation
        post_record = {
            "message_id": "post_rotation_456",
            "subject": "Post-Rotation",
            "sender": "test@example.com",
            "timestamp": datetime.now().isoformat(),
            "content": "This is a test email content after key rotation",
            "analysis_results": {
                "is_meeting": False,
                "final_category": "not_meeting"
            }
        }
        
        # Add record with new key
        post_record_id, post_success = await secure_storage.add_record(post_record)
        assert post_success is True
        
        # Verify we can access both records
        pre_processed, pre_check = await secure_storage.is_processed(test_record["message_id"])
        post_processed, post_check = await secure_storage.is_processed(post_record["message_id"])
        
        assert pre_processed is True
        assert post_processed is True
    
    @pytest.mark.asyncio
    async def test_backup_and_restore(self, secure_storage, monkeypatch):
        """
        Test backup creation and restoration.
        
        Verifies that backups are correctly created and can be
        restored in case of data corruption.
        
        Args:
            secure_storage: SecureStorage instance
            monkeypatch: Pytest fixture for monkeypatching
        """
        # Add a test record
        test_record = {
            "message_id": "backup_test_789",
            "subject": "Backup Test",
            "sender": "test@example.com",
            "timestamp": datetime.now().isoformat(),
            "content": "This is a test email content for backup testing",
            "analysis_results": {
                "is_meeting": True,
                "final_category": "standard_response"
            }
        }
        
        # Add record
        record_id, success = await secure_storage.add_record(test_record)
        assert success is True
        
        # Create backup (should be called automatically during add_record, but call explicitly for testing)
        backup_created = await asyncio.to_thread(secure_storage._create_backup)
        assert backup_created is True
        
        # Verify backup was created
        backup_files = list(secure_storage.backup_dir.glob("records_backup_*.bin"))
        assert len(backup_files) > 0
        
        # Corrupt the main record file
        with open(secure_storage.record_file, 'wb') as f:
            f.write(b'corrupted data')
        
        # Restore from backup
        restored = await asyncio.to_thread(secure_storage._restore_from_backup)
        assert restored is True
        
        # Verify we can still access the record after restoration
        is_processed, check_success = await secure_storage.is_processed(test_record["message_id"])
        assert is_processed is True
    
    @pytest.mark.asyncio
    async def test_old_records_cleanup(self, secure_storage, monkeypatch):
        """
        Test cleanup of old records.
        
        Verifies that records older than the retention period are
        properly removed during cleanup.
        
        Args:
            secure_storage: SecureStorage instance
            monkeypatch: Pytest fixture for monkeypatching
        """
        # Mock datetime.now to return a fixed time
        now = datetime.now()
        monkeypatch.setattr(datetime, 'now', lambda: now)
        
        # Add a test record with current timestamp
        current_record = {
            "message_id": "current_record_123",
            "subject": "Current Record",
            "sender": "test@example.com",
            "timestamp": now.isoformat(),
            "content": "This is a current test email content",
            "analysis_results": {
                "is_meeting": True,
                "final_category": "standard_response"
            }
        }
        
        # Add current record
        await secure_storage.add_record(current_record)
        
        # Add an old record with timestamp more than 30 days ago
        old_time = now - timedelta(days=31)
        
        # Modify _read_encrypted_data method to return customized data with old record
        original_read = secure_storage._read_encrypted_data
        
        async def mock_read(*args, **kwargs):
            data = await original_read(*args, **kwargs)
            # Add an old record to the data
            data["records"].append({
                "id": "old_record_456",
                "message_id": "old_record_456",
                "timestamp": old_time.isoformat(),
                "processed": True,
                "subject": "Old Record",
                "sender": "old@example.com",
                "analysis_results": {
                    "is_meeting": False,
                    "final_category": "not_meeting"
                }
            })
            return data
            
        # Apply the mock
        monkeypatch.setattr(secure_storage, '_read_encrypted_data', mock_read)
        
        # The next write will include our fake old record
        # Force a write to apply our changes
        test_record = {
            "message_id": "force_write_record",
            "subject": "Force Write",
            "sender": "test@example.com",
            "timestamp": now.isoformat(),
            "content": "This forces a write to apply our mock changes",
        }
        await secure_storage.add_record(test_record)
        
        # Restore original read method
        monkeypatch.setattr(secure_storage, '_read_encrypted_data', original_read)
        
        # Verify we have old and new records before cleanup
        # Directly check if "old_record_456" exists by checking all processed messages
        data_before = await secure_storage._read_encrypted_data()
        old_exists = False
        for record in data_before.get("records", []):
            if record.get("message_id") == "old_record_456":
                old_exists = True
                break
                
        assert old_exists, "Failed to inject old record for testing"
        
        # Perform cleanup with 30-day retention
        cleanup_success = await secure_storage._cleanup_old_records(retention_days=30, force=True)
        assert cleanup_success is True
        
        # Verify old record was removed but current record remains
        data_after = await secure_storage._read_encrypted_data()
        current_exists = False
        old_exists = False
        
        for record in data_after.get("records", []):
            if record.get("message_id") == "current_record_123":
                current_exists = True
            if record.get("message_id") == "old_record_456":
                old_exists = True
                
        assert current_exists, "Current record should still exist after cleanup"
        assert not old_exists, "Old record should be removed after cleanup"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, secure_storage):
        """
        Test error handling during storage operations.
        
        Verifies that the storage component correctly handles errors
        during read/write operations without crashing.
        
        Args:
            secure_storage: SecureStorage instance
        """
        # Test with invalid record format
        invalid_record = "This is not a valid record dictionary"
        
        # This should fail but not crash
        with pytest.raises(Exception):
            record_id, success = await secure_storage.add_record(invalid_record)
            assert success is False
        
        # Test with empty message_id
        empty_id_record = {
            "message_id": "",
            "subject": "Empty ID Record",
            "sender": "test@example.com",
            "timestamp": datetime.now().isoformat(),
            "content": "This record has an empty message_id",
        }
        
        # This should succeed but log a warning
        with patch.object(logger, 'warning') as mock_warning:
            record_id, success = await secure_storage.add_record(empty_id_record)
            assert success is True
            # The storage should have generated a unique ID
            assert record_id != ""
    
    @pytest.mark.asyncio
    async def test_get_records_by_category(self, secure_storage):
        """
        Test retrieving records filtered by category.
        
        Verifies that records can be correctly filtered and retrieved
        by their assigned category.
        
        Args:
            secure_storage: SecureStorage instance
        """
        # Add records with different categories
        categories = ["meeting", "needs_review", "not_actionable", "not_meeting"]
        
        for i, category in enumerate(categories):
            record = {
                "message_id": f"category_test_{i}",
                "subject": f"Category {category}",
                "sender": "test@example.com",
                "timestamp": datetime.now().isoformat(),
                "content": f"This is a test email for category {category}",
                "analysis_results": {
                    "is_meeting": category == "meeting",
                    "final_category": category
                }
            }
            await secure_storage.add_record(record)
        
        # Retrieve records by category
        for category in categories:
            records = await secure_storage.get_records_by_category(category)
            
            # Should find exactly one record for each category
            assert len(records) == 1
            assert records[0]["analysis_results"]["final_category"] == category
    
    @pytest.mark.asyncio
    async def test_get_category_counts(self, secure_storage):
        """
        Test getting counts of records by category.
        
        Verifies that category counts accurately reflect the
        distribution of records across categories.
        
        Args:
            secure_storage: SecureStorage instance
        """
        # Add multiple records with different categories
        category_counts = {
            "meeting": 3,
            "needs_review": 2,
            "not_actionable": 1,
            "not_meeting": 4
        }
        
        for category, count in category_counts.items():
            for i in range(count):
                record = {
                    "message_id": f"{category}_test_{i}",
                    "subject": f"Category {category} #{i}",
                    "sender": "test@example.com",
                    "timestamp": datetime.now().isoformat(),
                    "content": f"This is test email #{i} for category {category}",
                    "analysis_results": {
                        "is_meeting": category == "meeting",
                        "final_category": category
                    }
                }
                await secure_storage.add_record(record)
        
        # Get category counts
        counts = await secure_storage.get_category_counts()
        
        # Verify counts match what we added
        for category, expected_count in category_counts.items():
            assert counts[category] == expected_count
    
    @pytest.mark.asyncio
    async def test_get_processed_records_since(self, secure_storage, monkeypatch):
        """
        Test retrieving records processed since a specific time.
        
        Verifies that time-based filtering correctly returns only
        records processed after the specified timestamp.
        
        Args:
            secure_storage: SecureStorage instance
            monkeypatch: Pytest fixture for monkeypatching
        """
        # Create timestamps for testing
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        
        # Add records with different timestamps
        timestamps = [
            two_days_ago,  # 0
            yesterday,     # 1
            yesterday,     # 2
            now,           # 3
            now            # 4
        ]
        
        for i, timestamp in enumerate(timestamps):
            record = {
                "message_id": f"time_test_{i}",
                "subject": f"Time Test {i}",
                "sender": "test@example.com",
                "timestamp": timestamp.isoformat(),
                "content": f"This is a test email with timestamp {timestamp.isoformat()}",
                "analysis_results": {
                    "is_meeting": i % 2 == 0,
                    "final_category": "meeting" if i % 2 == 0 else "not_meeting"
                }
            }
            await secure_storage.add_record(record)
        
        # Get records since yesterday
        since_yesterday = await secure_storage.get_processed_records_since(yesterday)
        
        # Should find records with index 1, 2, 3, 4 (4 records)
        assert len(since_yesterday) == 4
        
        # Get records since now
        since_now = await secure_storage.get_processed_records_since(now)
        
        # Should find records with index 3, 4 (2 records)
        assert len(since_now) == 2
