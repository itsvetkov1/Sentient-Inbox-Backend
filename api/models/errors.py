"""
Error Response Models

Defines standardized error response models for consistent
error handling across the API surface.

Design Considerations:
- Consistent error structure for client processing
- Comprehensive error metadata for debugging
- Clear error codes and messages
- Proper timestamp handling
"""

from datetime import datetime
from typing import Dict, Optional, Any, List

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Standardized error response model for API errors.
    
    Provides consistent error structure with comprehensive
    metadata for client understanding and debugging.
    """
    status: str = Field(
        default="error",
        description="Error status indicator"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    error_code: str = Field(
        ...,
        description="Machine-readable error code"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )


class ValidationErrorItem(BaseModel):
    """
    Validation error detail model for data validation errors.
    
    Contains specific information about field validation failures.
    """
    loc: List[str] = Field(
        ...,
        description="Error location (field path)"
    )
    msg: str = Field(
        ...,
        description="Error message"
    )
    type: str = Field(
        ...,
        description="Error type"
    )


class ValidationErrorResponse(ErrorResponse):
    """
    Enhanced error response for validation errors.
    
    Extends standard error response with field-specific
    validation error details.
    """
    validation_errors: List[ValidationErrorItem] = Field(
        ...,
        description="List of specific validation errors"
    )