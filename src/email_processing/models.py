"""
Shared data models for email processing.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

class EmailTopic(Enum):
    """Supported email topics for classification."""
    MEETING = "meeting"
    UNKNOWN = "unknown"
    # Add new topics here as more agents are introduced
    # Example: TASK = "task"
    # Example: REPORT = "report"

@dataclass
class EmailMetadata:
    """Metadata about a processed email."""
    message_id: str
    subject: str
    sender: str
    received_at: datetime
    topic: EmailTopic
    requires_response: bool
    raw_content: str
    analysis_data: Optional[Dict] = None
