# Email Processing Rules and Mechanisms

## Introduction
This document details the comprehensive set of rules and mechanisms governing email processing within the system. These specifications ensure consistent handling of emails across the pipeline while maintaining efficiency and reliability.

## Processing Pipeline Overview

### Four-Stage Processing Pipeline
The system implements a sophisticated four-stage processing pipeline:

1. **Initial Classification (LlamaAnalyzer)**
   - Binary classification of emails (meeting-related or not)
   - Initial filtering to optimize processing resources
   - Processing of only unique, unhandled emails

2. **Content Analysis & Response Generation (DeepseekAnalyzer)**
   - Comprehensive content analysis of meeting-related emails
   - Required elements verification (time/date, location, agenda, attendees)
   - Risk assessment for complex or sensitive content
   - Dynamic response generation based on analysis results
   - Tone adaptation to match sender's communication style

3. **Response Categorization (ResponseCategorizer)**
   - Processing of Deepseek analysis output
   - Extraction and validation of pre-generated responses
   - Final categorization decision-making
   - Preparation of responses for delivery

4. **Response Delivery (EmailAgent)**
   - Sending of appropriate responses to senders
   - Email status management in Gmail
   - Special handling for needs_review emails (starred in Gmail)
   - Comprehensive response logging

## Batch Processing Specifications

### Batch Size Management
The system processes emails in controlled batches to optimize resource utilization and maintain system stability. Each processing cycle handles up to 100 emails, ensuring efficient throughput while preventing system overload. This batch size was chosen to balance processing efficiency with system responsiveness.

### Processing Sequence
Emails are processed in chronological order within each batch. The system maintains strict processing order to ensure no emails are inadvertently skipped or processed out of sequence. Each email undergoes the complete four-stage pipeline:

1. LlamaAnalyzer determines if the email is meeting-related
2. If meeting-related, DeepseekAnalyzer performs content analysis and generates appropriate response
3. ResponseCategorizer finalizes the categorization and prepares response
4. EmailAgent handles delivery and status management

## Email History Tracking

### Weekly Rolling History
The system implements a weekly rolling history mechanism to track processed emails. This approach ensures efficient resource utilization while maintaining adequate historical context for duplicate prevention. The history tracking system stores only essential information:
- Unique email identifiers
- No additional metadata
- No model outputs or processing results

### Cleanup Process
At the end of each week, the system automatically purges outdated history entries. This ensures the history tracking system remains efficient and prevents unnecessary resource consumption while maintaining sufficient historical data for proper operation.

## Duplicate Processing Prevention

### Identifier Tracking
The system uses unique email identifiers to prevent duplicate processing. Before processing any email, the system checks these identifiers against the weekly history. This mechanism ensures that each email is processed exactly once, preventing redundant analysis and responses.

### History Verification
Before initiating the analysis pipeline for any email, the system performs a thorough check against the historical record. Emails found in the history are automatically skipped, ensuring system resources are focused on new, unprocessed content.

## Required Meeting Parameters

### Mandatory Fields
Four specific parameters are required for optimal processing:
- Date of the meeting (specific day)
- Time of the meeting (specific hour)
- Location (physical or virtual)
- Agenda (purpose of the meeting)

### Parameter Validation
Each required parameter undergoes validation to ensure completeness and accuracy:
- Date must be in a recognized format
- Time must be clearly specified
- Location must be explicitly stated
- Agenda must provide sufficient context

## Response Generation Rules

### Dynamic Response Generation
The DeepseekAnalyzer implements a sophisticated response generation system:

```
Response Logic Matrix:
┌───────────────────────┬──────────────────────────────┐
│ Scenario              │ Action                       │
├───────────────────────┼──────────────────────────────┤
│ Complete + Low Risk   → Instant confirmation         │
│ Missing 1-3 Elements → Request specific missing data │
│ High Risk Content    → 24h human review notice       │
│ Info Only            → Polite acknowledgment        │
└───────────────────────┴──────────────────────────────┘
```

### Tone Adaptation
Responses are dynamically adapted to match the sender's communication style:

| Scenario          | Friendly Response                          | Formal Response                              |
|-------------------|--------------------------------------------|----------------------------------------------|
| Needs Review      | "Hey Sam! We'll get back within 24h 😊"    | "Dear Ms. Smith: Your request is under review..." |
| Missing Info      | "Hi! Could you share the time? 🕒"         | "Please provide meeting time at your earliest..." |

### Response Priority
The system prioritizes sending appropriate responses whenever possible. The DeepseekAnalyzer actively attempts to avoid "needs_review" status, ensuring senders receive timely responses in most scenarios.

## Email Status Management

### Read/Unread Status
The system maintains precise control over email status:
- Emails receiving standard responses are marked as read after processing
- Emails requiring review remain unread
- Ignored emails maintain their current status

### Starring System
The system implements specific starring rules:
- All emails classified for review are starred for visibility and priority handling
- This provides a visual indicator for emails requiring human attention
- Starred emails can be easily filtered and identified in Gmail

## Data Integrity and Validation

### Input Validation
Every email entering the processing pipeline undergoes validation:
- Verification of required fields
- Format checking of critical data
- Structural integrity validation

### Output Verification
The system verifies all processing outputs:
- Confirmation of status changes
- Validation of response generation
- Verification of history updates

## Special Considerations

### Attachment Handling
Emails containing attachments receive special processing:
- Meeting-related emails with attachments are assessed for risk
- Complex attachments may trigger needs_review classification
- Attachment presence is logged for tracking purposes

### Multiple Request Handling
When multiple requests are detected:
- The system attempts to generate appropriate responses when possible
- Complex multiple requests may trigger needs_review classification
- Original email remains unread and starred if human review is needed

## System Monitoring and Logging

### Processing Metrics
The system maintains detailed logs at DEBUG level, with particular emphasis on:
- Batch processing statistics
- Parameter validation results
- Status change operations
- Template processing results
- Gmail status management operations

### Error Tracking
Comprehensive error logging includes:
- Parameter validation failures
- Processing exceptions
- Status update errors
- Template processing issues
- Response delivery failures

This specification ensures consistent and reliable email processing while maintaining system efficiency and accuracy. Each rule and mechanism works in concert to provide a robust email management solution with appropriate responses to senders and efficient handling of complex scenarios.