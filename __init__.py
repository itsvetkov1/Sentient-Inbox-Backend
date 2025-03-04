# src/__init__.py
"""
Sentient Inbox system root package.

Provides centralized access to core system components while maintaining
proper dependency management and component isolation.
"""

from email_processing import EmailProcessor
from email_processing.classification import EmailClassifier, EmailTopic
from integrations.gmail import GmailClient
from integrations.groq import GroqClient
from storage import SecureStorage

__version__ = '1.0.0'

__all__ = [
    'EmailProcessor',
    'EmailClassifier',
    'EmailTopic',
    'GmailClient',
    'GroqClient',
    'SecureStorage'
]