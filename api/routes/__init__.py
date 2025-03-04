"""
API Routes Package

Centralizes route management with proper module organization
and clean import structure.

Design Considerations:
- Clear route organization
- Explicit imports for better readability
- Centralized route registration
"""

from api.routes import auth
from api.routes import emails
from api.routes import dashboard

__all__ = ["auth", "emails", "dashboard"]
