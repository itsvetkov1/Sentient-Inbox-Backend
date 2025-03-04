# config/analyzer_config.py

ANALYZER_CONFIG = {
    "default_analyzer": {
        "model": {
            "name": "llama-3.3-70b-versatile",
            "temperature": 0.3,
            "max_tokens": 2000,
            "max_input_tokens": 4000,
            "retry_count": 3,
            "retry_delay": 2
        },
        "content_processing": {
            "preserve_patterns": [
                r'meeting\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?',
                r'schedule.*meeting',
                r'discuss.*at\s+\d{1,2}(?::\d{2})?'
            ],
            "max_paragraphs": 3,
            "token_buffer": 500
        }
    },
    "meeting_analyzer": {
        "model": {
            "name": "llama-3.3-70b-versatile",
            "temperature": 0.3,
            "max_tokens": 2000
        },
        "logging": {
            "base_dir": "logs/meeting_analyzer",
            "archive_retention_days": 30,
            "max_log_size_mb": 10,
            "backup_count": 5
        },
        "analysis": {
            "confidence_threshold": 0.7,
            "review_threshold": 0.5
        }
    },
    "deepseek_analyzer": {
        "model": {
            "name": "deepseek-reasoner",
            "temperature": 0.7,
            "max_tokens": 5000,
            "api_endpoint": "https://api.deepseek.com/v1",
            "api_key": "${DEEPSEEK_API_KEY}"
        },
        "logging": {
            "base_dir": "logs/deepseek_analyzer",
            "archive_retention_days": 30,
            "max_log_size_mb": 10,
            "backup_count": 5
        },
        "analysis": {
            "confidence_threshold": 0.7,
            "review_threshold": 0.5,
            "system_prompt": "You are an AI specialized in analyzing meeting-related communications. Extract key information systematically and provide structured analysis."
        },
        # Simple numeric timeout in seconds - MUST BE A SINGLE INTEGER
        "timeout": 180,  # 3 minutes total timeout
        
        # Retry configuration
        "retry_count": 1,     # Number of retry attempts (1 retry = 2 total attempts)
        "retry_delay": 3,     # Delay between retry attempts in seconds
        
        # Development fallback configuration
        "use_fallback": False,           # Set to True to use mock responses during development
        "use_fallback_on_error": True    # Use fallback analysis when API errors occur
    }
}