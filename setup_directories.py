"""
Directory Structure Setup Utility

This script ensures proper directory structure initialization before application startup.
It creates all required directories based on application configuration, implementing
proper error handling and logging following system specifications.

Usage:
    python setup_directories.py

Returns:
    0 for success, 1 for failure
"""

import os
import sys
import logging
from pathlib import Path


def setup_logging():
    """Configure basic logging for directory setup."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger("setup")


def create_required_directories():
    """
    Create all required application directories following system specifications.
    
    Implements comprehensive directory structure creation with proper error
    handling and validation, following requirements from system documentation.
    
    Returns:
        bool: True if all directories created successfully, False otherwise
    """
    logger = setup_logging()
    
    # Define required directories based on system documentation
    required_directories = [
        # Core system directories
        "logs",                    # Logging directory for all components
        "data",                    # Base data directory
        "data/config",             # Configuration storage
        "data/secure",             # Encrypted data storage
        "data/secure/backups",     # Backup storage for secure data
        "data/metrics",            # Performance metrics storage
        "data/cache",              # Temporary cache storage
    ]
    
    success = True
    created_dirs = []
    
    # Create each directory with proper error handling
    for directory in required_directories:
        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {directory}")
                created_dirs.append(directory)
            else:
                logger.info(f"Directory already exists: {directory}")
        except Exception as e:
            logger.error(f"Error creating directory {directory}: {str(e)}")
            success = False
    
    # Summary output
    if created_dirs:
        logger.info(f"Created {len(created_dirs)} directories: {', '.join(created_dirs)}")
    else:
        logger.info("No new directories needed to be created")
        
    return success


def check_file_permissions():
    """
    Verify write permissions on critical directories.
    
    Implements permission validation for key application directories
    to ensure proper operation throughout the application lifecycle.
    
    Returns:
        bool: True if all permissions are correct, False otherwise
    """
    logger = setup_logging()
    critical_dirs = ["logs", "data/secure", "data/config"]
    success = True
    
    for directory in critical_dirs:
        test_file = Path(directory) / ".permission_test"
        try:
            # Attempt to create and remove a test file
            with open(test_file, 'w') as f:
                f.write("test")
            test_file.unlink()
            logger.info(f"Confirmed write permissions on {directory}")
        except Exception as e:
            logger.error(f"Permission error on {directory}: {str(e)}")
            success = False
            
    return success


if __name__ == "__main__":
    logger = setup_logging()
    logger.info("Starting directory structure initialization")
    
    # Create required directories
    directory_success = create_required_directories()
    
    # Check file permissions
    permission_success = check_file_permissions()
    
    if directory_success and permission_success:
        logger.info("Directory structure initialization completed successfully")
        sys.exit(0)
    else:
        logger.error("Directory structure initialization failed")
        sys.exit(1)
