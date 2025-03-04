# Email Management API

## Overview

This API provides a secure REST interface to the email processing system, allowing you to:

- Authenticate users with JWT tokens
- Process and analyze emails
- Retrieve email processing results
- Configure system settings
- Get email processing statistics

## Authentication

The API uses JSON Web Tokens (JWT) for authentication with role-based access control:

- **Admin Role** - Full system access including configuration changes
- **Process Role** - Can trigger email processing and view results
- **View Role** - Can only view processed emails and statistics

### Development Credentials

For local development, the following users are pre-configured:

- **Admin User**
  - Username: `admin`
  - Password: `securepassword`
  - Permissions: admin, process, view

- **Viewer User**
  - Username: `viewer`
  - Password: `viewerpass`
  - Permissions: view

## API Endpoints

### Authentication

- `POST /token` - OAuth2 token endpoint (form submission)
- `POST /login` - User login endpoint (JSON)

### Email Processing

- `GET /emails/` - Get paginated list of processed emails
- `GET /emails/{message_id}` - Get detailed email information
- `POST /emails/analyze` - Analyze email content
- `GET /emails/stats` - Get email processing statistics
- `GET /emails/settings` - Get current email processing settings
- `PUT /emails/settings` - Update email processing settings
- `POST /emails/process-batch` - Trigger batch email processing

### System Monitoring

- `GET /health` - Simple health check endpoint

## Running the API Server

You can run the API server using the provided `run_api.py` script:

```bash
# Run in development mode with auto-reload
python run_api.py --reload

# Run on a specific host and port
python run_api.py --host 0.0.0.0 --port 5000

# Run in production mode
python run_api.py --env production
```

In development mode, you can access the Swagger UI documentation at: http://127.0.0.1:8000/docs

## Example Usage

### Authentication

```bash
# Get access token
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=securepassword"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Analyzing an Email

```bash
# Analyze email
curl -X POST "http://localhost:8000/emails/analyze" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hi Team, Let's meet tomorrow at 2pm in Conference Room A to discuss the project. Best, John",
    "subject": "Meeting Request",
    "sender": "john@example.com"
  }'
```

Response:
```json
{
  "is_meeting_related": true,
  "category": "meeting",
  "recommended_action": "respond",
  "meeting_details": {
    "date": "tomorrow",
    "time": "2pm",
    "location": "Conference Room A",
    "agenda": "discuss the project",
    "participants": null,
    "missing_elements": []
  },
  "suggested_response": "Hi John, I'm pleased to confirm our meeting tomorrow at 2pm in Conference Room A to discuss the project. Looking forward to it!",
  "metadata": {
    "analyzed_at": "2025-02-27T23:47:32.145123",
    "model_version": "1.0.0",
    "confidence_score": 0.85,
    "processing_time_ms": 352
  }
}
```

### Processing Batch of Emails

```bash
# Process email batch
curl -X POST "http://localhost:8000/emails/process-batch?batch_size=20" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response:
```json
{
  "processed": 5,
  "errors": 0,
  "success_rate": 1.0,
  "timestamp": "2025-02-27T23:48:01.129875"
}
```

## Security Considerations

1. **JWT Secret**: In production, ensure you set a strong JWT_SECRET_KEY in the environment or .env file
2. **CORS Settings**: Configure the CORS_ORIGINS environment variable for production
3. **Rate Limiting**: The API includes rate limiting to protect against abuse

## Integration Architecture

The API connects to the core email processing system through the `EmailService` which acts as an integration layer between the HTTP API and the core processing components:

```
│ FastAPI Routes │ ───► │ Email Service │ ───► │ Email Processor │
     │                                              │
     ▼                                              ▼
│ Auth Service  │                         │ Email Analyzers │
```

This architecture ensures a clean separation of concerns and allows the API to evolve independently from the core processing logic.
