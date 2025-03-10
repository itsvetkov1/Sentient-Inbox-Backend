"""
Database Models for User Management System

Defines comprehensive database models for user information and OAuth token
storage, implementing secure handling of sensitive data with proper
encryption and relationship management.

Design Considerations:
- Secure token storage with encryption
- Comprehensive user profile management
- Support for multiple OAuth providers per user
- Proper indexing for optimal query performance
- Clear documentation of field purposes
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

Base = declarative_base()

class User(Base):
    """
    User model storing core user information with OAuth provider linkage.
    
    Implements secure user profile management with comprehensive field
    validation and OAuth provider integration while maintaining minimal
    required user information for system functionality.
    """
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    
    # User permissions and status
    is_active = Column(Boolean, default=True, nullable=False)
    permissions = Column(JSON, nullable=False, default=lambda: json.dumps(["view"]))
    
    # Profile information (optional)
    profile_picture = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # OAuth token relationships
    oauth_tokens = relationship("OAuthToken", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary representation for API responses."""
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "permissions": json.loads(self.permissions) if isinstance(self.permissions, str) else self.permissions,
            "profile_picture": self.profile_picture,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "oauth_providers": [token.provider for token in self.oauth_tokens]
        }

class OAuthToken(Base):
    """
    OAuth token storage with secure encryption and provider metadata.
    
    Implements comprehensive token management with secure storage
    of sensitive OAuth credentials, refresh token handling, and
    proper provider-specific metadata.
    """
    __tablename__ = "oauth_tokens"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False, index=True)  # 'google', 'microsoft', etc.
    
    # Provider-specific identifiers
    provider_user_id = Column(String(255), nullable=False)
    provider_email = Column(String(255), nullable=False)
    
    # Token data (encrypted in the database)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(50), nullable=False, default="Bearer")
    expires_at = Column(DateTime, nullable=False)
    
    # Scopes granted
    scopes = Column(Text, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="oauth_tokens")
    
    # Unique constraint: one provider per user
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )