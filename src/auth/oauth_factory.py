"""
OAuth Provider Factory

Provides a centralized factory for creating OAuth provider instances
with proper provider registration and comprehensive error handling.

Design Considerations:
- Dynamic provider registration
- Lazy provider instantiation
- Comprehensive error handling
- Clean separation of provider implementations
"""

import logging
from typing import Dict, Type, Optional

from src.auth.oauth_base import OAuthProvider
from src.auth.google_oauth import GoogleOAuthProvider
from src.auth.microsoft_oauth import MicrosoftOAuthProvider

logger = logging.getLogger(__name__)

class OAuthProviderFactory:
    """
    Factory for creating OAuth provider instances.
    
    Implements a registry-based factory pattern for OAuth provider
    instantiation with proper error handling and lazy loading.
    """
    
    # Provider registry mapping provider names to classes
    _registry: Dict[str, Type[OAuthProvider]] = {
        "google": GoogleOAuthProvider,
        "microsoft": MicrosoftOAuthProvider
    }
    
    # Provider cache for singleton instances
    _instances: Dict[str, OAuthProvider] = {}
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[OAuthProvider]) -> None:
        """
        Register a new provider class.
        
        Args:
            name: Provider name
            provider_class: Provider class
            
        Raises:
            ValueError: If provider name is already registered
        """
        if name in cls._registry:
            raise ValueError(f"Provider {name} is already registered")
            
        cls._registry[name] = provider_class
        logger.info(f"Registered OAuth provider: {name}")
    
    @classmethod
    def get_provider(cls, name: str) -> OAuthProvider:
        """
        Get provider instance by name.
        
        Args:
            name: Provider name
            
        Returns:
            Provider instance
            
        Raises:
            ValueError: If provider is not registered
        """
        if name not in cls._registry:
            logger.error(f"No provider registered with name: {name}")
            raise ValueError(f"No provider registered with name: {name}")
            
        # Create instance if not in cache
        if name not in cls._instances:
            try:
                cls._instances[name] = cls._registry[name]()
                logger.debug(f"Created new provider instance: {name}")
            except Exception as e:
                logger.error(f"Failed to create provider {name}: {str(e)}")
                raise ValueError(f"Failed to create provider {name}: {str(e)}")
                
        return cls._instances[name]
    
    @classmethod
    def get_available_providers(cls) -> Dict[str, str]:
        """
        Get list of available provider names.
        
        Returns:
            Dictionary mapping provider names to display names
        """
        display_names = {
            "google": "Google",
            "microsoft": "Microsoft / Outlook"
        }
        
        return {
            name: display_names.get(name, name.capitalize())
            for name in cls._registry.keys()
        }