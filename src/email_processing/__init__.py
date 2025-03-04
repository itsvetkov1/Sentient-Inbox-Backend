"""
Email processing package initialization.
"""

from .models import EmailMetadata, EmailTopic
from .classification.classifier import EmailClassifier, EmailRouter
from .handlers.writer import EmailAgent
from .analyzers.llama import LlamaAnalyzer
from .analyzers.deepseek import DeepseekAnalyzer
from .analyzers.response_categorizer import ResponseCategorizer
from .processor import EmailProcessor

__all__ = [
    'EmailMetadata',
    'EmailTopic',
    'EmailClassifier',
    'EmailRouter',
    'EmailAgent',
    'LlamaAnalyzer',
    'DeepseekAnalyzer',
    'ResponseCategorizer',
    'EmailProcessor'
]
