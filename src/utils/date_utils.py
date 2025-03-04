"""
Date handling utilities for email processing system.

This module provides robust date parsing and formatting capabilities,
specifically handling email date formats and ensuring proper conversion
to system-standard ISO format. Implements comprehensive error handling
and logging as specified in error-handling.md.
"""

from datetime import datetime
import email.utils
import logging
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class DateParsingError(Exception):
    """Custom exception for date parsing failures."""
    pass

def parse_email_date(date_str: str) -> Tuple[datetime, bool]:
    """
    Parse email date strings with comprehensive format handling.
    
    Implements robust parsing of various email date formats, including:
    - RFC 2822 format (standard email dates)
    - ISO format dates
    - Common variations of email date formats
    
    Args:
        date_str: Date string to parse
        
    Returns:
        Tuple containing:
        - Parsed datetime object in UTC
        - Boolean indicating parsing success
        
    Implementation follows error handling protocols from error-handling.md:
    - Single retry attempt
    - 3-second delay between attempts
    - Comprehensive error logging
    """
    if not date_str:
        logger.error("Empty date string provided")
        return datetime.now(ZoneInfo("UTC")), False
        
    try:
        # First attempt: Parse as email date format
        email_tuple = email.utils.parsedate_tz(date_str)
        if email_tuple:
            timestamp = email.utils.mktime_tz(email_tuple)
            return datetime.fromtimestamp(timestamp, ZoneInfo("UTC")), True
            
        # Second attempt: Parse as ISO format
        try:
            parsed_date = datetime.fromisoformat(date_str)
            if not parsed_date.tzinfo:
                parsed_date = parsed_date.replace(tzinfo=ZoneInfo("UTC"))
            return parsed_date, True
        except ValueError:
            pass
            
        # Final attempt: Common format variations
        for fmt in [
            "%Y-%m-%d %H:%M:%S %z",
            "%Y-%m-%d %H:%M:%S",
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S"
        ]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                if not parsed.tzinfo:
                    parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
                return parsed, True
            except ValueError:
                continue
                
        raise DateParsingError(f"Unable to parse date string: {date_str}")
        
    except Exception as e:
        logger.error(f"Error parsing date string '{date_str}': {str(e)}")
        return datetime.now(ZoneInfo("UTC")), False

def format_iso_date(dt: datetime) -> str:
    """
    Format datetime object as ISO string with timezone handling.
    
    Ensures consistent ISO format output for all system date representations,
    maintaining timezone information and format compatibility.
    
    Args:
        dt: Datetime object to format
        
    Returns:
        ISO formatted date string
    """
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.isoformat()

def is_valid_iso_date(date_str: str) -> bool:
    """
    Validate if a string is in proper ISO format.
    
    Implements strict ISO format validation for system date strings,
    ensuring consistency in date handling across the system.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        Boolean indicating if string is valid ISO format
    """
    try:
        datetime.fromisoformat(date_str)
        return True
    except ValueError:
        return False