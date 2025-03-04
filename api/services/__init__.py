# api/services/__init__.py
"""
API Services Package

Centralizes service implementations for clean business logic
separation from route handlers.

Design Considerations:
- Clean separation from route handling
- Reusable business logic
- Proper dependency injection
"""

from api.services.email_service import EmailService, get_email_service
from api.services.dashboard_service import DashboardService, get_dashboard_service

__all__ = ["EmailService", "get_email_service", "DashboardService", "get_dashboard_service"]