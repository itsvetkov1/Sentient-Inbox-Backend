from groq import Groq
from typing import Dict, List, Optional, Union
from datetime import datetime
import asyncio
import json
import os
from dotenv import load_dotenv


class EnhancedGroqClient:
    """Enhanced Groq client with retry logic, error handling, and performance monitoring."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the enhanced Groq client."""
        load_dotenv(override=True)
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY must be provided either through initialization or environment")

        self.client = Groq(api_key=self.api_key)
        self.metrics_file = 'groq_metrics.json'
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

    def save_metrics(self):
        """Save current metrics to file."""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)

    async def process_with_retry(self,
                                 messages: List[Dict],
                                 model: str = "llama-3.3-70b-versatile",
                                 max_retries: int = 3,
                                 **kwargs) -> Dict:
        """Process a request with retry logic and error handling."""
        start_time = datetime.now()
        retries = 0

        while retries < max_retries:
            try:
                # Configure default parameters based on task complexity
                params = {
                    'model': model,
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
                self.record_error(str(e))

                if retries == max_retries:
                    raise Exception(f"Failed after {max_retries} retries: {str(e)}")

                # Exponential backoff
                await asyncio.sleep(2 ** retries)

    def record_success(self, start_time: datetime):
        """Record successful request metrics."""
        duration = (datetime.now() - start_time).total_seconds()
        self.metrics['requests'].append({
            'timestamp': datetime.now().isoformat(),
            'duration': duration,
            'status': 'success'
        })

        # Update performance metrics
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

    async def batch_process(self,
                            requests: List[Dict],
                            model: str = "llama-3.3-70b-versatile",
                            **kwargs) -> List[Dict]:
        """Process multiple requests in parallel."""
        tasks = [
            self.process_with_retry(
                messages=req['messages'],
                model=model,
                **kwargs
            )
            for req in requests
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def get_performance_metrics(self) -> Dict:
        """Get current performance metrics."""
        return self.metrics['performance']