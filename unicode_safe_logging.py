"""
Encoding-Safe Logging Utility

Provides robust logging functionality with proper Unicode handling for
cross-platform compatibility, specifically addressing Windows console
encoding limitations while maintaining visual indicators.

This module implements proper error handling and fallback mechanisms
following system specifications from error-handling.md.
"""

import logging
import os
import sys
from typing import Optional, Dict, Any
import platform


class SafeFormatter(logging.Formatter):
    """
    Custom log formatter with encoding-safe character substitution.
    
    Implements automatic substitution of Unicode symbols with ASCII
    alternatives when operating in environments with limited encoding
    support, ensuring consistent logging across all platforms.
    """
    
    # Define symbol mappings for Unicode -> ASCII-safe alternatives
    SYMBOL_MAP = {
        # Success symbols
        "✓": "√",  # Checkmark -> ASCII approximation
        "✅": "[SUCCESS]",
        
        # Warning symbols
        "⚠": "!",  # Warning symbol -> Exclamation mark
        "⚠️": "[WARNING]",
        
        # Error symbols
        "❌": "x",  # X mark -> ASCII 'x'
        "🔴": "[ERROR]",
        
        # Info symbols
        "ℹ": "i",  # Info symbol -> ASCII 'i'
        "🔵": "[INFO]",
        
        # Other symbols
        "→": "->",  # Right arrow -> ASCII approximation
        "←": "<-",  # Left arrow -> ASCII approximation
        "•": "*",   # Bullet point -> Asterisk
    }
    
    # Extra symbols that should be replaced in Windows environments
    WINDOWS_EXTRA_REPLACEMENTS = {
        "√": "OK",
        "✓": "OK",
        "⚠": "WARNING",
        "❌": "ERROR",
        "•": "-"
    }
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None,
                 style: str = '%', validate: bool = True):
        """
        Initialize formatter with format string and symbol replacement.
        
        Args:
            fmt: Format string for log messages
            datefmt: Date format string
            style: Style of format string (%, {, or $)
            validate: Whether to validate the format string
        """
        super().__init__(fmt, datefmt, style, validate)
        
        # Determine if we're on Windows to apply additional replacements
        self.is_windows = platform.system() == "Windows"
        
        # Check for explicit encoding override environment variable
        self.force_ascii = os.environ.get("FORCE_ASCII_LOGGING", "0").lower() in ("1", "true", "yes")
        
        # Check terminal encoding capabilities
        self.limited_encoding = self._has_limited_encoding()
    
    def _has_limited_encoding(self) -> bool:
        """
        Detect if the current environment has limited encoding support.
        
        Implements comprehensive encoding detection for terminals,
        identifying environments that may have problematic Unicode support.
        
        Returns:
            bool: True if environment has limited encoding support
        """
        # Always treat as limited encoding if forcing ASCII
        if self.force_ascii:
            return True
            
        # Windows command prompt and PowerShell often have encoding issues
        if self.is_windows:
            # Check if we're in Windows Terminal which has better Unicode support
            if "WT_SESSION" in os.environ:
                return False
                
            # Check if PYTHONIOENCODING is explicitly set to UTF-8
            if os.environ.get("PYTHONIOENCODING", "").lower() == "utf-8":
                return False
                
            # Default to limited encoding for standard Windows console
            return True
            
        # Most Unix-like systems have good Unicode support by default
        return False
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with encoding-safe character substitution.
        
        Overrides the standard formatter to replace Unicode symbols
        with ASCII alternatives when necessary based on the detected
        environment capabilities.
        
        Args:
            record: Log record to format
            
        Returns:
            str: Formatted log message with encoding-safe characters
        """
        # First, let the parent formatter do its job
        formatted_message = super().format(record)
        
        # If we have limited encoding, apply substitutions
        if self.limited_encoding:
            # Apply standard substitutions
            for unicode_char, ascii_char in self.SYMBOL_MAP.items():
                formatted_message = formatted_message.replace(unicode_char, ascii_char)
            
            # Apply Windows-specific extra substitutions if needed
            if self.is_windows:
                for unicode_char, ascii_char in self.WINDOWS_EXTRA_REPLACEMENTS.items():
                    formatted_message = formatted_message.replace(unicode_char, ascii_char)
        
        return formatted_message


def configure_safe_logging(
    name: Optional[str] = None,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_str: Optional[str] = None
) -> logging.Logger:
    """
    Configure logging with encoding-safe formatting and proper error handling.
    
    Creates a logger with proper Unicode character handling for cross-platform
    compatibility, ensuring consistent logging output across environments.
    
    Args:
        name: Logger name (defaults to root logger if None)
        level: Logging level
        log_file: Optional log file path
        format_str: Custom format string for log messages
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear any existing handlers to avoid duplication
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Default format string if not provided
    if format_str is None:
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create safe formatter
    formatter = SafeFormatter(format_str)
    
    # Create console handler with safe encoding
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if log file specified
    if log_file:
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # Create file handler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Log to console if file handler creation fails
            console_handler.setLevel(logging.WARNING)
            logger.warning(f"Failed to create log file handler: {str(e)}")
    
    return logger


# Constants for ASCII-art status indicators (Windows-safe)
STATUS_INDICATORS = {
    "success": "[+] ",
    "error": "[-] ",
    "warning": "[!] ",
    "info": "[*] "
}


def get_status_prefix(status_type: str) -> str:
    """
    Get encoding-safe status prefix for log messages.
    
    Provides consistent status indicators that work across platforms,
    including environments with limited encoding support.
    
    Args:
        status_type: Type of status (success, error, warning, info)
        
    Returns:
        str: Encoding-safe status prefix
    """
    return STATUS_INDICATORS.get(status_type.lower(), "")
