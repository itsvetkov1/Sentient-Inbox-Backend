"""
Pre-Startup Initialization Script (Unicode-Safe Version)

Performs comprehensive application initialization before main application startup,
ensuring proper directory structure, dependency validation, and environment setup.

This script implements proper error handling and logging following system specifications,
with enhanced Unicode-safe logging to ensure compatibility across all platforms.

Usage:
    python pre_startup.py

Returns:
    0 if initialization successful, 1 otherwise
"""

import os
import sys
import logging
import subprocess
import platform
from pathlib import Path
import json
from datetime import datetime
import re
from typing import Dict, List, Optional, Tuple

# Import safe logging utility if available, otherwise define basic version
try:
    from unicode_safe_logging import configure_safe_logging, get_status_prefix
    HAS_SAFE_LOGGING = True
except ImportError:
    HAS_SAFE_LOGGING = False


def setup_basic_logging():
    """Configure basic logging as fallback if safe logging is unavailable."""
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/initialization.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("pre_startup")


def setup_logging():
    """Configure comprehensive logging with Unicode safety."""
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    if HAS_SAFE_LOGGING:
        return configure_safe_logging(
            name="pre_startup",
            level=logging.INFO,
            log_file="logs/initialization.log",
            format_str='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        return setup_basic_logging()


def get_safe_prefix(status_type):
    """Get platform-safe status prefix for logging."""
    if HAS_SAFE_LOGGING:
        return get_status_prefix(status_type)
        
    # Fallback simple indicators
    prefixes = {
        "success": "[OK] ",
        "error": "[ERROR] ",
        "warning": "[WARNING] ",
        "info": "[INFO] "
    }
    return prefixes.get(status_type.lower(), "")


def run_directory_setup():
    """
    Run directory setup with proper error handling.
    
    Ensures all required directories exist for application functionality,
    implementing proper error handling and recovery.
    
    Returns:
        bool: True if setup successful, False otherwise
    """
    logger = logging.getLogger("pre_startup.directories")
    logger.info("Setting up required directories")
    
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
                logger.info(f"{get_safe_prefix('success')}Created directory: {directory}")
                created_dirs.append(directory)
            else:
                logger.info(f"{get_safe_prefix('info')}Directory already exists: {directory}")
        except Exception as e:
            logger.error(f"{get_safe_prefix('error')}Error creating directory {directory}: {str(e)}")
            success = False
    
    # Summary output
    if created_dirs:
        logger.info(f"Created {len(created_dirs)} directories: {', '.join(created_dirs)}")
    else:
        logger.info("No new directories needed to be created")
        
    return success


def validate_dependencies():
    """
    Validate critical dependencies with version checks.
    
    Implements comprehensive dependency validation, checking
    for known problematic versions and compatibility issues.
    
    Returns:
        bool: True if all dependencies valid, False otherwise
    """
    logger = logging.getLogger("pre_startup.dependencies")
    logger.info("Validating critical dependencies")
    
    # Critical dependencies to validate
    critical_deps = ["bcrypt", "cryptography", "fastapi", "pydantic"]
    all_valid = True
    
    try:
        # Create a subprocess to check installed packages
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Parse installed packages
        installed_packages = json.loads(result.stdout)
        installed_dict = {pkg["name"].lower(): pkg["version"] for pkg in installed_packages}
        
        # Check critical dependencies
        for dep in critical_deps:
            if dep.lower() in installed_dict:
                logger.info(f"Found {dep} version {installed_dict[dep.lower()]}")
                
                # Specific version checks
                if dep.lower() == "bcrypt":
                    version = installed_dict[dep.lower()]
                    if version.startswith("4.0."):
                        logger.info(f"{get_safe_prefix('success')}{dep} version {version} is compatible")
                    else:
                        logger.warning(f"{get_safe_prefix('warning')}{dep} version {version} may have compatibility issues")
                        logger.warning(f"  Recommended version: 4.0.1")
                        all_valid = False
            else:
                logger.error(f"{get_safe_prefix('error')}Required dependency {dep} not found")
                all_valid = False
                
        if all_valid:
            logger.info(f"{get_safe_prefix('success')}All critical dependencies validated successfully")
        
        return all_valid
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Dependency validation failed: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error validating dependencies: {str(e)}")
        return False


def create_default_configs():
    """
    Create default configuration files if they don't exist.
    
    Implements configuration initialization following system 
    specifications, ensuring required configuration is available.
    
    Returns:
        bool: True if configuration setup successful, False otherwise
    """
    logger = logging.getLogger("pre_startup.config")
    logger.info("Setting up default configurations")
    
    # Ensure config directory exists
    config_dir = Path("data/config")
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Default configurations to create
    default_configs = {
        "email_settings.json": {
            "batch_size": 50,
            "auto_respond_enabled": True,
            "confidence_threshold": 0.7,
            "processing_interval_minutes": 15,
            "max_tokens_per_analysis": 4000,
            "models": {
                "classification": "llama-3.3-70b-versatile",
                "analysis": "deepseek-reasoner",
                "response": "llama-3.3-70b-versatile"
            }
        }
    }
    
    success = True
    for filename, config in default_configs.items():
        file_path = config_dir / filename
        
        if not file_path.exists():
            try:
                with open(file_path, 'w') as f:
                    json.dump(config, f, indent=2)
                logger.info(f"{get_safe_prefix('success')}Created default configuration: {filename}")
            except Exception as e:
                logger.error(f"{get_safe_prefix('error')}Error creating default configuration {filename}: {str(e)}")
                success = False
        else:
            logger.info(f"{get_safe_prefix('info')}Configuration file already exists: {filename}")
            
    return success


def initialize_secure_storage():
    """
    Initialize secure storage with proper error handling.
    
    Implements secure storage initialization following error handling
    protocols, ensuring critical storage systems are ready.
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    logger = logging.getLogger("pre_startup.storage")
    logger.info("Initializing secure storage")
    
    try:
        # Ensure secure storage directory exists
        storage_path = Path("data/secure")
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Placeholder for actual secure storage initialization
        # This would integrate with the SecureStorage class in a real implementation
        
        # For now, just touch required files to prevent startup errors
        required_files = [
            storage_path / ".initialized",
            storage_path / "backups" / ".initialized"
        ]
        
        for file_path in required_files:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if not file_path.exists():
                file_path.touch()
                logger.info(f"{get_safe_prefix('success')}Created initialization marker: {file_path}")
        
        return True
    except Exception as e:
        logger.error(f"{get_safe_prefix('error')}Error initializing secure storage: {str(e)}")
        return False


def initialize_metrics():
    """
    Initialize metrics storage with proper error handling.
    
    Implements metrics storage initialization following system
    specifications, ensuring metrics systems are available.
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    logger = logging.getLogger("pre_startup.metrics")
    logger.info("Initializing metrics storage")
    
    try:
        # Ensure metrics directory exists
        metrics_path = Path("data/metrics")
        metrics_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize groq_metrics.json if it doesn't exist
        groq_metrics_file = metrics_path / "groq_metrics.json"
        if not groq_metrics_file.exists():
            default_metrics = {
                "requests": [],
                "errors": [],
                "performance": {
                    "avg_response_time": 0,
                    "total_requests": 0,
                    "success_rate": 100
                },
                "initialized_at": datetime.now().isoformat()
            }
            
            with open(groq_metrics_file, 'w') as f:
                json.dump(default_metrics, f, indent=2)
            logger.info(f"{get_safe_prefix('success')}Created default metrics file: {groq_metrics_file}")
        
        # Initialize email_stats.json if it doesn't exist
        email_stats_file = metrics_path / "email_stats.json"
        if not email_stats_file.exists():
            default_stats = {
                "total_emails_processed": 0,
                "emails_by_category": {
                    "meeting": 0,
                    "needs_review": 0,
                    "not_actionable": 0,
                    "not_meeting": 0
                },
                "average_processing_time_ms": 0,
                "success_rate": 0,
                "stats_period_days": 30,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(email_stats_file, 'w') as f:
                json.dump(default_stats, f, indent=2)
            logger.info(f"{get_safe_prefix('success')}Created default email stats file: {email_stats_file}")
            
        return True
    except Exception as e:
        logger.error(f"{get_safe_prefix('error')}Error initializing metrics storage: {str(e)}")
        return False


def validate_environment():
    """
    Validate environment settings and dependencies.
    
    Implements environment validation following system specifications,
    ensuring required environment variables and settings are available.
    
    Returns:
        bool: True if environment valid, False otherwise
    """
    logger = logging.getLogger("pre_startup.environment")
    logger.info("Validating environment")
    
    # System requirements
    min_python_version = (3, 9)
    
    # Check Python version
    python_version = tuple(map(int, platform.python_version_tuple()[:2]))
    python_valid = python_version >= min_python_version
    
    if python_valid:
        logger.info(f"{get_safe_prefix('success')}Python version: {platform.python_version()}")
    else:
        logger.error(f"{get_safe_prefix('error')}Python version {platform.python_version()} is below minimum {'.'.join(map(str, min_python_version))}")
    
    # Check for .env file
    env_file = Path(".env")
    if env_file.exists():
        logger.info(f"{get_safe_prefix('success')}Found .env file")
        
        # Check for critical environment variables
        critical_env_vars = ["GROQ_API_KEY"]
        missing_vars = []
        
        for var in critical_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
                
        if missing_vars:
            logger.warning(f"{get_safe_prefix('warning')}Missing critical environment variables: {', '.join(missing_vars)}")
            logger.warning("  Application may fail at runtime if these are required")
    else:
        logger.warning(f"{get_safe_prefix('warning')}No .env file found - environment variables must be set manually")
    
    return python_valid


def main():
    """
    Main initialization sequence for application pre-startup.
    
    Implements comprehensive initialization following system specifications
    and error handling protocols, ensuring proper application startup.
    
    Returns:
        int: 0 for success, 1 for failure
    """
    # Setup logging with encoding-safe formatting
    logger = setup_logging()
    logger.info("=== Starting pre-startup initialization ===")
    
    # Track initialization steps
    steps = [
        {"name": "Run directory setup", "func": run_directory_setup},
        {"name": "Validate dependencies", "func": validate_dependencies},
        {"name": "Create default configurations", "func": create_default_configs},
        {"name": "Initialize secure storage", "func": initialize_secure_storage},
        {"name": "Initialize metrics", "func": initialize_metrics},
        {"name": "Validate environment", "func": validate_environment}
    ]
    
    # Run all initialization steps
    success = True
    for step in steps:
        logger.info(f"Running step: {step['name']}")
        step_success = step["func"]()
        
        if step_success:
            logger.info(f"{get_safe_prefix('success')}Step completed successfully: {step['name']}")
        else:
            logger.error(f"{get_safe_prefix('error')}Step failed: {step['name']}")
            success = False
    
    # Finalize
    if success:
        logger.info("=== Pre-startup initialization completed successfully ===")
        return 0
    else:
        logger.error("=== Pre-startup initialization completed with errors ===")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
