"""
Unit tests for database configuration and connection management.

These tests validate database initialization, session handling,
connection pooling, and proper error management.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, call

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.storage.database import (
    init_db,
    get_db_session,
    engine,
    SessionLocal,
    DB_PATH
)


class TestDatabaseModule:
    """Test suite for database configuration and connection management."""
    
    def test_database_config_defaults(self):
        """Test database configuration with default values."""
        # The database module imports these from environment variables
        # Validate they have proper defaults
        assert DB_PATH == "sqlite:///data/secure/sentient_inbox.db"
        assert "QueuePool" in str(engine.pool.__class__)
    
    @patch('src.storage.database.Base')
    def test_init_db_success(self, mock_base):
        """Test successful database initialization."""
        # Setup mock
        mock_metadata = MagicMock()
        mock_base.metadata = mock_metadata
        
        # Call function
        init_db()
        
        # Verify metadata.create_all was called with engine
        mock_metadata.create_all.assert_called_once_with(bind=engine)
    
    @patch('src.storage.database.Base')
    def test_init_db_error_handling(self, mock_base):
        """Test error handling during database initialization."""
        # Setup mock to raise exception
        mock_metadata = MagicMock()
        mock_metadata.create_all.side_effect = Exception("DB error")
        mock_base.metadata = mock_metadata
        
        # Verify exception is re-raised with additional context
        with pytest.raises(RuntimeError) as excinfo:
            init_db()
        
        assert "Failed to initialize database: DB error" in str(excinfo.value)
    
    @patch('src.storage.database.SessionLocal')
    def test_get_db_session_normal_flow(self, mock_session_local):
        """Test normal flow of database session context manager."""
        # Setup session mock
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session
        
        # Use context manager
        with get_db_session() as session:
            assert session is mock_session
        
        # Verify proper session lifecycle
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
    
    @patch('src.storage.database.SessionLocal')
    def test_get_db_session_with_exception(self, mock_session_local):
        """Test session handling when an exception occurs."""
        # Setup session mock
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session
        
        # Use context manager with exception
        with pytest.raises(ValueError):
            with get_db_session() as session:
                raise ValueError("Test exception")
        
        # Verify rollback and close were called
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
    
    @patch('src.storage.database.create_engine')
    @patch('src.storage.database.sessionmaker')
    def test_engine_initialization(self, mock_sessionmaker, mock_create_engine):
        """Test engine initialization with proper parameters."""
        # This requires reimporting the module to trigger initialization
        # We'll use a context manager to temporarily modify the module's environment
        
        with patch.dict('sys.modules', {'src.storage.database': None}):
            with patch.dict('os.environ', {
                'DATABASE_URL': 'postgresql://user:pass@localhost/testdb',
                'DB_POOL_SIZE': '10',
                'DB_MAX_OVERFLOW': '20',
                'DB_POOL_TIMEOUT': '60',
                'SQL_ECHO': 'true'
            }):
                # Re-import to trigger initialization with our mocked environment
                import importlib
                importlib.invalidate_caches()
                import src.storage.database
                
                # Check create_engine was called with correct parameters
                mock_create_engine.assert_called_once()
                args, kwargs = mock_create_engine.call_args
                
                assert args[0] == 'postgresql://user:pass@localhost/testdb'
                assert kwargs['pool_size'] == 10
                assert kwargs['max_overflow'] == 20
                assert kwargs['pool_timeout'] == 60
                assert kwargs['echo'] is True
                
                # Check sessionmaker was called with create_engine result
                mock_sessionmaker.assert_called_once()
    
    @patch('src.storage.database.create_engine')
    def test_sqlite_connection_args(self, mock_create_engine):
        """Test SQLite-specific connection arguments."""
        # SQLite connections need check_same_thread=False
        
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        with patch.dict('sys.modules', {'src.storage.database': None}):
            with patch.dict('os.environ', {
                'DATABASE_URL': 'sqlite:///test.db'
            }):
                # Re-import to trigger initialization
                import importlib
                importlib.invalidate_caches()
                import src.storage.database
                
                # Verify check_same_thread was set for SQLite
                args, kwargs = mock_create_engine.call_args
                assert 'connect_args' in kwargs
                assert kwargs['connect_args'] == {'check_same_thread': False}


if __name__ == "__main__":
    pytest.main()
