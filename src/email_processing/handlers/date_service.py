"""
Comprehensive date handling service for email processing system.

This module provides robust date parsing and management capabilities,
specifically handling email date formats per RFC 2822 and other common
formats encountered in email processing.

Design Considerations:
- Robust parsing of multiple date formats
- Timezone-aware processing
- Comprehensive error handling
- Detailed logging for debugging
"""

import email.utils
import logging
from datetime import datetime, timezone
from typing import Tuple, Optional
from zoneinfo import ZoneInfo
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ParsedDate:
    """Container for parsed date results with metadata."""
    datetime: datetime
    original: str
    confidence: float
    source_format: str

class EmailDateService:
    """
    Manages date parsing and validation for email processing.
    
    Implements comprehensive date handling with support for:
    - RFC 2822 email dates
    - ISO format dates
    - Common date variations
    - Timezone handling
    """
    
    # Common date format patterns for validation
    DATE_FORMATS = [
        "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822
        "%Y-%m-%dT%H:%M:%S%z",       # ISO format
        "%Y-%m-%d %H:%M:%S%z",       # Common variant
        "%Y-%m-%d %H:%M:%S"          # Simple format
    ]
    
    @classmethod
    def parse_email_date(cls, date_str: str, default_timezone: str = "UTC") -> Tuple[datetime, bool]:
        """
        Parse email date string with comprehensive format handling.
        
        Implements multi-stage parsing with fallbacks:
        1. RFC 2822 parsing
        2. ISO format attempt
        3. Common format patterns
        4. Timezone normalization
        
        Args:
            date_str: Date string to parse
            default_timezone: Timezone to use if none specified
            
        Returns:
            Tuple of (parsed datetime, success flag)
        """
        if not date_str:
            logger.warning("Empty date string provided")
            return datetime.now(ZoneInfo(default_timezone)), False
            
        try:
            # First attempt: RFC 2822 parsing
            email_tuple = email.utils.parsedate_tz(date_str)
            if email_tuple:
                timestamp = email.utils.mktime_tz(email_tuple)
                return datetime.fromtimestamp(timestamp, timezone.utc), True
                
            # Second attempt: Direct ISO parsing
            try:
                dt = datetime.fromisoformat(date_str)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=ZoneInfo(default_timezone))
                return dt, True
            except ValueError:
                pass
                
            # Third attempt: Common formats
            for fmt in cls.DATE_FORMATS:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=ZoneInfo(default_timezone))
                    return dt, True
                except ValueError:
                    continue
                    
            # Final attempt: Extract components
            return cls._extract_date_components(date_str, default_timezone)
            
        except Exception as e:
            logger.error(f"Date parsing failed for '{date_str}': {str(e)}")
            return datetime.now(ZoneInfo(default_timezone)), False
            
    @classmethod
    def _extract_date_components(cls, date_str: str, default_timezone: str) -> Tuple[datetime, bool]:
        """
        Extract date components from non-standard format strings.
        
        Implements pattern-based extraction for dates that don't match
        standard formats but contain recognizable components.
        
        Args:
            date_str: Date string to parse
            default_timezone: Default timezone to apply
            
        Returns:
            Tuple of (datetime, success flag)
        """
        try:
            # Extract basic date components using regex
            date_pattern = r"(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(\d{4})"
            time_pattern = r"(\d{1,2}):(\d{2})(?::(\d{2}))?"
            zone_pattern = r"([+-]\d{4}|[A-Z]{3})"
            
            date_match = re.search(date_pattern, date_str, re.IGNORECASE)
            time_match = re.search(time_pattern, date_str)
            zone_match = re.search(zone_pattern, date_str)
            
            if not date_match:
                return datetime.now(ZoneInfo(default_timezone)), False
                
            # Parse date components
            day = int(date_match.group(1))
            month = cls._month_to_number(date_match.group(2))
            year = int(date_match.group(3))
            
            # Parse time components
            hour = minute = second = 0
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                second = int(time_match.group(3)) if time_match.group(3) else 0
                
            # Create datetime with timezone
            dt = datetime(year, month, day, hour, minute, second)
            if zone_match:
                try:
                    if len(zone_match.group(1)) == 5:  # +HHMM format
                        offset = int(zone_match.group(1)[:3]) * 3600 + int(zone_match.group(1)[3:]) * 60
                        dt = dt.replace(tzinfo=timezone(timedelta(seconds=offset)))
                    else:  # Timezone abbreviation
                        dt = dt.replace(tzinfo=ZoneInfo(default_timezone))
                except Exception:
                    dt = dt.replace(tzinfo=ZoneInfo(default_timezone))
            else:
                dt = dt.replace(tzinfo=ZoneInfo(default_timezone))
                
            return dt, True
            
        except Exception as e:
            logger.error(f"Component extraction failed for '{date_str}': {str(e)}")
            return datetime.now(ZoneInfo(default_timezone)), False
            
    @staticmethod
    def _month_to_number(month: str) -> int:
        """Convert month name to number."""
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        return months[month.lower()[:3]]
        
    @classmethod
    def format_iso(cls, dt: datetime) -> str:
        """
        Format datetime as ISO string with timezone.
        
        Ensures consistent ISO format output while maintaining
        timezone information for accurate timestamp representation.
        
        Args:
            dt: Datetime object to format
            
        Returns:
            ISO formatted datetime string
        """
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.isoformat()
        
    @classmethod
    def is_valid_date(cls, date_str: str) -> bool:
        """
        Validate date string format.
        
        Implements comprehensive validation for supported date formats.
        
        Args:
            date_str: Date string to validate
            
        Returns:
            Boolean indicating if date string is valid
        """
        try:
            parsed_date, success = cls.parse_email_date(date_str)
            return success
        except Exception:
            return False