# Four-Stage Email Analysis Pipeline Specification

## Overview
The email analysis pipeline implements a sophisticated four-stage approach to email processing, utilizing both Llama and Deepseek R1 models. This architecture ensures accurate classification, thorough analysis, appropriate response generation, and efficient delivery of email responses while maintaining optimal handling of meeting-related communications.

## Stage 1: Initial Meeting Classification (Llama Model)

### Purpose
The first stage serves as an initial filter to identify meeting-related content within incoming emails. This stage prevents unnecessary deep analysis of non-meeting emails, optimizing system resources and processing time.

### Input Processing
The Llama model receives the complete email content and applies initial classification logic to determine if the email contains meeting-related information. The system processes emails in batches, examining only previously unprocessed emails.

### Classification Process
The model performs binary classification:
- Positive Classification: Email contains meeting-related content
- Negative Classification: Email contains no meeting-related content

### Duplicate Prevention
The system maintains a weekly rolling history of processed email IDs to prevent duplicate processing. Only unique identifiers are stored, without additional metadata or model outputs.

### Output
The stage produces a binary decision that determines whether the email proceeds to Stage 2 or exits the pipeline.

## Stage 2: Detailed Content Analysis with Response Generation (Deepseek R1 Model)

### Purpose
For emails classified as meeting-related, the Deepseek R1 model performs comprehensive content analysis and generates appropriate responses, aiming to provide immediate assistance whenever possible.

### Core Workflow
1. **Email Ingestion & Initial Processing**
   - Generates unique request ID using content hash + timestamp
   - Performs content length validation and sanitization
   - Creates structured analysis prompt with:
      - Step-by-step evaluation instructions
      - Response templates
      - Format requirements

2. **Comprehensive Content Analysis**
   - **Initial Screening**
     - Meeting request detection
     - Purpose clarity assessment
     - Tone classification (Friendly/Formal)
   - **Completeness Check** (4 Required Elements)
     - Specific time/date → Checks for concrete times/dates
     - Location → Physical/virtual meeting space verification
     - Agenda → Attempt to extract the purpose of the meeting 
     - Attendees → Participant list detection
   - **Risk Assessment**
     - Financial/legal keyword scanning
     - Multi-party coordination complexity
     - Sensitive content detection

3. **Dynamic Response Generation**
   - **Response Logic Matrix:**
     ```
     ┌───────────────────────┬──────────────────────────────┐
     │ Scenario              │ Action                       │
     ├───────────────────────┼──────────────────────────────┤
     │ Complete + Low Risk   → Instant confirmation         │
     │ Missing 1-3 Elements → Request specific missing data │
     │ High Risk Content    → 24h human review notice       │
     │ Info Only            → Polite acknowledgment        │
     └───────────────────────┴──────────────────────────────┘
     ```

   - **Tone Adaptation** based on sender's communication style

### Output
The model generates a structured output containing:
- Comprehensive analysis results
- Specific missing elements (if any)
- Pre-generated response text appropriate to the situation
- Recommended handling category
- Confidence scores for extracted information

> **Important:** The Deepseek analyzer actively attempts to avoid "needs_review" status whenever possible, ensuring senders receive appropriate responses in most scenarios.

## Stage 3: Response Categorization (Response Categorizer)

### Purpose
The third stage processes Deepseek's analysis to finalize categorization and prepare the response for delivery, serving as an integration layer between analysis and delivery.

### Input Processing
The Response Categorizer receives:
- Structured analysis from Deepseek R1
- Pre-generated response text
- Recommended handling category
- Extracted parameters and confidence scores

### Categorization Process
The Response Categorizer:
- Validates the analysis output and recommendation
- Extracts and formats the pre-generated response
- Makes final categorization decision according to the deepseek recommendation
- Prepares the response for delivery

### Classification Categories
The stage assigns one of three final statuses:

1. "standard_response"
   Requirements:
   - Complete analysis with appropriate response text
   - No critical issues requiring human intervention
   Actions:
   - Response text is finalized for delivery
   - Email is prepared for processing by the Email Agent

2. "needs_review"
   Triggers:
   - High risk content identified by Deepseek
   - Complex scenarios beyond automated handling capability
   - System processing uncertainty or low confidence
   Actions:
   - Email is flagged for human review with star in gmail
   - Appropriate notification text is prepared

3. "ignored"
   Criteria:
   - Confirmed non-meeting content
   - Informational-only content requiring polite acknowledgment 
   Actions:
   - Polite acknowledgment  is generated
   - Email is marked as processed and read

## Stage 4: Response Delivery (Email Agent)

### Purpose
The final stage handles the delivery of responses, email status management, and comprehensive record-keeping of all communications.

### Input Processing
The Email Agent receives:
- Final categorization decision
- Finalized response text
- Email metadata

### Delivery Process
The Email Agent:
- Sends appropriate responses to email senders
- Updates email status in Gmail based on category
- Maintains detailed logs of all responses
- Tracks communication history

### Special Handling
- **Standard Response:** Sends response and marks email as read
- **Needs Review:** Marks email with a star in Gmail for visibility and priority handling by human reviewers
- **Ignored:** Updates internal records with no further action and mark it as read

### Output
The stage completes the pipeline by:
- Delivering responses to senders when appropriate
- Setting correct email status and flags in Gmail
- Recording all communications in the response log
- Providing confirmation of successful processing

## Pipeline Integration

The entire four-stage pipeline is orchestrated by the EmailProcessor, which:
- Manages the flow between all stages
- Maintains processing state and history
- Ensures proper error handling throughout the pipeline
- Provides logging and monitoring of the complete process
- Controls batch processing and deduplication