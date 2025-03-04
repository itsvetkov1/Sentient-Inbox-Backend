# Technical Context

## Technologies Used

### Core Technologies
- Python 3.x (with asyncio)
- FastAPI (REST API framework)
- Gmail API
- Groq API (for Llama model integration)
- Deepseek API (for Deepseek R1 model integration)
- BeautifulSoup4 for HTML processing
- JSON for structured data storage and communication
- Uvicorn (ASGI server)

### Key Dependencies
- fastapi: REST API framework
- uvicorn: ASGI server implementation
- pydantic: Data validation and API models
- groq-sdk: Groq API integration for Llama model
- deepseek-sdk: Deepseek API integration for Deepseek R1 model
- google-api-python-client: Gmail API access
- beautifulsoup4: HTML content processing
- python-dotenv: Environment management
- typing-extensions: Type hints support
- pathlib: Path manipulation
- logging: Comprehensive DEBUG level logging
- zoneinfo: Timezone handling for dates
- email: RFC 2822 email parsing

## API Endpoints

### Email Processing
- POST /api/process-emails
  - Process a batch of emails
  - Parameters: batch_size (default: 100)
  - Returns: ProcessEmailResponse

### System Maintenance
- POST /api/maintenance
  - Run maintenance tasks
  - Returns: MaintenanceResponse

### Health Check
- GET /api/health
  - Check API health status
  - Returns: Health status object

## Development Setup

### Environment Configuration
1. Required Environment Variables:
   - GROQ_API_KEY
   - DEEPSEEK_API_KEY
   - Gmail OAuth credentials
   
2. Directory Structure:
```
sentient-inbox/
├── data/
│   ├── secure/          # Encrypted data storage
│   ├── cache/           # Weekly rolling history
│   └── metrics/         # Performance metrics
├── docs/                # Documentation
├── src/
│   ├── email_processing/
│   │   ├── analyzers/   # Llama and Deepseek analyzers
│   │   ├── handlers/    # Content and date processing
│   │   └── classification/
│   ├── integrations/    # API integrations
│   └── utils/          # Shared utilities
├── logs/               # System logs
└── memory-bank/        # System memory
```

3. File Organization:
   - main.py: Entry point
   - content.py: Content preprocessing and date handling
   - llama_analyzer.py: Initial classification and final decision
   - deepseek_analyzer.py: Detailed content analysis
   - email_writer.py: Response generation
   - secure_storage.py: Encrypted data management

## Technical Constraints

### API Limitations
- Groq API rate limits
- Deepseek API rate limits
- Gmail API quotas
- Response time requirements
- Token limits for model inputs
- HTML parsing complexity

### Performance Requirements
- FastAPI async request handling
- Efficient HTML content cleaning
- Accurate date pattern recognition
- Smart content chunking and preservation
- Token limit optimization
- Batch processing of 100 emails per cycle
- Efficient three-stage analysis pipeline
- Quick response generation for standard responses
- Reliable error recovery with single retry and 3-second delay

### Security Requirements
- CORS configuration for API endpoints
- OAuth2 authentication for Gmail integration
- Secure API key storage for Groq and Deepseek
- HTML content sanitization
- Pattern validation security
- Error message safety
- Processing metadata privacy
- Encrypted storage for processed emails

## Development Practices

### Code Standards
- Type hints with dataclasses
- PEP 8 compliance
- Async/await patterns
- Comprehensive error handling
- Pattern preservation practices
- Token management strategies

### Logging System
- DEBUG level logging for all operations
- File-based logging with rotation
- Structured log format for easy parsing
- Comprehensive error and exception logging
- Processing statistics tracking
- Pattern preservation monitoring

### Error Handling
- Custom ContentProcessingError
- Single retry attempt with 3-second delay
- Graceful degradation for parsing failures
- Pattern validation errors
- Token limit violations
- Date parsing fallbacks
- HTML cleaning recovery

### Testing Requirements
- API endpoint testing
- Unit tests for content processing
- Date parsing validation tests
- Pattern preservation verification
- Token management testing
- HTML cleaning validation
- Integration testing for full pipeline
- Error scenario coverage
- Performance benchmarking

## Monitoring & Metrics

### Performance Tracking
- API endpoint response times
- Request success rates
- HTML cleaning efficiency
- Date extraction accuracy
- Pattern preservation success
- Token estimation accuracy
- Content chunking effectiveness
- Processing statistics analysis
- Error frequency by type
- API usage monitoring

### Data Management
- Structured content processing results
- Enhanced date pattern storage
- Pattern preservation tracking
- Processing metadata collection
- Token usage statistics
- Error pattern analysis
- Performance metrics collection

This technical context ensures robust and efficient email processing through sophisticated content handling, comprehensive error management, and detailed performance tracking.
