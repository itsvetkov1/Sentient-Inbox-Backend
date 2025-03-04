"""
Global Exception Handlers

Implements comprehensive exception handling middleware with consistent
error responses and proper logging for all API exceptions.

Design Considerations:
- Standardized error response format
- Comprehensive error type coverage
- Appropriate status code mapping
- Detailed error logging
"""

import json
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Union, List

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse as StarletteJSONResponse
from pydantic import ValidationError

from api.models.errors import ErrorResponse, ValidationErrorResponse, ValidationErrorItem

# Configure logging
logger = logging.getLogger(__name__)

# Custom JSON Encoder to handle datetime serialization
class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def serialize_json(obj):
    """Serialize object to JSON string with datetime support."""
    return json.dumps(obj, cls=DateTimeEncoder)

# Custom JSONResponse that automatically handles datetime serialization
class JSONResponse(StarletteJSONResponse):
    """Custom JSONResponse that handles datetime serialization."""
    def render(self, content):
        return serialize_json(content).encode("utf-8")

def add_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI application.
    
    Implements comprehensive exception handling for all relevant
    error types with proper status code mapping and logging.
    
    Args:
        app: FastAPI application instance
    """
    # Register handlers for specific exception types
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered")


async def http_exception_handler(
    request: Request, 
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle HTTP exceptions with standardized format.
    
    Provides consistent error response format for HTTP exceptions
    with proper status codes and error details.
    
    Args:
        request: Request that caused exception
        exc: HTTP exception
        
    Returns:
        Standardized error response
    """
    # Log the exception
    log_exception(request, exc, exc.status_code)
    
    # Create error response
    error_response = ErrorResponse(
        status="error",
        message=exc.detail,
        error_code=f"HTTP_{exc.status_code}",
        details=getattr(exc, "details", None),
        timestamp=datetime.utcnow()
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()  # Use model_dump() in Pydantic V2
    )


async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle request validation errors with detailed field information.
    
    Provides enhanced error responses for validation errors with
    field-specific detail and proper error formatting.
    
    Args:
        request: Request that caused exception
        exc: Validation exception
        
    Returns:
        Detailed validation error response
    """
    # Log the exception
    log_exception(request, exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
    
    # Format validation errors
    validation_errors = []
    for error in exc.errors():
        # Convert loc tuple to list of strings for Pydantic V2
        loc = [str(loc_item) for loc_item in error["loc"]]
        validation_errors.append(
            ValidationErrorItem(
                loc=loc,
                msg=error["msg"],
                type=error["type"]
            )
        )
    
    # Create error response
    error_response = ValidationErrorResponse(
        status="error",
        message="Request validation error",
        error_code="VALIDATION_ERROR",
        details={"errors": str(exc)},
        validation_errors=validation_errors,
        timestamp=datetime.utcnow()
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump()  # Use model_dump() in Pydantic V2
    )


async def pydantic_validation_handler(
    request: Request, 
    exc: ValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors with detailed information.
    
    Provides enhanced error responses for model validation errors
    with field-specific detail and proper error formatting.
    
    Args:
        request: Request that caused exception
        exc: Pydantic validation exception
        
    Returns:
        Detailed validation error response
    """
    # Log the exception
    log_exception(request, exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
    
    # Format validation errors
    validation_errors = []
    for error in exc.errors():
        # Convert loc tuple to list of strings for Pydantic V2
        loc = [str(loc_item) for loc_item in error["loc"]]
        validation_errors.append(
            ValidationErrorItem(
                loc=loc,
                msg=error["msg"],
                type=error["type"]
            )
        )
    
    # Create error response
    error_response = ValidationErrorResponse(
        status="error",
        message="Data validation error",
        error_code="VALIDATION_ERROR",
        details={"errors": str(exc)},
        validation_errors=validation_errors,
        timestamp=datetime.utcnow()
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump()  # Use model_dump() in Pydantic V2
    )


async def general_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """
    Handle all unhandled exceptions with safe error responses.
    
    Provides consistent error handling for unexpected exceptions
    with proper error sanitization and comprehensive logging.
    
    Args:
        request: Request that caused exception
        exc: Unhandled exception
        
    Returns:
        Safe error response
    """
    # Log the exception with full traceback
    log_exception(request, exc, status.HTTP_500_INTERNAL_SERVER_ERROR, include_traceback=True)
    
    # Create sanitized error response
    error_response = ErrorResponse(
        status="error",
        message="An unexpected error occurred",
        error_code="INTERNAL_SERVER_ERROR",
        details={"type": exc.__class__.__name__},
        timestamp=datetime.utcnow()
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump()  # Use model_dump() in Pydantic V2
    )


def log_exception(
    request: Request, 
    exc: Exception, 
    status_code: int,
    include_traceback: bool = False
) -> None:
    """
    Log exception with request context and appropriate severity.
    
    Implements comprehensive exception logging with request details,
    error context, and configurable traceback inclusion.
    
    Args:
        request: Request that caused exception
        exc: Exception instance
        status_code: HTTP status code
        include_traceback: Whether to include full traceback
    """
    # Determine log level based on status code
    if status_code >= 500:
        log_level = logging.ERROR
    elif status_code >= 400:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO
    
    # Create error message
    error_message = f"Exception during request to {request.method} {request.url.path}"
    error_details = {
        "status_code": status_code,
        "error_type": exc.__class__.__name__,
        "error_message": str(exc),
        "client_host": request.client.host if request.client else "unknown"
    }
    
    # Add traceback for server errors
    if include_traceback:
        error_details["traceback"] = traceback.format_exc()
    
    # Log with appropriate level
    logger.log(log_level, error_message, extra={"error_details": error_details})