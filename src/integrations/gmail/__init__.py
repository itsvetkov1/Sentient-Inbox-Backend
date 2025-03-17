"""
Gmail integration package.

Provides centralized access to Gmail API functionality through a comprehensive
client implementation with robust authentication handling.
"""

from .client import GmailClient

__all__ = ["GmailClient"]
