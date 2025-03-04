"""
Email Data Models

Defines comprehensive data models for email processing operations
including analysis requests, responses, and metadata structures.

Design Considerations:
- Comprehensive field validation
- Type safety with clear annotations
- Consistent structure for client processing
- Proper documentation of data requirements
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from pydantic import BaseModel, Field, EmailStr, field_validator


class EmailSummary(BaseModel):
    """
    Summary model for email listings.
    
    Provides essential email information for list views
    with proper type safety and validation.
    """
    message_id: str = Field(
        ...,
        description="Unique email message identifier"
    )
    subject: str = Field(
        ...,
        description="Email subject line"
    )
    sender: str = Field(
        ...,
        description="Email sender address"
    )
    received_at: datetime = Field(
        ...,
        description="Email receive timestamp"
    )
    category: str = Field(
        ...,
        description="Email categorization result"
    )
    is_responded: bool = Field(
        default=False,
        description="Whether a response has been sent"
    )


class EmailListResponse(BaseModel):
    """
    Response model for paginated email listings.
    
    Implements comprehensive pagination metadata with
    proper email summary information.
    """
    emails: List[EmailSummary] = Field(
        default_factory=list,
        description="List of email summaries"
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of emails matching criteria"
    )
    limit: int = Field(
        ...,
        ge=1,
        description="Maximum emails per page"
    )
    offset: int = Field(
        ...,
        ge=0,
        description="Offset from start of results"
    )


class AnalysisMetadata(BaseModel):
    """
    Metadata for email analysis results.
    
    Provides comprehensive metadata about the analysis process
    with proper timestamp and result information.
    """
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Analysis timestamp"
    )
    model_version: str = Field(
        ...,
        description="Version of the analysis model used"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0, 
        le=1.0,
        description="Confidence score of analysis"
    )
    processing_time_ms: int = Field(
        ...,
        ge=0,
        description="Processing time in milliseconds"
    )


class EmailAnalysisRequest(BaseModel):
    """
    Request model for email analysis.
    
    Implements comprehensive request structure for email analysis
    with proper validation and field requirements.
    """
    content: str = Field(
        ...,
        description="Email content to analyze"
    )
    subject: str = Field(
        ...,
        description="Email subject line"
    )
    sender: str = Field(
        ...,
        description="Email sender address"
    )
    message_id: Optional[str] = Field(
        default=None,
        description="Optional message ID for tracking"
    )


class MeetingDetails(BaseModel):
    """
    Extracted meeting details from email analysis.
    
    Contains structured representation of meeting information
    extracted during email analysis with proper validation.
    """
    date: Optional[str] = Field(
        default=None,
        description="Extracted meeting date"
    )
    time: Optional[str] = Field(
        default=None,
        description="Extracted meeting time"
    )
    location: Optional[str] = Field(
        default=None,
        description="Extracted meeting location"
    )
    participants: Optional[List[str]] = Field(
        default=None,
        description="Extracted meeting participants"
    )
    agenda: Optional[str] = Field(
        default=None,
        description="Extracted meeting agenda or purpose"
    )
    missing_elements: List[str] = Field(
        default_factory=list,
        description="Required elements missing from meeting details"
    )
    
    @property
    def is_complete(self) -> bool:
        """Check if meeting details are complete."""
        return len(self.missing_elements) == 0


class EmailAnalysisResponse(BaseModel):
    """
    Response model for email analysis results.
    
    Provides comprehensive analysis results with structured
    data and metadata about the analysis process.
    """
    is_meeting_related: bool = Field(
        ...,
        description="Whether email is meeting-related"
    )
    category: str = Field(
        ...,
        description="Email categorization result"
    )
    recommended_action: str = Field(
        ...,
        description="Recommended action for the email"
    )
    meeting_details: Optional[MeetingDetails] = Field(
        default=None,
        description="Extracted meeting details if applicable"
    )
    suggested_response: Optional[str] = Field(
        default=None,
        description="Suggested response text if available"
    )
    metadata: AnalysisMetadata = Field(
        ...,
        description="Analysis process metadata"
    )


class EmailContent(BaseModel):
    """
    Email content model with comprehensive data.
    
    Implements complete email content representation with
    proper content formatting and metadata.
    """
    raw_content: str = Field(
        ...,
        description="Raw email content"
    )
    processed_content: Optional[str] = Field(
        default=None,
        description="Processed email content"
    )
    html_content: Optional[str] = Field(
        default=None,
        description="HTML email content if available"
    )
    attachments: List[str] = Field(
        default_factory=list,
        description="List of attachment filenames"
    )


class EmailDetailResponse(BaseModel):
    """
    Detailed email information for single email view.
    
    Provides comprehensive email details including content,
    analysis results, and processing metadata.
    """
    message_id: str = Field(
        ...,
        description="Unique email message identifier"
    )
    subject: str = Field(
        ...,
        description="Email subject line"
    )
    sender: str = Field(
        ...,
        description="Email sender address"
    )
    received_at: datetime = Field(
        ...,
        description="Email receive timestamp"
    )
    content: EmailContent = Field(
        ...,
        description="Email content details"
    )
    category: str = Field(
        ...,
        description="Email categorization result"
    )
    is_responded: bool = Field(
        default=False,
        description="Whether a response has been sent"
    )
    analysis_results: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detailed analysis results if available"
    )
    processing_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="History of processing operations"
    )


class EmailProcessingStats(BaseModel):
    """
    Statistics about email processing operations.
    
    Provides comprehensive statistics about email processing
    volume, categories, and performance metrics.
    """
    total_emails_processed: int = Field(
        ...,
        ge=0,
        description="Total number of emails processed"
    )
    emails_by_category: Dict[str, int] = Field(
        ...,
        description="Count of emails by category"
    )
    average_processing_time_ms: float = Field(
        ...,
        ge=0.0,
        description="Average processing time in milliseconds"
    )
    success_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Percentage of emails successfully processed"
    )
    stats_period_days: int = Field(
        default=30,
        ge=1,
        description="Period in days these statistics cover"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="When these statistics were last updated"
    )


class EmailSettings(BaseModel):
    """
    Email processing system settings.
    
    Implements comprehensive settings for email processing
    configuration with proper validation and defaults.
    """
    batch_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of emails to process in each batch"
    )
    auto_respond_enabled: bool = Field(
        default=True,
        description="Whether to automatically send responses"
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for automatic responses"
    )
    processing_interval_minutes: int = Field(
        default=15,
        ge=1,
        description="How often to process new emails in minutes"
    )
    max_tokens_per_analysis: int = Field(
        default=4000,
        ge=1000,
        description="Maximum tokens to use for email analysis"
    )
    models: Dict[str, str] = Field(
        default={
            "classification": "llama-3.3-70b-versatile",
            "analysis": "deepseek-reasoner",
            "response": "llama-3.3-70b-versatile"
        },
        description="Model configuration for each pipeline stage"
    )
    
    @field_validator("models")
    @classmethod
    def validate_models(cls, models: Dict[str, str]) -> Dict[str, str]:
        """Validate that all required models are specified."""
        required_keys = {"classification", "analysis", "response"}
        if not all(key in models for key in required_keys):
            missing = required_keys - set(models.keys())
            raise ValueError(f"Missing required model configurations: {missing}")
        return models
