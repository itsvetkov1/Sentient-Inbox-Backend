# Email Management System Development Instructions

## System Overview and Purpose
This automated email management system focuses on meeting coordination through Gmail integration. The system leverages a sophisticated AI-powered architecture using Groq and Deepseek, with specialized components designed for efficient email processing and response handling. The foundation includes secure storage encryption and Gmail integration with OAuth2 authentication.

## Core Architecture Implementation Flow
The system processes emails through a sophisticated four-stage pipeline, utilizing specialized models and components for comprehensive email understanding, response generation, and delivery.

### Stage 1: Initial Meeting Classification (LlamaAnalyzer)
The first stage employs a Llama model to perform preliminary email classification with these key functions:
- Analysis of incoming email content to determine meeting-related information
- Binary classification (meeting-related or not)
- Processing of only new, unhandled emails using unique identifiers
- Maintenance of a weekly rolling history of processed email IDs for deduplication

### Stage 2: Detailed Content Analysis and Response Generation (DeepseekAnalyzer)
When an email is classified as meeting-related, the Deepseek R1 model performs comprehensive content analysis and generates appropriate responses:

**Core Workflow:**
1. **Email Ingestion & Initial Processing**
   - Generates unique request ID using content hash + timestamp
   - Performs content length validation and sanitization
   - Creates structured analysis prompt with comprehensive instructions

2. **Comprehensive Content Analysis**
   - Initial screening for meeting content and tone
   - Completeness check for required elements (time/date, location, agenda, attendees)
   - Risk assessment for sensitive content and complexity

3. **Dynamic Response Generation**
   - Generates appropriate responses based on analysis results
   - Adapts tone to match sender's communication style
   - Provides specific responses for different scenarios:
     - Complete + Low Risk → Instant confirmation
     - Missing Elements → Request for specific missing data
     - High Risk Content → Human review notification
     - Info Only → Polite acknowledgment

> The DeepseekAnalyzer actively attempts to avoid "needs_review" status whenever possible, ensuring senders receive appropriate responses in most scenarios.

### Stage 3: Response Categorization (ResponseCategorizer)
The Response Categorizer processes Deepseek's analysis to finalize the handling category and prepare responses:
- Processes structured output from DeepseekAnalyzer
- Extracts and validates pre-generated response text
- Makes final categorization decisions (standard_response, needs_review, ignored)
- Prepares response for delivery

### Stage 4: Response Delivery (EmailAgent)
The Email Agent handles the final delivery and status management:
- Sends responses for standard_response emails
- Updates email status in Gmail based on categorization
- Marks needs_review emails with a star for visibility
- Maintains comprehensive response logs
- Records all communications for future reference

## Email Processing Rules and Requirements

### Required Meeting Details
Standard response processing requires:
- Date (with validated format)
- Time (with clear specification)
- Location (physical or virtual meeting space)
- Agenda (purpose of the meeting)

### Standard Response Template
Template structure with parameter insertion:
"Thank you for your meeting request. I am pleased to confirm our meeting on {params['date']['value']} at {params['time']['value']} at {params['location']['value']}"

### Batch Processing Specifications
- Batch size: 100 emails per processing cycle
- Processing of only new, unhandled emails
- Weekly rolling history maintenance
- Deduplication checks before processing

### Error Handling and Retry Logic
- Single retry attempt with 3-second delay
- No retries for content parsing failures
- Comprehensive error reporting
- DEBUG level logging for all operations
- Input/output logging for troubleshooting

## System Evolution and Future Features

### High Priority Development
1. Agent coordination system implementation
2. Monitoring dashboard development
3. Agent configuration interface
4. Enhanced response template system

### Planned Feature Expansion
1. Auto-reminder System:
   - Independent service architecture
   - API endpoint accessibility
   - Frontend integration capability

2. Advanced Features:
   - Multi-agent architecture
   - Calendar integration with conflict detection
   - Frontend customization options
   - Template customization interface
   - Variable field insertion system
   - Processing rules configuration

### Lower Priority Enhancements
1. Timezone handling improvements
2. Advanced PII detection and handling
3. Performance metrics expansion

## Development Guidelines
Development priorities should focus on:
1. Maintaining the integrity of the four-stage pipeline
2. Ensuring proper integration between all components
3. Implementing robust error handling throughout the pipeline
4. Supporting the dynamic response generation capabilities
5. Enhancing Gmail status management for better visibility

The system should be developed with consideration for:
- Future distributed system architecture
- API endpoint development
- Frontend communication requirements
- Scalability and maintenance
- Security and data protection

This architecture ensures a robust, scalable system that provides timely responses to meeting-related emails while maintaining reliable processing capabilities and appropriate human oversight when needed.