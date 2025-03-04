# Email Classification Categories and Handling Specifications

## Overview
This document outlines the three primary classification categories used in the email management system, detailing the specific requirements, criteria, and handling procedures for each category. The classification system ensures consistent and appropriate handling of all incoming emails while maintaining efficient processing and user-friendly organization.

## Standard Response Category

### Definition and Purpose
The "standard_response" classification indicates emails that can be handled automatically through the system's response mechanism. These emails have sufficient information for the system to generate appropriate responses without human intervention.

### Qualification Requirements
For an email to qualify for standard response handling, it typically meets the following criteria:
- Contains clear meeting-related content
- Provides sufficient information for appropriate response generation
- Presents minimal complexity or risk factors
- Has clear parameters if it's a meeting request
- Contains no complex attachments requiring review

### Processing Actions
When an email is classified for standard response, the system performs these actions:
- Sends the pre-generated response from DeepseekAnalyzer
- Stars the email for future reference
- Marks the email as read after successful response
- Records the processing in the weekly history

### Response Types
The system may generate various types of standard responses:
- Confirmation for complete meeting requests
- Information requests for meetings with missing details
- Acknowledgments for informational emails
- Clarification requests for ambiguous content

## Needs Review Category

### Definition and Purpose
The "needs_review" classification indicates emails that require human attention due to complexity, sensitive content, or other factors that prevent automated handling. This category ensures human oversight for appropriate situations but it's with low priority and only when unavoidable.

### Triggering Conditions
An email is classified for review under these conditions:
- High-risk content identified during analysis
- Complex scenarios beyond automated handling capabilities
- Multi-party coordination requirements
- Financial or legal implications detected
- Complex attachments requiring human assessment

### Processing Actions
For emails requiring review, the system:
- Maintains unread status
- Applies star marking for visibility and priority
- Preserves all attachments and original formatting
- May generate a notification of pending review
- Records the classification in processing history

### Special Handling Requirements
The system implements specific handling for review cases:
- Gmail starring provides visual indication for priority attention
- Star marking ensures easy filtering and identification
- Preservation of unread status maintains visibility in inbox
- Response generation may include pending review notification

## Ignore Category

### Definition and Purpose
The "ignored" classification applies to emails that require no action, either because they contain no meeting-related content or have been determined to need no response.

### Classification Criteria
Emails are classified for ignoring when:
- Confirmed as non-meeting related content
- Meeting content is determined to be informational only
- No action or response is required
- Content falls outside the scope of meeting management

### Processing Actions
For ignored emails, the system:
- Maintains current status
- Performs no response generation
- Records the classification in processing history
- Takes no further action

### Verification Process
Before finalizing ignore classification:
- Confirms absence of meeting-related content
- Verifies no response requirement
- Ensures no critical information is overlooked
- Records classification reasoning

## Response Generation Guidelines

### Standard Response Generation
The system generates responses based on the email content and analysis results:

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

## Classification Process Flow

### Initial Stage (LlamaAnalyzer)
- Performs binary classification (meeting-related or not)
- Non-meeting emails typically proceed to ignored category
- Meeting-related emails proceed to detailed analysis

### Detailed Analysis Stage (DeepseekAnalyzer)
- Performs comprehensive content analysis
- Generates appropriate response when possible
- Identifies potential review requirements
- Provides structured output for categorization

### Final Categorization Stage (ResponseCategorizer)
- Processes structured analysis output
- Makes final categorization decisions
- Prepares responses for delivery
- Determines email handling requirements

### Delivery Stage (EmailAgent)
- Implements appropriate handling based on category
- Sends responses for standard_response emails
- Sets correct email status in Gmail
- Stars emails requiring review
- Maintains comprehensive response logs

This classification system ensures appropriate handling of all incoming emails while maintaining efficient processing and organization. Each category has specific criteria and actions that work together to provide comprehensive email management with appropriate human oversight when needed.