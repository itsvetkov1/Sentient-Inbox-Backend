# groq_integration/constants.py

MODEL_CONFIGURATIONS = {
    'complex': {
        'primary': {
            'name': 'llama-3.3-70b-versatile',
            'default_temperature': 0.7,
            'max_tokens': 4096,
            'recommended_tasks': ['meeting_analysis', 'complex_response_generation']
        },
        'fallback': {
            'name': 'llama-3.1-8b-instant',
            'default_temperature': 0.6,
            'max_tokens': 4096,
            'recommended_tasks': ['meeting_analysis', 'response_generation']
        }
    },
    'simple': {
        'primary': {
            'name': 'llama-3.3-70b-versatile',
            'default_temperature': 0.5,
            'max_tokens': 2048,
            'recommended_tasks': ['email_classification', 'simple_responses']
        },
        'fallback': {
            'name': 'llama-3.1-8b-instant',
            'default_temperature': 0.5,
            'max_tokens': 2048,
            'recommended_tasks': ['email_classification']
        }
    }
}

# Default settings for different task types
TASK_SETTINGS = {
    'meeting_analysis': {
        'complexity': 'complex',
        'temperature': 0.7,
        'reasoning_format': 'parsed'
    },
    'email_classification': {
        'complexity': 'simple',
        'temperature': 0.5,
        'reasoning_format': 'raw'
    },
    'response_generation': {
        'complexity': 'complex',
        'temperature': 0.6,
        'reasoning_format': 'parsed'
    }
}
