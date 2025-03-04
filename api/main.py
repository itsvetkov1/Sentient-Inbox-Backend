"""
API Application Entry Point

Defines the main FastAPI application with comprehensive middleware,
route configuration, and lifecycle management.

Design Considerations:
- Proper middleware ordering for optimal processing
- Comprehensive error handling
- Structured route organization
- Clean dependency management
"""

import logging
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings, EnvironmentType
from api.middleware.rate_limiter import RateLimiter
from api.utils.error_handlers import add_exception_handlers
from api.routes import auth, emails, dashboard

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api")

# Create application
def create_application() -> FastAPI:
    """
    Create and configure FastAPI application instance.
    
    Implements comprehensive application setup with proper middleware
    configuration, route registration, and error handling.
    
    Returns:
        Configured FastAPI application
    """
    settings = get_settings()
    
    # Create application with configuration
    app = FastAPI(
        title=settings.API_TITLE,
        description=settings.API_DESCRIPTION,
        version=settings.API_VERSION,
        docs_url="/docs" if settings.ENVIRONMENT != EnvironmentType.PRODUCTION else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != EnvironmentType.PRODUCTION else None,
        debug=settings.DEBUG
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=settings.CORS_METHODS,
        allow_headers=["*"],
    )
    
    # Add rate limiting middleware
    app.add_middleware(RateLimiter)
    
    # Add exception handlers
    add_exception_handlers(app)
    
    # Include routers
    app.include_router(auth.router)
    app.include_router(emails.router)
    app.include_router(dashboard.router)
    
    # Add startup and shutdown events
    @app.on_event("startup")
    async def startup_event():
        """Perform initialization tasks on application startup."""
        logger.info("API service starting up")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Perform cleanup tasks on application shutdown."""
        logger.info("API service shutting down")
    
    logger.info(f"Application initialized in {settings.ENVIRONMENT} environment")
    return app


# Create application instance
app = create_application()


# Simple health check endpoint
@app.get("/health", tags=["Monitoring"])
async def health_check():
    """API health check endpoint."""
    return {"status": "healthy"}
