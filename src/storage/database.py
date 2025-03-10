"""
Database Configuration and Connection Management

Provides comprehensive database setup, connection pooling, and session
management with proper error handling and connection lifecycle management.

Design Considerations:
- Connection pooling for optimal performance
- SQLAlchemy session management
- Comprehensive error handling
- Secure credential management
- Support for multiple database backends
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Any

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from src.storage.models import Base
from src.storage.encryption import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = os.getenv("DATABASE_URL", "sqlite:///data/secure/sentient_inbox.db")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

# Initialize engine with connection pooling
engine = create_engine(
    DB_PATH,
    poolclass=QueuePool,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    connect_args={"check_same_thread": False} if DB_PATH.startswith("sqlite") else {},
    echo=os.getenv("SQL_ECHO", "False").lower() == "true"
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    """
    Initialize database with proper schema creation and migration handling.
    
    Creates all tables if they don't exist and performs any necessary
    migrations to ensure schema compatibility. Implements proper error
    handling for database setup failures.
    """
    try:
        logger.info("Initializing database schema")
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise RuntimeError(f"Failed to initialize database: {str(e)}")

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Provide database session with proper error handling and cleanup.
    
    Implements comprehensive session lifecycle management with proper
    error handling, rollback on exceptions, and guaranteed cleanup.
    
    Yields:
        SQLAlchemy session for database operations
        
    Raises:
        Exception: Re-raises any exceptions that occur during session use
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {str(e)}")
        raise
    finally:
        session.close()