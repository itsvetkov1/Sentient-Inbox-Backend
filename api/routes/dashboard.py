"""
Dashboard API Routes

Implements comprehensive dashboard endpoints with proper 
authentication, validation, and optimal data retrieval.

Design Considerations:
- Performance optimization for dashboard data retrieval
- Proper caching strategies
- Consistent route organization
- Clear endpoint documentation
- Proper error handling
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status

from api.auth.service import require_admin, require_view
from api.models.dashboard import (
    DashboardStats,
    UserActivitySummary,
    EmailAccountStats,
    DashboardSummary
)
from api.services.dashboard_service import DashboardService, get_dashboard_service

# Configure logging
logger = logging.getLogger(__name__)

# Create router with prefix
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/stats",
    response_model=DashboardStats,
    summary="Get dashboard statistics",
    dependencies=[Depends(require_view)]
)
async def get_dashboard_stats(
    period: str = Query("day", description="Time period for metrics (day, week, month)"),
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """
    Retrieve comprehensive dashboard statistics.
    
    Provides key metrics and visualization data for the dashboard
    with proper caching and optimization.
    
    Args:
        period: Time period for metrics (day, week, month)
        
    Returns:
        Comprehensive dashboard statistics
    """
    try:
        stats = await dashboard_service.get_dashboard_stats(period)
        return stats
    except Exception as e:
        logger.error(f"Error retrieving dashboard stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve dashboard statistics: {str(e)}"
        )


@router.get(
    "/user-activity",
    response_model=UserActivitySummary,
    summary="Get user activity summary",
    dependencies=[Depends(require_view)]
)
async def get_user_activity(
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """
    Retrieve user activity summary for the dashboard.
    
    Provides aggregated user activity data with proper
    caching and optimization.
    
    Returns:
        User activity summary data
    """
    try:
        activity = await dashboard_service.get_user_activity()
        return activity
    except Exception as e:
        logger.error(f"Error retrieving user activity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user activity: {str(e)}"
        )


@router.get(
    "/email-accounts",
    response_model=List[EmailAccountStats],
    summary="Get email account statistics",
    dependencies=[Depends(require_view)]
)
async def get_email_account_stats(
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """
    Retrieve email account statistics.
    
    Provides statistics for each connected email account
    with proper caching and optimization.
    
    Returns:
        List of email account statistics
    """
    try:
        account_stats = await dashboard_service.get_email_account_stats()
        return account_stats
    except Exception as e:
        logger.error(f"Error retrieving email account stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve email account statistics: {str(e)}"
        )


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Get comprehensive dashboard summary",
    dependencies=[Depends(require_view)]
)
async def get_dashboard_summary(
    period: str = Query("day", description="Time period for metrics (day, week, month)"),
    dashboard_service: DashboardService = Depends(get_dashboard_service)
):
    """
    Retrieve comprehensive dashboard summary.
    
    Provides a complete dashboard data package combining multiple
    data sources with proper caching and optimization.
    
    Args:
        period: Time period for metrics (day, week, month)
        
    Returns:
        Comprehensive dashboard summary
    """
    try:
        summary = await dashboard_service.get_dashboard_summary(period)
        return summary
    except Exception as e:
        logger.error(f"Error retrieving dashboard summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve dashboard summary: {str(e)}"
        )