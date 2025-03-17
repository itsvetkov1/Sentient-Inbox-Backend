# Sentient Inbox API Documentation

This document provides comprehensive documentation for integrating frontend applications with the Sentient Inbox Backend API.

## Coding Guidelines:

Always prefer simple solutions
Avoid duplication of code whenever possible, which means checking for other areas of the codebase that might already have similar code and functionality
Write code that takes into account the different environments: dev, test, and prod
You are careful to only make changes that are requested or you are confident are well understood and related to the change being requested
When fixing an issue or bug, do not introduce a new pattern or technology without first exhausting all options for the existing implementation. And if you finally do this, make sure to remove the old implementation afterwards so we don't have duplicate logic.
Keep the codebase very clean and organized
Avoid writing scripts in files if possible, especially if the script is likely only to be run once
Avoid having files over 200-300 lines of code. Refactor at that point.
Mocking data is only needed for tests, never mock data for dev or prod
Never add stubbing or fake data patterns to code that affects the dev or prod environments
Never overwrite my .env file without first asking and confirming

## Coding Workflow Preferences:

Focus on the areas of code relevant to the task
Do not touch code that is unrelated to the task
Write thorough tests for all major functionality
Avoid making major changes to the patterns and architecture of how a feature works, after it has shown to work well, unless explicitly instructed
Always think about what other methods and areas of code might be affected by code changes

## Table of Contents
- [Base URL](#base-url)
- [Authentication](#authentication)
  - [Password Authentication](#password-authentication)
  - [OAuth Authentication](#oauth-authentication)
  - [Using Authentication Tokens](#using-authentication-tokens)
- [Email Endpoints](#email-endpoints)
  - [List Emails](#list-emails)
  - [Get Email Details](#get-email-details)
  - [Analyze Email](#analyze-email)
  - [Email Processing Stats](#email-processing-stats)
  - [Email Settings](#email-settings)
  - [Process Email Batch](#process-email-batch)
- [Dashboard Endpoints](#dashboard-endpoints)
  - [Dashboard Statistics](#dashboard-statistics)
  - [User Activity](#user-activity)
  - [Email Account Statistics](#email-account-statistics)
  - [Dashboard Summary](#dashboard-summary)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

## Base URL

All API endpoints are relative to the base URL of your deployed backend. For local development, this will typically be:

```
http://localhost:8000
```

## Authentication

The API uses JWT (JSON Web Token) for authentication. There are two methods to obtain a token:

### Password Authentication

**Endpoint:** `POST /token`

**Description:** Obtain a JWT token using username and password.

**Request (form data):**
```
username: string (required)
password: string (required)
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Example (using fetch):
```javascript
const response = await fetch('/token', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded'
  },
  body: new URLSearchParams({
    'username': 'user@example.com',
    'password': 'securepassword'
  })
});

const data = await response.json();
// Store the token for subsequent requests
localStorage.setItem('access_token', data.access_token);
```

### OAuth Authentication

The API supports OAuth authentication with multiple providers (Google, Microsoft).

#### 1. Get Available Providers

**Endpoint:** `GET /oauth/providers`

**Description:** Get a list of available OAuth providers.

**Response:**
```json
{
  "providers": {
    "google": "Google",
    "microsoft": "Microsoft"
  }
}
```

#### 2. Initiate OAuth Flow

**Endpoint:** `POST /oauth/login`

**Description:** Obtain an authorization URL to redirect the user to.

**Request:**
```json
{
  "provider": "google",
  "redirect_uri": "https://yourapp.com/callback"
}
```

**Response:**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "state": "random-state-string"
}
```

#### 3. Process OAuth Callback

**Endpoint:** `POST /oauth/callback`

**Description:** Exchange the authorization code for an access token.

**Request:**
```json
{
  "provider": "google",
  "code": "authorization-code-from-oauth-provider",
  "redirect_uri": "https://yourapp.com/callback"
}
```

**Response:**
```json
{
  "user": {
    "id": "user-id",
    "username": "user@example.com",
    "email": "user@example.com",
    "display_name": "User Name",
    "permissions": ["view", "process"],
    "profile_picture": "https://...",
    "is_active": true,
    "created_at": "2025-01-01T00:00:00Z",
    "last_login": "2025-03-01T12:00:00Z",
    "oauth_providers": ["google"]
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Example OAuth Flow:

```javascript
// Step 1: Get available providers
const providersResponse = await fetch('/oauth/providers');
const providers = await providersResponse.json();

// Step 2: Initiate OAuth login (when user clicks "Login with Google" button)
const loginResponse = await fetch('/oauth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    provider: 'google',
    redirect_uri: 'https://yourapp.com/callback'
  })
});

const loginData = await loginResponse.json();

// Redirect user to authorization URL
window.location.href = loginData.authorization_url;

// Step 3: Handle callback (in your callback page)
// Get code from URL parameters
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');

const callbackResponse = await fetch('/oauth/callback', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    provider: 'google',
    code: code,
    redirect_uri: 'https://yourapp.com/callback'
  })
});

const userData = await callbackResponse.json();
// Store the token and user info
localStorage.setItem('access_token', userData.access_token);
localStorage.setItem('user', JSON.stringify(userData.user));
```

### Using Authentication Tokens

For authenticated API calls, include the token in the `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Example Authenticated Request:

```javascript
const response = await fetch('/emails', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  }
});
```

#### Get Current User Information

**Endpoint:** `GET /me`

**Description:** Get information about the currently authenticated user.

**Response:**
```json
{
  "id": "user-id",
  "username": "user@example.com",
  "email": "user@example.com",
  "display_name": "User Name",
  "permissions": ["view", "process"],
  "profile_picture": "https://...",
  "is_active": true,
  "created_at": "2025-01-01T00:00:00Z",
  "last_login": "2025-03-01T12:00:00Z",
  "oauth_providers": ["google"]
}
```

## Email Endpoints

### List Emails

**Endpoint:** `GET /emails`

**Description:** Get a paginated list of processed emails with optional filtering.

**Authentication:** Required (view permission)

**Query Parameters:**
- `limit` (integer, default: 20): Maximum number of emails to return
- `offset` (integer, default: 0): Number of emails to skip
- `category` (string, optional): Filter by email category

**Response:**
```json
{
  "emails": [
    {
      "message_id": "email-id-1",
      "subject": "Meeting Agenda",
      "sender": "sender@example.com",
      "received_at": "2025-03-14T10:00:00Z",
      "category": "Meeting",
      "is_responded": true
    },
    {
      "message_id": "email-id-2",
      "subject": "Project Update",
      "sender": "team@example.com",
      "received_at": "2025-03-14T09:30:00Z",
      "category": "Update",
      "is_responded": false
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

### Get Email Details

**Endpoint:** `GET /emails/{message_id}`

**Description:** Get detailed information about a specific email.

**Authentication:** Required (view permission)

**Path Parameters:**
- `message_id` (string, required): Unique email message ID

**Response:**
```json
{
  "message_id": "email-id-1",
  "subject": "Meeting Agenda",
  "sender": "sender@example.com",
  "received_at": "2025-03-14T10:00:00Z",
  "content": {
    "raw_content": "Meeting scheduled for tomorrow at 10 AM...",
    "processed_content": "Processed meeting content...",
    "html_content": "<p>Meeting scheduled for tomorrow at 10 AM...</p>",
    "attachments": ["agenda.pdf", "slides.pptx"]
  },
  "category": "Meeting",
  "is_responded": true,
  "analysis_results": {
    "is_meeting_related": true,
    "category": "Meeting",
    "recommended_action": "Attend",
    "meeting_details": {
      "date": "2025-03-15",
      "time": "10:00",
      "location": "Conference Room A",
      "participants": ["user@example.com", "team@example.com"],
      "agenda": "Quarterly review",
      "missing_elements": []
    }
  },
  "processing_history": [
    {
      "timestamp": "2025-03-14T10:05:00Z",
      "operation": "classification",
      "result": "Meeting"
    },
    {
      "timestamp": "2025-03-14T10:05:30Z",
      "operation": "analysis",
      "result": "success"
    }
  ]
}
```

### Analyze Email

**Endpoint:** `POST /emails/analyze`

**Description:** Analyze email content with the AI pipeline.

**Authentication:** Required (process permission)

**Request:**
```json
{
  "content": "Meeting scheduled for tomorrow at 10 AM...",
  "subject": "Meeting Agenda",
  "sender": "sender@example.com"
}
```

**Response:**
```json
{
  "is_meeting_related": true,
  "category": "Meeting",
  "recommended_action": "Attend",
  "meeting_details": {
    "date": "2025-03-15",
    "time": "10:00",
    "location": "Conference Room A",
    "participants": ["user@example.com", "team@example.com"],
    "agenda": "Quarterly review",
    "missing_elements": []
  },
  "suggested_response": "I'll attend the meeting tomorrow at 10 AM in Conference Room A.",
  "metadata": {
    "analyzed_at": "2025-03-14T10:05:00Z",
    "model_version": "deepseek-reasoner",
    "confidence_score": 0.95,
    "processing_time_ms": 450
  }
}
```

### Email Processing Stats

**Endpoint:** `GET /emails/stats`

**Description:** Get email processing statistics.

**Authentication:** Required (view permission)

**Response:**
```json
{
  "total_emails_processed": 1250,
  "emails_by_category": {
    "Meeting": 450,
    "Update": 325,
    "Request": 275,
    "Notification": 150,
    "Other": 50
  },
  "average_processing_time_ms": 425.5,
  "success_rate": 0.98,
  "stats_period_days": 30,
  "last_updated": "2025-03-14T12:00:00Z"
}
```

### Email Settings

**Endpoint:** `GET /emails/settings`

**Description:** Get current email processing settings.

**Authentication:** Required (view permission)

**Response:**
```json
{
  "batch_size": 10,
  "auto_respond_enabled": true,
  "confidence_threshold": 0.7,
  "processing_interval_minutes": 15,
  "max_tokens_per_analysis": 4000,
  "models": {
    "classification": "llama-3.3-70b-versatile",
    "analysis": "deepseek-reasoner",
    "response": "llama-3.3-70b-versatile"
  }
}
```

**Endpoint:** `PUT /emails/settings`

**Description:** Update email processing settings.

**Authentication:** Required (admin permission)

**Request:**
```json
{
  "batch_size": 20,
  "auto_respond_enabled": true,
  "confidence_threshold": 0.8,
  "processing_interval_minutes": 30,
  "max_tokens_per_analysis": 5000,
  "models": {
    "classification": "llama-3.3-70b-versatile",
    "analysis": "deepseek-reasoner",
    "response": "llama-3.3-70b-versatile"
  }
}
```

**Response:** Updated settings (same format as GET response)

### Process Email Batch

**Endpoint:** `POST /emails/process-batch`

**Description:** Trigger batch processing of unread emails.

**Authentication:** Required (process permission)

**Query Parameters:**
- `batch_size` (integer, default: 50): Number of emails to process in this batch

**Response:**
```json
{
  "processed": 48,
  "errors": 2,
  "success_rate": 0.96,
  "timestamp": "2025-03-14T12:30:00Z"
}
```

## Dashboard Endpoints

### Dashboard Statistics

**Endpoint:** `GET /dashboard/stats`

**Description:** Get comprehensive dashboard statistics.

**Authentication:** Required (view permission)

**Query Parameters:**
- `period` (string, default: "day"): Time period for metrics (day, week, month)

**Response:**
```json
{
  "total_emails": 1250,
  "meeting_emails": 450,
  "response_rate": 0.85,
  "avg_processing_time": 425.5,
  "success_rate": 0.98,
  "volume_trend": [
    {
      "date": "2025-03-13",
      "total": 120,
      "meeting": 45,
      "other": 75
    },
    {
      "date": "2025-03-14",
      "total": 135,
      "meeting": 50,
      "other": 85
    }
  ],
  "category_distribution": [
    {
      "category": "Meeting",
      "count": 450,
      "percentage": 0.36
    },
    {
      "category": "Update",
      "count": 325,
      "percentage": 0.26
    }
  ],
  "performance_metrics": [
    {
      "metric_name": "processing_time",
      "current_value": 425.5,
      "previous_value": 450.2,
      "change_percentage": -5.5,
      "trend": "down"
    }
  ],
  "agent_metrics": [
    {
      "agent_id": "agent-1",
      "agent_name": "Classification Agent",
      "emails_processed": 1250,
      "success_rate": 0.99,
      "avg_processing_time": 120.5,
      "is_active": true
    }
  ],
  "last_updated": "2025-03-14T12:00:00Z"
}
```

### User Activity

**Endpoint:** `GET /dashboard/user-activity`

**Description:** Get user activity summary for the dashboard.

**Authentication:** Required (view permission)

**Response:**
```json
{
  "total_users": 5,
  "active_users": 3,
  "emails_per_user": {
    "user1@example.com": 450,
    "user2@example.com": 375,
    "user3@example.com": 425
  },
  "last_activity": {
    "user1@example.com": "2025-03-14T11:45:00Z",
    "user2@example.com": "2025-03-14T10:30:00Z",
    "user3@example.com": "2025-03-14T12:15:00Z"
  }
}
```

### Email Account Statistics

**Endpoint:** `GET /dashboard/email-accounts`

**Description:** Get statistics for each connected email account.

**Authentication:** Required (view permission)

**Response:**
```json
[
  {
    "email": "user1@example.com",
    "total_processed": 450,
    "categories": {
      "Meeting": 150,
      "Update": 125,
      "Request": 100,
      "Notification": 50,
      "Other": 25
    },
    "is_active": true,
    "last_sync": "2025-03-14T12:00:00Z"
  },
  {
    "email": "user2@example.com",
    "total_processed": 375,
    "categories": {
      "Meeting": 120,
      "Update": 95,
      "Request": 85,
      "Notification": 45,
      "Other": 30
    },
    "is_active": true,
    "last_sync": "2025-03-14T11:45:00Z"
  }
]
```

### Dashboard Summary

**Endpoint:** `GET /dashboard/summary`

**Description:** Get comprehensive dashboard summary.

**Authentication:** Required (view permission)

**Query Parameters:**
- `period` (string, default: "day"): Time period for metrics (day, week, month)

**Response:**
```json
{
  "stats": {
    "total_emails": 1250,
    "meeting_emails": 450,
    "response_rate": 0.85,
    "avg_processing_time": 425.5,
    "success_rate": 0.98,
    "volume_trend": [...],
    "category_distribution": [...],
    "performance_metrics": [...],
    "agent_metrics": [...],
    "last_updated": "2025-03-14T12:00:00Z"
  },
  "user_activity": {
    "total_users": 5,
    "active_users": 3,
    "emails_per_user": {...},
    "last_activity": {...}
  },
  "email_accounts": [
    {
      "email": "user1@example.com",
      "total_processed": 450,
      "categories": {...},
      "is_active": true,
      "last_sync": "2025-03-14T12:00:00Z"
    },
    ...
  ],
  "period": "day"
}
```

## Error Handling

The API uses standard HTTP status codes to indicate the success or failure of a request:

- `200 OK`: The request was successful
- `400 Bad Request`: The request was invalid or incorrectly formatted
- `401 Unauthorized`: Authentication is required or failed
- `403 Forbidden`: The authenticated user does not have the required permissions
- `404 Not Found`: The requested resource was not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: An unexpected error occurred on the server

Error responses include a detailed error message:

```json
{
  "detail": "Error message describing what went wrong"
}
```

## Rate Limiting

The API implements rate limiting to prevent abuse. If you exceed the rate limit, you'll receive a `429 Too Many Requests` response with a `Retry-After` header indicating how many seconds to wait before retrying.

Default rate limits:
- Authentication endpoints: 10 requests per minute
- API endpoints: 60 requests per minute for authenticated users

When implementing the frontend, include appropriate error handling for rate limiting. For example:

```javascript
async function fetchWithRateLimit(url, options = {}) {
  try {
    const response = await fetch(url, options);
    
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After') || 30;
      console.log(`Rate limit exceeded. Retry after ${retryAfter} seconds.`);
      // Implement retry logic or user notification
    }
    
    return response;
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
}
