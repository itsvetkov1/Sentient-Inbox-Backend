from typing import Dict, Optional, List, Tuple, Set
from bs4 import BeautifulSoup
import re
import logging
from dataclasses import dataclass
from datetime import datetime
import email.utils
from zoneinfo import ZoneInfo
from src.email_processing.base import BaseEmailAnalyzer as BaseProcessor

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
        """Extract dates from content using defined patterns"""
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
        """Process and structure email content"""
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

    def _clean_html(self, content: str) -> str:
        """Clean HTML content from email body"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
                
            # Get text content
            text = soup.get_text()
            
            # Break into lines and remove leading/trailing space
            lines = (line.strip() for line in text.splitlines())
            
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            
            # Drop blank lines
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            logger.warning(f"HTML cleaning failed: {e}, returning original content")
            return content.strip()

    def _extract_key_information(self, content: str) -> str:
        """Extract key information from email content"""
        try:
            # Keep content manageable - limit to relevant paragraphs
            paragraphs = content.split('\n\n')
            if len(paragraphs) > self.config.get('max_paragraphs', 3):
                # Keep first paragraph, any paragraphs with preserved patterns, and last paragraph
                selected_paragraphs = [paragraphs[0]]
                
                # Check middle paragraphs for important patterns
                for paragraph in paragraphs[1:-1]:
                    if any(re.search(pattern, paragraph, re.IGNORECASE) 
                          for pattern in self.preserve_patterns):
                        selected_paragraphs.append(paragraph)
                        
                # Add last paragraph if we haven't exceeded max
                if len(selected_paragraphs) < self.config.get('max_paragraphs', 3):
                    selected_paragraphs.append(paragraphs[-1])
                    
                content = '\n\n'.join(selected_paragraphs)
            
            # Extract dates from content
            dates = DateProcessor.extract_dates(content)
            
            # Find and preserve important patterns
            preserved_content = content
            for pattern in self.preserve_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    preserved_content = preserved_content.replace(
                        match.group(), f"__PRESERVED__{match.group()}__PRESERVED__"
                    )
            
            # Clean up extra whitespace while preserving intentional line breaks
            lines = [line.strip() for line in preserved_content.splitlines()]
            cleaned_content = '\n'.join(line for line in lines if line)
            
            # Restore preserved patterns
            final_content = cleaned_content.replace('__PRESERVED__', '')
            
            # Add extracted dates to content if not already present
            if dates:
                date_section = "\n\nExtracted Dates:\n" + "\n".join(sorted(dates))
                final_content = final_content + date_section
                
            return final_content
            
        except Exception as e:
            logger.error(f"Error extracting key information: {e}")
            return content

    def _enforce_token_limit(self, content: str) -> str:
        """Enforce token limit while preserving key information"""
        if not content:
            return ""
            
        # Rough token estimation (words as proxy)
        words = content.split()
        if len(words) <= self.max_tokens:
            return content
            
        # Keep introduction and preserved patterns
        preserved_indices = set()
        for pattern in self.preserve_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                start_word = len(content[:match.start()].split())
                end_word = len(content[:match.end()].split())
                preserved_indices.update(range(start_word, end_word))
                
        # Build limited content
        limited_words = []
        for i, word in enumerate(words):
            # Keep start, end, and preserved patterns
            if (i < self.max_tokens // 3 or  
                i >= len(words) - (self.max_tokens // 3) or 
                i in preserved_indices):
                limited_words.append(word)
                
        return ' '.join(limited_words)

    def _find_preserved_patterns(self, content: str) -> List[str]:
        """Find all preserved patterns in content"""
        preserved = []
        for pattern in self.preserve_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                preserved.append(match.group())
        return preserved

class ContentProcessingError(Exception):
    """Custom exception for content processing errors"""
    pass
