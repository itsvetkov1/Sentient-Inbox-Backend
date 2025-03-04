"""
API Server Runner

Provides a convenient entry point for running the FastAPI server
with proper configuration and environment setup.
"""

import argparse
import logging
import os
import sys
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api_runner")

def parse_arguments():
    """Parse command line arguments for the API server."""
    parser = argparse.ArgumentParser(description="Run the Email Management API server")
    
    parser.add_argument(
        "--host", 
        type=str, 
        default="127.0.0.1", 
        help="Host to bind the server to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to bind the server to (default: 8000)"
    )
    
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="Enable auto-reload for development"
    )
    
    parser.add_argument(
        "--env", 
        type=str, 
        choices=["development", "testing", "production"],
        default="development",
        help="Environment to run in (default: development)"
    )
    
    return parser.parse_args()

def setup_environment(env):
    """Set up environment variables for the API server."""
    os.environ["ENVIRONMENT"] = env
    
    # Set debug mode for development and testing
    if env in ["development", "testing"]:
        os.environ["DEBUG"] = "true"
    else:
        os.environ["DEBUG"] = "false"
    
    # Ensure required directories exist
    required_dirs = [
        "data/config",
        "data/metrics",
        "data/secure",
        "logs"
    ]
    
    for directory in required_dirs:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")

def main():
    """Run the API server with the specified configuration."""
    args = parse_arguments()
    
    # Setup environment
    setup_environment(args.env)
    
    logger.info(f"Starting API server in {args.env} mode")
    logger.info(f"Server will be available at http://{args.host}:{args.port}")
    
    if args.env == "development":
        logger.info(f"API documentation will be available at http://{args.host}:{args.port}/docs")
    
    # Run the server
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info" if args.env == "production" else "debug"
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")
        sys.exit(1)
