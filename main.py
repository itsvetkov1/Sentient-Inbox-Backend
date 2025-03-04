import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from api.routes import auth, emails, dashboard


sys.path.append(str(Path(__file__).parent / "src"))



from src.email_processing import (
    EmailProcessor, EmailTopic, EmailAgent, LlamaAnalyzer, 
    DeepseekAnalyzer, ResponseCategorizer 
)

from src.integrations.gmail.client import GmailClient
from src.storage.secure import SecureStorage

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

def setup_logging():
    """
    Configure comprehensive logging with detailed formatting and appropriate levels.
    
    Implements hierarchical logging configuration to capture:
    - Detailed API interaction logging
    - Model inputs/outputs
    - System state changes
    - Performance metrics
    """
    # Create logs directory if it doesn't exist
    Path('logs').mkdir(exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,  # Set to DEBUG to capture all levels
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/main.log'),
            logging.StreamHandler()
        ]
    )
    
    # Set specific logger levels
    logging.getLogger('src.email_processing.analyzers.llama').setLevel(logging.DEBUG)
    logging.getLogger('src.email_processing.analyzers.deepseek').setLevel(logging.DEBUG)
    logging.getLogger('src.email_processing.analyzers.response_categorizer').setLevel(logging.DEBUG)
    logging.getLogger('httpx').setLevel(logging.DEBUG)  # For API calls

setup_logging()

logger = logging.getLogger(__name__)

# Ensure logs directory exists
Path('logs').mkdir(exist_ok=True)

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
