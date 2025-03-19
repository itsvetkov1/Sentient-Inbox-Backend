"""
API Package Initialization

Provides FastAPI application with comprehensive route management,
authentication, and service integration. This initialization file
ensures proper module resolution throughout the API package hierarchy.

Design Considerations:
- Clean package organization
- Proper dependency management
- Secure authentication
- Comprehensive error handling
"""

try:
    # Import key modules to expose at the package level
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
except ImportError as e:
    # Provide detailed error information for debugging
    import sys
    import os
    print(f"Import error in api/__init__.py: {e}")
    print(f"Current sys.path: {sys.path}")
    print(f"Current directory: {os.getcwd()}")