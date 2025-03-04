import asyncio
import base64
import hashlib
import json
import logging
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Constants for security settings
KEY_ROTATION_DAYS = 30
BACKUP_RETENTION_DAYS = 7
MAX_RETRIES = 1
RETRY_DELAY = 3  # seconds
WEEKLY_HISTORY_DAYS = 7

class SecureStorage:
    """Manages secure storage of email records with encryption, automatic cleanup, and weekly rolling history."""

    def __init__(self, storage_path: str = "data/secure"):
        """Initialize the secure storage manager with encryption setup."""
        self.storage_path = Path(storage_path)
        self.record_file = self.storage_path / "encrypted_records.bin"
        self.backup_dir = self.storage_path / "backups"
        self.keys_file = self.storage_path / "key_history.bin"
        
        # Create necessary directories
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

        # Initialize or load encryption keys
        self.keys = self._initialize_keys()
        self.current_key = self.keys[0]  # Most recent key
        self.cipher_suite = Fernet(self.current_key)

        # Initialize storage if needed
        if not self.record_file.exists():
            self._write_encrypted_data({
                "records": [], 
                "metadata": {
                    "last_cleanup": None,
                    "last_key_rotation": datetime.now().isoformat(),
                    "last_backup": None,
                    "data_version": 1
                }
            })

        # Set up logging
        logging.basicConfig(level=logging.DEBUG)

    def _generate_secure_key(self, extra_entropy: Optional[bytes] = None) -> bytes:
        """Generate a secure encryption key using system-specific information."""
        # Combine system info with optional extra entropy
        system_info = f"{os.getpid()}{os.path.getmtime(__file__)}{time.time()}"
        if extra_entropy:
            system_info = f"{system_info}{extra_entropy.hex()}"
        salt = hashlib.sha256(system_info.encode()).digest()

        # Use PBKDF2 to derive a secure key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        key = base64.urlsafe_b64encode(kdf.derive(os.urandom(32)))
        return key

    def _generate_record_id(self, email_data: Dict[str, Any]) -> str:
        """Generate a unique, non-reversible ID for an email record."""
        # Combine relevant data to create a unique identifier
        unique_data = f"{email_data.get('timestamp', '')}{email_data.get('message_id', '')}"
        # Create a one-way hash that can't be reversed to get the original data
        return hashlib.sha256(unique_data.encode()).hexdigest()[:32]

    def _initialize_keys(self) -> List[bytes]:
        """Initialize or load encryption keys with history."""
        try:
            if self.keys_file.exists():
                with open(self.keys_file, 'rb') as f:
                    keys_data = json.load(f)
                    return [k.encode() for k in keys_data['keys']]
            
            # Generate initial key
            initial_key = base64.urlsafe_b64encode(os.urandom(32))
            with open(self.keys_file, 'w') as f:
                json.dump({'keys': [initial_key.decode()]}, f)
            return [initial_key]
            
        except Exception as e:
            logger.error(f"Error initializing keys: {e}")
            # Generate a new key if there's any error
            initial_key = base64.urlsafe_b64encode(os.urandom(32))
            with open(self.keys_file, 'w') as f:
                json.dump({'keys': [initial_key.decode()]}, f)
            return [initial_key]

    def _save_keys(self, keys: List[bytes]) -> bool:
        """Save encryption keys."""
        try:
            keys_data = {
                'keys': [base64.urlsafe_b64encode(k).decode() for k in keys]
            }
            with open(self.keys_file, 'w') as f:
                json.dump(keys_data, f)
            return True
        except Exception as e:
            logger.error(f"Error saving keys: {e}")
            return False

    def _read_encrypted_data(self, allow_restore: bool = True) -> Dict:
        """Read and decrypt the stored data with retry and key rotation support."""
        for attempt in range(MAX_RETRIES):
            try:
                if not self.record_file.exists():
                    return {"records": [], "metadata": self._get_default_metadata()}

                with open(self.record_file, 'rb') as f:
                    encrypted_data = f.read()
                    if not encrypted_data:
                        return {"records": [], "metadata": self._get_default_metadata()}

                    # Try decryption with all available keys
                    last_error = None
                    for key in self.keys:
                        try:
                            cipher = Fernet(key)
                            decrypted_data = cipher.decrypt(encrypted_data)
                            data = json.loads(decrypted_data)
                            
                            # Verify data integrity
                            if not self._verify_data_structure(data):
                                raise ValueError("Invalid data structure")
                            
                            # Re-encrypt with current key if an old key was used
                            if key != self.current_key:
                                self._write_encrypted_data(data)
                            
                            return data
                        except Exception as e:
                            last_error = e
                            continue
                    
                    # If decryption failed and restore is allowed, try to restore
                    if allow_restore and self._restore_from_backup():
                        # Try reading one more time without allowing another restore
                        return self._read_encrypted_data(allow_restore=False)
                    
                    raise ValueError(f"Unable to decrypt with any available key: {last_error}")
                    
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Retry {attempt + 1} reading data: {e}")
                    time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                    continue
                logger.error(f"Error reading encrypted data: {e}")
                if allow_restore and self._restore_from_backup():
                    return self._read_encrypted_data(allow_restore=False)
                return {"records": [], "metadata": self._get_default_metadata()}

    def _write_encrypted_data(self, data: Dict) -> bool:
        """Encrypt and write data to storage with backup."""
        for attempt in range(MAX_RETRIES):
            try:
                # Create backup before writing
                self._create_backup()

                # Verify data structure before encryption
                if not self._verify_data_structure(data):
                    raise ValueError("Invalid data structure")

                # Encrypt and write data
                encrypted_data = self.cipher_suite.encrypt(json.dumps(data).encode())
                temp_file = self.record_file.with_suffix('.tmp')
                
                # Write to temp file first
                with open(temp_file, 'wb') as f:
                    f.write(encrypted_data)
                
                # Verify the temp file
                with open(temp_file, 'rb') as f:
                    verify_data = f.read()
                    if verify_data != encrypted_data:
                        raise ValueError("Data verification failed")
                
                # Atomic replace
                os.replace(temp_file, self.record_file)
                
                # Update backup timestamp
                data["metadata"]["last_backup"] = datetime.now().isoformat()
                return True

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Retry {attempt + 1} writing data: {e}")
                    time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass
                    continue
                logger.error(f"Error writing encrypted data: {e}")
                return False

    def _verify_data_structure(self, data: Dict) -> bool:
        """Verify the integrity of the data structure."""
        try:
            required_keys = {"records", "metadata"}
            metadata_keys = {"last_cleanup", "last_key_rotation", "last_backup", "data_version"}
            
            if not all(k in data for k in required_keys):
                return False
                
            if not all(k in data["metadata"] for k in metadata_keys):
                return False
                
            if not isinstance(data["records"], list):
                return False
                
            return True
        except Exception:
            return False

    def _get_default_metadata(self) -> Dict:
        """Get default metadata structure."""
        return {
            "last_cleanup": None,
            "last_key_rotation": datetime.now().isoformat(),
            "last_backup": None,
            "data_version": 1
        }

    def _create_backup(self) -> bool:
        """Create a backup of the current data file."""
        try:
            if self.record_file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = self.backup_dir / f"records_backup_{timestamp}.bin"
                shutil.copy2(self.record_file, backup_file)
                
                # Verify backup
                if not backup_file.exists() or backup_file.stat().st_size != self.record_file.stat().st_size:
                    raise ValueError("Backup verification failed")
                
                # Cleanup old backups
                self._cleanup_old_backups()
                return True
            return False
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False

    def _cleanup_old_backups(self):
        """Remove backups older than BACKUP_RETENTION_DAYS."""
        try:
            cutoff = datetime.now() - timedelta(days=BACKUP_RETENTION_DAYS)
            for backup_file in self.backup_dir.glob("records_backup_*.bin"):
                try:
                    if datetime.fromtimestamp(backup_file.stat().st_mtime) < cutoff:
                        backup_file.unlink()
                except Exception as e:
                    logger.error(f"Error cleaning up backup {backup_file}: {e}")
        except Exception as e:
            logger.error(f"Error during backup cleanup: {e}")

    def _restore_from_backup(self) -> bool:
        """Attempt to restore from the most recent valid backup."""
        try:
            # Get list of backups sorted by modification time (newest first)
            backups = sorted(
                [f for f in self.backup_dir.glob("records_backup_*.bin") if f.is_file()],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            if not backups:
                logger.warning("No backups found for restoration")
                return False
            
            # Try each backup until we find a valid one
            for backup_file in backups:
                try:
                    # Read the backup data
                    with open(backup_file, 'rb') as f:
                        encrypted_data = f.read()
                        
                    # Try to decrypt with all available keys
                    for key in self.keys:
                        try:
                            cipher = Fernet(key)
                            decrypted_data = cipher.decrypt(encrypted_data)
                            data = json.loads(decrypted_data)
                            
                            if self._verify_data_structure(data):
                                # Re-encrypt with current key
                                encrypted_data = self.cipher_suite.encrypt(json.dumps(data).encode())
                                
                                # Write directly to record file
                                with open(self.record_file, 'wb') as f:
                                    f.write(encrypted_data)
                                
                                logger.info(f"Successfully restored from backup: {backup_file}")
                                return True
                        except Exception:
                            continue
                    
                except Exception as e:
                    logger.warning(f"Failed to restore from backup {backup_file}: {e}")
                    continue
            
            logger.error("All backup restoration attempts failed")
            return False
            
        except Exception as e:
            logger.error(f"Error during backup restoration: {e}")
            return False

    async def rotate_key(self) -> bool:
        """Rotate encryption key and re-encrypt data."""
        try:
            # Check if rotation is needed
            data = await asyncio.to_thread(self._read_encrypted_data)
            last_rotation = datetime.fromisoformat(data["metadata"]["last_key_rotation"])
            if datetime.now() - last_rotation < timedelta(days=KEY_ROTATION_DAYS):
                return True

            # Generate new key
            new_key = await asyncio.to_thread(self._generate_secure_key, os.urandom(32))
            
            # Create backup before rotation
            if not await asyncio.to_thread(self._create_backup):
                logger.error("Failed to create backup before key rotation")
                return False
            
            # Re-encrypt data with new key
            self.keys.insert(0, new_key)
            self.current_key = new_key
            self.cipher_suite = Fernet(new_key)
            
            # Update metadata and save
            data["metadata"]["last_key_rotation"] = datetime.now().isoformat()
            success = await asyncio.to_thread(self._write_encrypted_data, data)
            
            if success:
                # Keep limited key history
                self.keys = self.keys[:3]  # Keep last 3 keys
                await asyncio.to_thread(self._save_keys, self.keys)
                return True
            return False

        except Exception as e:
            logger.error(f"Error rotating encryption key: {e}")
            return False

    async def _cleanup_old_records(self, retention_days: int = 30, force: bool = False) -> bool:
        """Remove records older than the retention period.
        Args:
            retention_days: Number of days to retain records
            force: If True, ignores last_cleanup timestamp (for testing)
        Returns: True if cleanup was successful, False otherwise."""
        try:
            data = await asyncio.to_thread(self._read_encrypted_data)
            now = datetime.now()

            # Check if cleanup is needed (unless forced)
            if not force:
                last_cleanup = data["metadata"].get("last_cleanup")
                if last_cleanup:
                    last_cleanup_date = datetime.fromisoformat(last_cleanup)
                    if last_cleanup_date > now - timedelta(days=1):
                        return True

            # Keep only records within retention period
            cutoff_date = now - timedelta(days=retention_days)
            original_records = data["records"]
            data["records"] = [
                record for record in original_records
                if datetime.fromisoformat(record.get("timestamp", "2000-01-01")) > cutoff_date
            ]

            # Update cleanup timestamp and write changes
            data["metadata"]["last_cleanup"] = now.isoformat()
            return await asyncio.to_thread(self._write_encrypted_data, data)

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return False

    async def add_record(self, email_data: Dict[str, Any], force_cleanup: bool = False) -> Tuple[str, bool]:
        """Add a new email record to secure storage.
        Args:
            email_data: The email data to store
            force_cleanup: If True, forces cleanup regardless of last cleanup time
        Returns: Tuple of (record_id, success)"""
        try:
            # Input validation
            if not email_data or not isinstance(email_data, dict):
                logger.error("Invalid email data format")
                return "", False

            # Generate a unique ID for the record
            record_id = self._generate_record_id(email_data)

            # Create a sanitized record with thread information
            sanitized_record = {
                "id": record_id,
                "timestamp": datetime.now().isoformat(),
                "processed": True,
                "message_id": email_data.get("message_id", ""),
                "thread_id": email_data.get("thread_id", ""),
                "thread_messages": email_data.get("thread_messages", []),
                "message_hash": hashlib.sha256(
                    f"{email_data.get('subject', '')}{email_data.get('sender', '')}"
                    f"{','.join(sorted(email_data.get('recipients', [])))}"
                    f"{email_data.get('thread_id', '')}".encode()
                ).hexdigest(),
                "checksum": hashlib.sha256(
                    json.dumps(email_data, sort_keys=True).encode()
                ).hexdigest()
            }

            # Read existing data, add new record, and write back
            data = await asyncio.to_thread(self._read_encrypted_data)
            data["records"].append(sanitized_record)
            
            if await asyncio.to_thread(self._write_encrypted_data, data):
                # Trigger maintenance operations
                await self._cleanup_old_records(force=force_cleanup)
                await self.rotate_key()  # Check and rotate key if needed
                return record_id, True
            return record_id, False

        except Exception as e:
            logger.error(f"Error adding record: {e}")
            return "", False

    async def is_processed(self, message_id: str) -> Tuple[bool, bool]:
        """
        Check if an email has been processed using its message ID.
        Also checks if any message in the same thread has been processed.
        
        Returns: Tuple of (is_processed, operation_success)
        """
        try:
            if not message_id:
                return False, True  # Not processed, but operation succeeded

            # Get all records
            data = await asyncio.to_thread(self._read_encrypted_data)
            records = data.get("records", [])
            
            # First check direct message ID match
            for record in records:
                if record.get("message_id") == message_id:
                    return True, True
                    
                # Also check if this message is in any processed thread
                thread_messages = record.get("thread_messages", [])
                if message_id in thread_messages:
                    return True, True
                    
            return False, True

        except Exception as e:
            logger.error(f"Error checking processed status: {e}")
            return False, False

    async def get_record_count(self) -> int:
        """Get the total number of records (for monitoring purposes only)."""
        try:
            data = await asyncio.to_thread(self._read_encrypted_data)
            return len(data.get("records", []))
        except Exception as e:
            logger.error(f"Error getting record count: {e}")
            return 0
