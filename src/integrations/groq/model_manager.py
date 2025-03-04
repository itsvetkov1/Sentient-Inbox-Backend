import json
from datetime import datetime
from typing import Dict, Optional
from .constants import MODEL_CONFIGURATIONS, TASK_SETTINGS


class ModelManager:
    def __init__(self, service_tier: str = None, metrics_file: str = 'model_metrics.json'):
        """
        Initialize the ModelManager with service tier and metrics tracking.

        Args:
            metrics_file: File to store performance metrics
        """
        self.service_tier = service_tier
        self.metrics_file = metrics_file
        self.performance_metrics = self._load_metrics()

    def _load_metrics(self) -> Dict:
        """Load existing performance metrics from file"""
        try:
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'models': {}, 'tasks': {}}

    def get_model_config(self, task_type: str, force_model: Optional[str] = None) -> Dict:
        """
        Get the appropriate model configuration for a task.

        Args:
            task_type: Type of task (e.g., 'meeting_analysis')
            force_model: Optional specific model to use

        Returns:
            Dict containing model configuration
        """
        if force_model:
            # Find and return forced model config
            for complexity in MODEL_CONFIGURATIONS.values():
                for model_type in complexity.values():
                    if model_type['name'] == force_model:
                        return model_type
            raise ValueError(f"Forced model {force_model} not found in configurations")

        # Get task complexity from settings
        task_settings = TASK_SETTINGS.get(task_type)
        if not task_settings:
            raise ValueError(f"Unknown task type: {task_type}")

        complexity = task_settings['complexity']
        models = MODEL_CONFIGURATIONS[complexity]

        # Check performance metrics to decide between primary and fallback
        if self._should_use_fallback(task_type, models['primary']['name']):
            return models['fallback']
        return models['primary']

    def _should_use_fallback(self, task_type: str, primary_model: str) -> bool:
        """Determine if we should use fallback based on recent performance"""
        # Implementation of fallback logic based on metrics
        # This can be expanded based on your specific requirements
        return False

    def record_performance(self, model: str, task_type: str, metrics: Dict):
        """
        Record performance metrics for a model on a specific task.

        Args:
            model: Model name
            task_type: Type of task
            metrics: Dictionary containing performance metrics
        """
        timestamp = datetime.now().isoformat()

        if model not in self.performance_metrics['models']:
            self.performance_metrics['models'][model] = []

        self.performance_metrics['models'][model].append({
            'timestamp': timestamp,
            'task_type': task_type,
            **metrics
        })

        # Save updated metrics
        with open(self.metrics_file, 'w') as f:
            json.dump(self.performance_metrics, f, indent=2)