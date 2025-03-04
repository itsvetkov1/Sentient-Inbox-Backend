"""
Dashboard Data Models

Defines models for dashboard data including statistics, metrics, and
visualization data structures.

Design Considerations:
- Comprehensive type definitions
- Detailed documentation
- Proper validation rules
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class EmailVolumeMetric(BaseModel):
    """Email volume data for dashboard charts."""
    
    date: str = Field(..., description="Date label for the data point")
    total: int = Field(..., description="Total emails processed")
    meeting: int = Field(..., description="Meeting related emails")
    other: int = Field(..., description="Other emails")


class CategoryDistribution(BaseModel):
    """Category distribution data for pie charts."""
    
    category: str = Field(..., description="Email category name")
    count: int = Field(..., description="Number of emails in this category")
    percentage: float = Field(..., description="Percentage of total emails")


class PerformanceMetric(BaseModel):
    """Performance metric data for dashboards."""
    
    metric_name: str = Field(..., description="Name of the performance metric")
    current_value: float = Field(..., description="Current value of the metric")
    previous_value: Optional[float] = Field(None, description="Previous value for comparison")
    change_percentage: Optional[float] = Field(None, description="Percentage change from previous period")
    trend: Optional[str] = Field(None, description="Trend direction (up, down, stable)")


class AgentMetric(BaseModel):
    """Metrics for individual AI agents."""
    
    agent_id: str = Field(..., description="Unique identifier for the agent")
    agent_name: str = Field(..., description="Display name of the agent")
    emails_processed: int = Field(..., description="Number of emails processed by this agent")
    success_rate: float = Field(..., description="Success rate percentage")
    avg_processing_time: float = Field(..., description="Average processing time in milliseconds")
    is_active: bool = Field(..., description="Whether the agent is currently active")


class DashboardStats(BaseModel):
    """Comprehensive dashboard statistics."""
    
    total_emails: int = Field(..., description="Total number of emails processed")
    meeting_emails: int = Field(..., description="Number of meeting-related emails")
    response_rate: float = Field(..., description="Percentage of emails with responses")
    avg_processing_time: float = Field(..., description="Average email processing time in milliseconds")
    success_rate: float = Field(..., description="Success rate for email processing")
    volume_trend: List[EmailVolumeMetric] = Field(..., description="Email volume trend data")
    category_distribution: List[CategoryDistribution] = Field(..., description="Email category distribution")
    performance_metrics: List[PerformanceMetric] = Field(..., description="Key performance metrics")
    agent_metrics: List[AgentMetric] = Field(..., description="Metrics for individual AI agents")
    last_updated: datetime = Field(..., description="Timestamp of when stats were last updated")


class UserActivitySummary(BaseModel):
    """Summary of user activity for the dashboard."""
    
    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")
    emails_per_user: Dict[str, int] = Field(..., description="Emails processed per user")
    last_activity: Dict[str, datetime] = Field(..., description="Last activity timestamp per user")


class EmailAccountStats(BaseModel):
    """Statistics for a single email account."""
    
    email: str = Field(..., description="Email address")
    total_processed: int = Field(..., description="Total emails processed for this account")
    categories: Dict[str, int] = Field(..., description="Email count by category")
    is_active: bool = Field(..., description="Whether this account is currently active")
    last_sync: Optional[datetime] = Field(None, description="Last synchronization timestamp")


class DashboardSummary(BaseModel):
    """Summary dashboard data combining multiple metrics."""
    
    stats: DashboardStats = Field(..., description="Overall dashboard statistics")
    user_activity: UserActivitySummary = Field(..., description="User activity summary")
    email_accounts: List[EmailAccountStats] = Field(..., description="Email account statistics")
    period: str = Field(..., description="Time period for the dashboard data (day, week, month, etc.)")