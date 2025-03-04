# content_processor.py

from typing import Dict, Optional, List, Tuple, Set
from bs4 import BeautifulSoup
import re
import logging
from dataclasses import dataclass
from datetime import datetime
import email.utils
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

@dataclass
class ProcessedContent:
    """
    Structured container for processed content results.
    """
    content: str
    metadata: Dict[str, any]
    token_estimate: int
    processing_stats: Dict[str, any]
    extracted_dates: Set[str] = None

class EmailDateService:
    """
    Enhanced date handling service with proper RFC 2822 and ISO 8601 support
    """
    
    @staticmethod
    def parse_email_date(date_str: str) -> Tuple[datetime, bool]:
        """
        Robust email date parsing with fallback strategies
        """
        try:
            # Try RFC 2822 parsing first
            email_tuple = email.utils.parsedate_tz(date_str)
            if email_tuple:
                timestamp = email.utils.mktime_tz(email_tuple)
                dt = datetime.fromtimestamp(timestamp, ZoneInfo("UTC"))
                return dt, True

            # Fallback to ISO 8601 parsing
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')), True
            except ValueError:
                pass

            # Additional fallback formats
            for fmt in ('%a, %d %b %Y %H:%M:%S %z',
                        '%d %b %Y %H:%M:%S %z',
                        '%Y-%m-%d %H:%M:%S%z'):
                try:
                    return datetime.strptime(date_str, fmt), True
                except ValueError:
                    continue

            return None, False
        except Exception as e:
            logger.warning(f"Date parsing failed for '{date_str}': {e}")
            return None, False

    @staticmethod
    def format_iso(dt: datetime) -> str:
        """Format datetime to ISO 8601 with timezone"""
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.isoformat()

class DateProcessor:
    """
    Enhanced date pattern recognition and validation
    """
    
    DATE_PATTERNS = [
        r'\w{3},\s+\d{1,2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s+(?:[+-]\d{4}|[A-Z]{3})',
        r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?',
        r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?',
        r'\d{1,2}-\d{1,2}-\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?',
        r'\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?',
        r'(?:today|tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))',
    ]

    @classmethod
    def extract_dates(cls, content: str) -> Set[str]:
        dates = set()
        for pattern in cls.DATE_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                date_str = match.group()
                dt, success = EmailDateService.parse_email_date(date_str)
                if success:
                    dates.add(EmailDateService.format_iso(dt))
                else:
                    dates.add(date_str)
        return dates

class ContentPreprocessor:
    """
    Main content preprocessing implementation with enhanced date handling
    """
    
    def __init__(self, max_tokens: int = 4000, preserve_patterns: Optional[List[str]] = None, config: Optional[Dict] = None):
        self.max_tokens = max_tokens
        self.preserve_patterns = preserve_patterns or [
            r'meeting\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?',
            r'schedule.*meeting',
            r'discuss.*at\s+\d{1,2}(?::\d{2})?',
            r'conference.*\d{1,2}(?::\d{2})?',
            r'appointment.*\d{1,2}(?::\d{2})?'
        ]
        self.config = config or {}
    
    def preprocess_content(self, content: str) -> ProcessedContent:
        processing_stats = {"original_length": len(content)}
        
        cleaned_content = self._clean_html(content)
        processing_stats["cleaned_length"] = len(cleaned_content)
        
        extracted_dates = DateProcessor.extract_dates(cleaned_content)
        processing_stats["dates_found"] = len(extracted_dates)
        
        extracted_info = self._extract_key_information(cleaned_content)
        processing_stats["extraction_success"] = bool(extracted_info)
        
        final_content = self._enforce_token_limit(extracted_info)
        processing_stats.update({
            "final_length": len(final_content),
            "estimated_tokens": len(final_content.split())
        })
        
        return ProcessedContent(
            content=final_content,
            metadata={
                "preserved_patterns": self._find_preserved_patterns(final_content),
                "date_patterns": list(extracted_dates)
            },
            token_estimate=processing_stats["estimated_tokens"],
            processing_stats=processing_stats,
            extracted_dates=extracted_dates
        )

    # Rest of the ContentPreprocessor methods remain unchanged
    # (_clean_html, _extract_key_information, _enforce_token_limit, _find_preserved_patterns)

class ContentProcessingError(Exception):
    pass