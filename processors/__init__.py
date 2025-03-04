"""
Processors module initialization.

This module provides core processing components for the email analysis system,
implementing content preprocessing, analysis pipeline integration, and
extensible processing capabilities.

Architecture:
- Modular processor implementations
- Extensible base classes
- Standardized interfaces
- Comprehensive configuration
"""

from . import ContentPreprocessor
from src.email_processing.base import BaseProcessor
__all__ = [
    'ContentPreprocessor',
    'BaseProcessor'
]