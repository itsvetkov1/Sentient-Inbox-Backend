import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Get project root directory
PROJECT_ROOT = Path(__file__).parent
LOGS_DIR = PROJECT_ROOT / 'logs'
DATA_DIR = PROJECT_ROOT / 'data'

# Create all required directories first
def setup_directories():
    """Create required directories for the application"""
    directories = [
        LOGS_DIR,
        DATA_DIR / 'secure',
        DATA_DIR / 'metrics',
        DATA_DIR / 'cache'
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

# Set up directories before any logging
setup_directories()

def setup_logging():
    """Configure comprehensive logging"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOGS_DIR / 'main.log'),
            logging.StreamHandler()
        ]
    )
    
    # Set specific logger levels
    logging.getLogger('src.email_processing.analyzers.llama').setLevel(logging.DEBUG)
    logging.getLogger('src.email_processing.analyzers.deepseek').setLevel(logging.DEBUG)
    logging.getLogger('src.email_processing.analyzers.response_categorizer').setLevel(logging.DEBUG)
    logging.getLogger('httpx').setLevel(logging.DEBUG)

# Initialize logging before any other imports
setup_logging()

# Now import other modules
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from api.routes import auth, emails, dashboard

sys.path.append(str(Path(__file__).parent / "src"))

from src.email_processing import (
    EmailProcessor, EmailTopic, EmailAgent, LlamaAnalyzer, 
    DeepseekAnalyzer, ResponseCategorizer 
)

from src.integrations.gmail.client import GmailClient
from src.storage.secure import SecureStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("credentials")

# Define and call the credentials function early
def load_google_credentials():
    try:
        # Print current working directory to help with path issues
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Specify the exact path to your credentials file
        credentials_path = "client_secret.json"
        logger.info(f"Attempting to load credentials from: {credentials_path}")
        
        # Check if file exists
        if not os.path.exists(credentials_path):
            logger.error(f"ERROR: Credentials file not found at {credentials_path}")
            return
            
        with open(credentials_path, 'r') as file:
            credentials = json.load(file)
            logger.info("Successfully loaded JSON file")
            
        # Log the structure to verify it contains what we expect
        logger.info(f"JSON structure keys: {list(credentials.keys())}")
            
        # Extract and set environment variables
        if 'web' in credentials:
            logger.info("Found 'web' configuration in credentials")
            os.environ["GOOGLE_CLIENT_ID"] = credentials['web']['client_id']
            os.environ["GOOGLE_CLIENT_SECRET"] = credentials['web']['client_secret']
            logger.info(f"Set GOOGLE_CLIENT_ID: {os.environ.get('GOOGLE_CLIENT_ID')[:5]}...")
            logger.info(f"Set GOOGLE_CLIENT_SECRET: {os.environ.get('GOOGLE_CLIENT_SECRET')[:5]}...")
            return True
        elif 'installed' in credentials:
            logger.info("Found 'installed' configuration in credentials")
            os.environ["GOOGLE_CLIENT_ID"] = credentials['installed']['client_id']
            os.environ["GOOGLE_CLIENT_SECRET"] = credentials['installed']['client_secret']
            logger.info(f"Set GOOGLE_CLIENT_ID: {os.environ.get('GOOGLE_CLIENT_ID')[:5]}...")
            logger.info(f"Set GOOGLE_CLIENT_SECRET: {os.environ.get('GOOGLE_CLIENT_SECRET')[:5]}...")
            return True
        else:
            logger.error(f"WARNING: Unrecognized credentials format. Available keys: {list(credentials.keys())}")
            return False
            
    except Exception as e:
        logger.error(f"Error loading Google credentials: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# Call function immediately after definition
logger.info("==== STARTING GOOGLE CREDENTIALS LOADING ====")
success = load_google_credentials()
logger.info("==== COMPLETED GOOGLE CREDENTIALS LOADING ====")
logger.info(f"GOOGLE_CLIENT_ID environment variable set: {'GOOGLE_CLIENT_ID' in os.environ}")
logger.info(f"GOOGLE_CLIENT_SECRET environment variable set: {'GOOGLE_CLIENT_SECRET' in os.environ}")

if not success:
    logger.error("Failed to load Google OAuth credentials. OAuth features will not work.")

# Initialize FastAPI app
app = FastAPI(
    title="Sentient Inbox API",
    description="API for intelligent email processing and management",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(emails.router)
app.include_router(dashboard.router)

# API Models
class ProcessEmailRequest(BaseModel):
    batch_size: int = 100

class ProcessEmailResponse(BaseModel):
    processed_count: int
    error_count: int
    success: bool
    errors: list[str] = []

class MaintenanceResponse(BaseModel):
    key_rotated: bool
    records_cleaned: bool
    success: bool

logger = logging.getLogger(__name__)

def log_execution(message: str):
    """Log execution with timestamp"""
    timestamp = datetime.now().isoformat()
    logger.debug(f"[{timestamp}] {message}")

# Load environment variables
load_dotenv(override=True)

async def process_email_batch(batch_size: int = 100) -> bool:
    log_execution(f"Starting email processing cycle for batch of {batch_size} emails")

    try:
        gmail_client = GmailClient()
        meeting_agent = EmailAgent()
        llama_analyzer = LlamaAnalyzer()
        deepseek_analyzer = DeepseekAnalyzer()
        response_categorizer = ResponseCategorizer()
        secure_storage = SecureStorage()
        processor = EmailProcessor(
        gmail_client=gmail_client,
        llama_analyzer=llama_analyzer,
        deepseek_analyzer=deepseek_analyzer,
        response_categorizer=response_categorizer
    )
        processor.register_agent(EmailTopic.MEETING, meeting_agent)
        
        log_execution("Processing email batch...")
        processed_count, error_count, errors = await processor.process_email_batch(batch_size)
        
        log_execution(f"Email processing cycle completed. "
                     f"Processed: {processed_count}, "
                     f"Errors: {error_count}")
        
        logger.info(f"\nProcessed {processed_count} emails")
        logger.info(f"Encountered {error_count} errors")
        logger.info("Check the log file for detailed model responses and processing information.")
        
        if errors:
            logger.warning("Errors encountered during processing:")
            for error in errors:
                logger.warning(f"- {error}")

        return error_count == 0

    except Exception as e:
        logger.error(f"Error during email processing: {str(e)}", exc_info=True)
        return False
    


async def main():
    retry_delay = 3  # seconds
    max_retries = 1  # single retry attempt

    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.info(f"Retry attempt {attempt} after {retry_delay} seconds delay")
            await asyncio.sleep(retry_delay)

        success = await process_email_batch()
        if success:
            break
    
    if not success:
        logger.error("Email processing failed after all retry attempts")

    # Perform maintenance tasks
    await perform_maintenance()

async def perform_maintenance():
    """Perform maintenance tasks such as cleanup and key rotation"""
    try:
        secure_storage = SecureStorage()
        key_rotated = await secure_storage.rotate_key()
        records_cleaned = await secure_storage._cleanup_old_records()
        logger.info(f"Maintenance tasks completed. Key rotated: {key_rotated}, Records cleaned: {records_cleaned}")
    except Exception as e:
        logger.error(f"Error during maintenance tasks: {str(e)}", exc_info=True)

# Initialize components
gmail_client = GmailClient()
llama_analyzer = LlamaAnalyzer()
deepseek_analyzer = DeepseekAnalyzer()
response_categorizer = ResponseCategorizer()
secure_storage = SecureStorage()
meeting_agent = EmailAgent()
processor = EmailProcessor(
    gmail_client=gmail_client,
    llama_analyzer=llama_analyzer,
    deepseek_analyzer=deepseek_analyzer,
    response_categorizer=response_categorizer
)
processor.register_agent(EmailTopic.MEETING, meeting_agent)

# API Routes
@app.on_event("startup")
async def startup_event():
    """Perform initialization tasks on application startup."""
    logger.info("API service starting up")
    
    # Log all registered routes
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            routes.append(f"{route.path}")
    logger.info(f"Registered routes: {routes}")

@app.post("/api/process-emails", response_model=ProcessEmailResponse)
async def process_emails(request: ProcessEmailRequest) -> Dict[str, Any]:
    """Process a batch of emails"""
    try:
        processed_count, error_count, errors = await processor.process_email_batch(request.batch_size)
        return {
            "processed_count": processed_count,
            "error_count": error_count,
            "success": error_count == 0,
            "errors": errors
        }
    except Exception as e:
        logger.error(f"API Error processing emails: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/maintenance", response_model=MaintenanceResponse)
async def run_maintenance() -> Dict[str, Any]:
    """Run maintenance tasks"""
    try:
        key_rotated = await secure_storage.rotate_key()
        records_cleaned = await secure_storage._cleanup_old_records()
        return {
            "key_rotated": key_rotated,
            "records_cleaned": records_cleaned,
            "success": True
        }
    except Exception as e:
        logger.error(f"API Error during maintenance: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """Check API health"""
    return {"status": "healthy"}

# Script entry point
if __name__ == "__main__":
    log_execution("Starting email processing...")
    asyncio.run(main())
    log_execution("Processing complete")
