from groq import Groq
from typing import Dict, List, Optional, Union
from datetime import datetime
import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/groq_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EnhancedGroqClient:
    """Enhanced Groq client with retry logic and error handling."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the enhanced Groq client with API key from environment or parameter."""
        load_dotenv(override=True)
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY must be provided either through initialization or environment")

        self.client = Groq(api_key=self.api_key)

        # Create metrics directory if it doesn't exist
        Path('data/metrics').mkdir(parents=True, exist_ok=True)
        self.metrics_file = 'data/metrics/groq_metrics.json'
        self.load_metrics()

    def load_metrics(self):
        """Load or initialize performance metrics."""
        try:
            with open(self.metrics_file, 'r') as f:
                self.metrics = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.metrics = {
                'requests': [],
                'errors': [],
                'performance': {
                    'avg_response_time': 0,
                    'total_requests': 0,
                    'success_rate': 100
                }
            }
            self.save_metrics()

    def save_metrics(self):
        """Save current metrics to file."""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)

    async def process_with_retry(self,
                                 messages: List[Dict],
                                 max_retries: int = 3,
                                 **kwargs) -> Dict:
        """Process a request with retry logic and error handling.

        Args:
            messages: List of message dictionaries for the conversation
            max_retries: Maximum number of retry attempts
            **kwargs: Additional parameters for the API call

        Returns:
            API response dictionary
        """
        start_time = datetime.now()
        retries = 0
        last_error = None

        while retries < max_retries:
            try:
                # Configure default parameters
                params = {
                    'model': kwargs.get('model', 'llama-3.3-70b-versatile'),
                    'messages': messages,
                    'temperature': kwargs.get('temperature', 0.7),
                    'max_completion_tokens': kwargs.get('max_completion_tokens', 4096),
                    'service_tier': kwargs.get('service_tier', None),
                    **kwargs
                }

                # Make the API call
                response = await asyncio.to_thread(self.client.chat.completions.create, **params)

                # Record success metrics
                self.record_success(start_time)
                return response

            except Exception as e:
                retries += 1
                last_error = str(e)
                self.record_error(last_error)

                if retries == max_retries:
                    logger.error(f"Failed after {max_retries} retries: {last_error}")
                    raise Exception(f"Failed after {max_retries} retries: {last_error}")

                # Exponential backoff
                wait_time = 2 ** retries
                logger.warning(f"Attempt {retries} failed. Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)

    def record_success(self, start_time: datetime):
        """Record successful request metrics."""
        duration = (datetime.now() - start_time).total_seconds()
        self.metrics['requests'].append({
            'timestamp': datetime.now().isoformat(),
            'duration': duration,
            'status': 'success'
        })

        # Update aggregate performance metrics
        total_reqs = len(self.metrics['requests'])
        self.metrics['performance'].update({
            'avg_response_time': (
                    (self.metrics['performance']['avg_response_time'] * (total_reqs - 1) + duration)
                    / total_reqs
            ),
            'total_requests': total_reqs,
            'success_rate': (
                    (total_reqs - len(self.metrics['errors'])) / total_reqs * 100
            )
        })

        self.save_metrics()

    def record_error(self, error_message: str):
        """Record error metrics."""
        self.metrics['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'error': error_message
        })
        self.save_metrics()

    def get_performance_metrics(self) -> Dict:
        """Get current performance metrics."""
        return self.metrics['performance']