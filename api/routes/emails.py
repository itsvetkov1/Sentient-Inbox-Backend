"""
Email Processing API Routes

Implements comprehensive API endpoints for email processing operations,
including triggering analysis, retrieving results, and managing settings.

Design Considerations:
- Secure endpoint access with proper authentication
- Comprehensive input validation
- Clean separation of concerns
- Detailed response formatting
"""

import logging
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from pydantic import BaseModel

from api.auth.service import require_admin, require_process, require_view
from api.models.emails import (
    EmailAnalysisRequest, 
    EmailAnalysisResponse,
    EmailListResponse,
    EmailDetailResponse,
    EmailProcessingStats,
    EmailSettings
)
from api.services.email_service import EmailService, get_email_service

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/emails", tags=["Email Processing"])


@router.get(
    "/",
    response_model=EmailListResponse,
    summary="Get list of processed emails",
    dependencies=[Depends(require_view)]
)
async def get_emails(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of emails to return"),
    offset: int = Query(0, ge=0, description="Number of emails to skip"),
    category: Optional[str] = Query(None, description="Filter by email category"),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Retrieve a list of processed emails with optional filtering.
    
    Provides paginated access to email data with comprehensive
    filtering options and proper authorization.
    
    Args:
        limit: Maximum number of emails to return
        offset: Number of emails to skip (for pagination)
        category: Optional category filter
        
    Returns:
        List of email summaries with pagination metadata
    """
    try:
        emails, total = await email_service.get_emails(limit, offset, category)
        
        return EmailListResponse(
            emails=emails,
            total=total,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Error retrieving emails: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve emails: {str(e)}"
        )


@router.get(
    "/{message_id}",
    response_model=EmailDetailResponse,
    summary="Get detailed email information",
    dependencies=[Depends(require_view)]
)
async def get_email_detail(
    message_id: str = Path(..., description="Email message ID"),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Retrieve detailed information about a specific email.
    
    Provides comprehensive email details including content,
    analysis results, and processing metadata.
    
    Args:
        message_id: Unique email message ID
        
    Returns:
        Detailed email information
        
    Raises:
        HTTPException: If email not found
    """
    try:
        email = await email_service.get_email_by_id(message_id)
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Email with ID {message_id} not found"
            )
            
        return email
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving email {message_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve email: {str(e)}"
        )


@router.post(
    "/analyze",
    response_model=EmailAnalysisResponse,
    summary="Analyze email content",
    dependencies=[Depends(require_process)]
)
async def analyze_email(
    request: EmailAnalysisRequest,
    email_service: EmailService = Depends(get_email_service)
):
    """
    Analyze email content with the AI pipeline.
    
    Processes email content through the complete analysis pipeline
    with comprehensive processing and validation.
    
    Args:
        request: Email analysis request with content
        
    Returns:
        Analysis results
    """
    try:
        result = await email_service.analyze_email(
            content=request.content,
            subject=request.subject,
            sender=request.sender
        )
        
        return result
    except Exception as e:
        logger.error(f"Error analyzing email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze email: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=EmailProcessingStats,
    summary="Get email processing statistics",
    dependencies=[Depends(require_view)]
)
async def get_processing_stats(
    email_service: EmailService = Depends(get_email_service)
):
    """
    Retrieve email processing statistics.
    
    Provides comprehensive statistics about email processing
    including volume, categories, and performance metrics.
    
    Returns:
        Email processing statistics
    """
    try:
        return await email_service.get_processing_stats()
    except Exception as e:
        logger.error(f"Error retrieving processing stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve processing statistics: {str(e)}"
        )


@router.get(
    "/settings",
    response_model=EmailSettings,
    summary="Get email processing settings",
    dependencies=[Depends(require_view)]
)
async def get_email_settings(
    email_service: EmailService = Depends(get_email_service)
):
    """
    Retrieve current email processing settings.
    
    Provides access to system configuration settings
    with proper authorization verification.
    
    Returns:
        Current email processing settings
    """
    try:
        return await email_service.get_settings()
    except Exception as e:
        logger.error(f"Error retrieving settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve settings: {str(e)}"
        )


@router.put(
    "/settings",
    response_model=EmailSettings,
    summary="Update email processing settings",
    dependencies=[Depends(require_admin)]
)
async def update_email_settings(
    settings: EmailSettings,
    email_service: EmailService = Depends(get_email_service)
):
    """
    Update email processing settings.
    
    Allows administrators to modify system configuration
    with comprehensive validation and security checks.
    
    Args:
        settings: New email processing settings
        
    Returns:
        Updated email processing settings
    """
    try:
        return await email_service.update_settings(settings)
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )


@router.post(
    "/process-batch",
    summary="Trigger batch email processing",
    dependencies=[Depends(require_process)]
)
async def process_email_batch(
    batch_size: int = Query(50, ge=1, le=100, description="Number of emails to process"),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Trigger batch processing of unread emails.
    
    Initiates the email processing pipeline on unread emails
    with proper authorization and parameter validation.
    
    Args:
        batch_size: Number of emails to process in this batch
        
    Returns:
        Processing results summary
    """
    try:
        processed, errors = await email_service.process_batch(batch_size)
        
        return {
            "processed": processed,
            "errors": len(errors),
            "success_rate": processed / (processed + len(errors)) if processed + len(errors) > 0 else 0,
            "timestamp": email_service.get_current_timestamp()
        }
    except Exception as e:
        logger.error(f"Error processing email batch: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process email batch: {str(e)}"
        )
