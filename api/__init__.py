"""
API Package Initialization

Provides FastAPI application with comprehensive route management,
authentication, and service integration.

Design Considerations:
- Clean package organization
- Proper dependency management
- Secure authentication
- Comprehensive error handling
"""

from api.routes import auth, emails, dashboard
from api.services import email_service
from api.models import emails as email_models
from api.config import get_settings

__all__ = [
    'auth',
    'emails',
    'dashboard',
    'email_service',
    'email_models',
    'get_settings'
]
