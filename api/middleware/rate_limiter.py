"""
Rate Limiting Middleware Implementation

Provides comprehensive rate limiting functionality to protect
API resources from excessive usage and potential abuse.

Design Considerations:
- Efficient request counting with proper time window management
- Configurable rate limits with environment-specific defaults
- Clear response headers for client guidance
- Comprehensive error handling and logging
"""

import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable

from fastapi import FastAPI, Request, Response
# Updated import path for BaseHTTPMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from api.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

class RateLimiter(BaseHTTPMiddleware):
    """
    Rate limiting middleware with configurable limits and window size.
    
    Implements comprehensive request rate limiting with proper window
    management, client identification, and response headers for guidance.
    """
    
    def __init__(
        self, 
        app: FastAPI, 
        window_seconds: int = None,
        max_requests: int = None
    ):
        """
        Initialize rate limiter with configurable settings.
        
        Args:
            app: FastAPI application
            window_seconds: Rate limit window in seconds
            max_requests: Maximum requests per window
        """
        super().__init__(app)
        settings = get_settings()
        
        # Configure rate limiting parameters
        self.window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
        self.max_requests = max_requests or settings.RATE_LIMIT_MAX_REQUESTS
        
        # Data store for rate limiting
        # Note: In production, use Redis or similar distributed store
        self.client_requests: Dict[str, Dict] = {}
        
        logger.info(
            f"Rate limiter initialized: {self.max_requests} requests per {self.window_seconds} seconds"
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with rate limiting enforcement.
        
        Implements request rate limiting with proper client identification,
        request counting, and response generation based on limit status.
        
        Args:
            request: Incoming request
            call_next: Next middleware in chain
            
        Returns:
            API response with appropriate status and headers
        """
        # Skip rate limiting for excluded paths
        if self._should_skip_rate_limiting(request.url.path):
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_identifier(request)
        
        # Initialize client entry if not exists
        if client_id not in self.client_requests:
            self.client_requests[client_id] = {
                "requests": [],
                "blocked_until": None
            }
        
        client_data = self.client_requests[client_id]
        current_time = time.time()
        
        # Check if client is blocked
        if client_data["blocked_until"] and client_data["blocked_until"] > current_time:
            # Client is currently blocked
            wait_seconds = int(client_data["blocked_until"] - current_time)
            logger.warning(f"Rate limit exceeded for client {client_id}: blocked for {wait_seconds}s")
            
            return self._create_rate_limit_response(wait_seconds)
        
        # Clean old requests outside window
        window_start = current_time - self.window_seconds
        client_data["requests"] = [r for r in client_data["requests"] if r >= window_start]
        
        # Check if client exceeds rate limit
        if len(client_data["requests"]) >= self.max_requests:
            # Block client for window duration
            client_data["blocked_until"] = current_time + self.window_seconds
            logger.warning(
                f"Rate limit exceeded for client {client_id}: {self.max_requests} requests in {self.window_seconds}s"
            )
            
            return self._create_rate_limit_response(self.window_seconds)
        
        # Add current request to history and process normally
        client_data["requests"].append(current_time)
        
        # Add rate limit headers to response
        response = await call_next(request)
        remaining = self.max_requests - len(client_data["requests"])
        
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(window_start + self.window_seconds))
        
        return response
    
    def _should_skip_rate_limiting(self, path: str) -> bool:
        """
        Determine if rate limiting should be skipped for this path.
        
        Args:
            path: Request URL path
            
        Returns:
            Boolean indicating if rate limiting should be skipped
        """
        # Skip docs, health checks, and other specific endpoints
        skipped_paths = [
            "/docs", 
            "/redoc", 
            "/openapi.json",
            "/health",
            "/metrics"
        ]
        
        return any(path.startswith(skip_path) for skip_path in skipped_paths)
    
    def _get_client_identifier(self, request: Request) -> str:
        """
        Extract client identifier for rate limiting.
        
        Implements multi-factor client identification with fallbacks
        to properly identify clients for rate limiting purposes.
        
        Args:
            request: Incoming request
            
        Returns:
            Client identifier string
        """
        # Try to get client ID from header
        client_id = request.headers.get("X-Client-ID")
        
        # Fallback to IP address if no client ID provided
        if not client_id:
            client_id = request.client.host if request.client else "unknown"
            
        return client_id
    
    def _create_rate_limit_response(self, retry_after: int) -> Response:
        """
        Create rate limit exceeded response with proper headers.
        
        Args:
            retry_after: Seconds to wait before retrying
            
        Returns:
            Rate limit response with appropriate status and headers
        """
        from fastapi.responses import JSONResponse
        
        content = {
            "status": "error",
            "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = JSONResponse(
            content=content,
            status_code=HTTP_429_TOO_MANY_REQUESTS
        )
        
        response.headers["Retry-After"] = str(retry_after)
        return response