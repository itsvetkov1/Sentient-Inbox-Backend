"""
bcrypt Version Compatibility Fixer

This script fixes bcrypt version compatibility issues by installing the correct version
and applying necessary patches to ensure proper integration with passlib.

The script follows error handling protocols defined in error-handling.md, implementing
proper error detection, recovery mechanisms, and comprehensive logging.

Usage:
    python fix_bcrypt.py [--force]

Args:
    --force: Force reinstallation even if the correct version is already installed

Returns:
    0 if fix successful, 1 otherwise
"""

import argparse
import logging
import os
import subprocess
import sys
import importlib
import re
from pathlib import Path


def setup_logging():
    """Configure logging for bcrypt fix script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/bcrypt_fix.log", encoding="utf-8")
        ]
    )
    return logging.getLogger("bcrypt_fix")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Fix bcrypt version compatibility issues")
    parser.add_argument("--force", action="store_true", help="Force reinstallation even if correct version is installed")
    return parser.parse_args()


def check_current_version():
    """
    Check the currently installed bcrypt version.
    
    Implements proper version detection with error handling
    and version parsing following system specifications.
    
    Returns:
        tuple: (version_string, is_compatible)
    """
    try:
        # Try to import bcrypt
        import bcrypt
        
        # Try to get version from different attributes
        version = None
        
        # Check for __version__ attribute
        if hasattr(bcrypt, "__version__"):
            version = bcrypt.__version__
        # Check for __about__ attribute with __version__
        elif hasattr(bcrypt, "__about__") and hasattr(bcrypt.__about__, "__version__"):
            version = bcrypt.__about__.__version__
        # Check for _bcrypt attribute with __version__
        elif hasattr(bcrypt, "_bcrypt") and hasattr(bcrypt._bcrypt, "__version__"):
            version = bcrypt._bcrypt.__version__
        
        # If we couldn't get the version through attributes, try regex on __file__
        if not version and hasattr(bcrypt, "__file__"):
            # Try to extract version from the file path
            version_match = re.search(r'bcrypt-([0-9.]+)', bcrypt.__file__)
            if version_match:
                version = version_match.group(1)
        
        # If still no version, try using pkg_resources
        if not version:
            try:
                import pkg_resources
                version = pkg_resources.get_distribution("bcrypt").version
            except (ImportError, pkg_resources.DistributionNotFound):
                pass
        
        # Determine if compatible version (4.0.x)
        is_compatible = version and version.startswith("4.0.")
        
        return version, is_compatible
        
    except ImportError:
        return None, False
    except Exception as e:
        logging.error(f"Error detecting bcrypt version: {e}")
        return None, False


def uninstall_bcrypt():
    """
    Uninstall any existing bcrypt installations.
    
    Implements proper package uninstallation with error handling
    and dependency management following system specifications.
    
    Returns:
        bool: True if uninstallation successful, False otherwise
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "bcrypt"],
            check=True,
            capture_output=True,
            text=True
        )
        return "Successfully uninstalled" in result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"Error uninstalling bcrypt: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"General error during bcrypt uninstallation: {e}")
        return False


def install_compatible_bcrypt():
    """
    Install a compatible version of bcrypt (4.0.1).
    
    Implements proper package installation with error handling
    and version verification following system specifications.
    
    Returns:
        bool: True if installation successful, False otherwise
    """
    try:
        # Install specific version
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "bcrypt==4.0.1"],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Verify installation
        if "Successfully installed bcrypt-4.0.1" in result.stdout:
            return True
            
        # Double-check with check_current_version
        _, is_compatible = check_current_version()
        return is_compatible
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Error installing bcrypt: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"General error during bcrypt installation: {e}")
        return False


def apply_patches():
    """
    Apply necessary patches to ensure bcrypt compatibility with passlib.
    
    Implements targeted patches for known compatibility issues
    with proper error handling and validation.
    
    Returns:
        bool: True if patches applied successfully, False otherwise
    """
    try:
        # Try to locate passlib installation
        import passlib
        passlib_dir = Path(passlib.__file__).parent
        bcrypt_handler_file = passlib_dir / "handlers" / "bcrypt.py"
        
        if not bcrypt_handler_file.exists():
            logging.warning(f"Could not find passlib bcrypt handler at {bcrypt_handler_file}")
            return False
            
        # Read the bcrypt handler file
        with open(bcrypt_handler_file, 'r') as f:
            content = f.read()
            
        # Check if patching is needed
        if "_load_backend_mixin" in content and "__about__" in content:
            # Apply the patch
            patched_content = content.replace(
                "version = _bcrypt.__about__.__version__",
                "version = getattr(_bcrypt, '__version__', '4.0.1')"
            )
            
            # Write the patched file
            with open(bcrypt_handler_file, 'w') as f:
                f.write(patched_content)
                
            logging.info("Applied patch to passlib bcrypt handler")
            return True
        else:
            logging.info("Patching not needed or incompatible handler format")
            return True  # Return True as patching wasn't needed
            
    except ImportError:
        logging.warning("Could not import passlib, skipping patches")
        return True  # Not critical if passlib