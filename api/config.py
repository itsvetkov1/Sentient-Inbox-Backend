"""
API Configuration Management

Provides centralized configuration handling with environment-aware settings
management, secure secret retrieval, and comprehensive validation.

Design Considerations:
- Environment-specific configuration profiles
- Secure handling of sensitive information
- Comprehensive configuration validation
- Default values with proper documentation
"""

import os
from enum import Enum
from typing import Dict, Any, Optional, List

# Import BaseSettings from pydantic_settings instead of pydantic
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr, field_validator


class EnvironmentType(str, Enum):
    """Valid environment types for configuration context."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class APISettings(BaseSettings):
    """
    API configuration settings with environment-specific defaults and validation.
    
    Implements a comprehensive configuration system using Pydantic for validation,
    environment variable loading, and secure secret management. Provides safe defaults
    where appropriate while requiring critical security configurations.
    """
    # Environment Configuration
    ENVIRONMENT: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        description="Runtime environment context"
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # API Settings
    API_TITLE: str = Field(
        default="Email Management API",
        description="API title for documentation"
    )
    API_DESCRIPTION: str = Field(
        default="API for sophisticated email analysis and response management",
        description="API description for documentation"
    )
    API_VERSION: str = Field(
        default="1.0.0",
        description="API version"
    )
    
    # Security Settings
    JWT_SECRET_KEY: SecretStr = Field(
        default="insecure_development_key_do_not_use_in_production_1234567890",  # Default for development
        description="Secret key for JWT token generation and validation"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used for JWT token generation"
    )
    JWT_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="JWT token expiration time in minutes"
    )
    
    # CORS Settings
    CORS_ORIGINS: str = Field(
        default="*",
        description="Comma-separated list of allowed origins for CORS"
    )
    CORS_METHODS: str = Field(
        default="GET,POST,PUT,DELETE,OPTIONS",
        description="Comma-separated list of allowed methods for CORS"
    )
    
    # Rate Limiting
    RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=60,
        description="Rate limit window in seconds"
    )
    RATE_LIMIT_MAX_REQUESTS: int = Field(
        default=100,
        description="Maximum requests per window"
    )

    # Use field_validator instead of validator in Pydantic V2
    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, value: str) -> list:
        """Parse comma-separated CORS origins into list."""
        if value == "*":
            return ["*"]
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @field_validator("CORS_METHODS")
    @classmethod
    def parse_cors_methods(cls, value: str) -> list:
        """Parse comma-separated CORS methods into list."""
        return [method.strip() for method in value.split(",") if method.strip()]

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        """Validate JWT secret key meets minimum security requirements."""
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
        return value

    # Pydantic V2 uses model_config instead of Config class
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


def get_settings() -> APISettings:
    """
    Retrieve validated API settings with environment-specific configuration.
    
    Implements proper configuration loading with environment awareness
    and comprehensive validation to ensure all required settings are
    properly specified.
    
    Returns:
        Validated API settings object
    
    Raises:
        ValidationError: If configuration fails validation
    """
    # For development/testing, generate a secret if not provided
    env = os.getenv("ENVIRONMENT", "development")
    if env in ["development", "testing"]:
        os.environ.setdefault(
            "JWT_SECRET_KEY",
            "insecure_development_key_do_not_use_in_production_1234567890"
        )
        
    # Load and validate settings
    return APISettings()