"""
Enhanced Gmail Client Implementation

This module implements a comprehensive Gmail API client with robust authentication
handling, detailed logging, and thorough error management. It integrates with
the AuthenticationManager to provide reliable email access while maintaining
proper security protocols and error recovery mechanisms.

Design Considerations:
- Robust authentication and token management through AuthenticationManager
- Comprehensive error handling with detailed logging
- Automatic service recovery on token expiration
- Thread-safe email operations
- Memory-efficient batch processing

Integration Requirements:
- Requires AuthenticationManager from auth_manager.py
- Expects proper logging configuration
- Gmail API scopes must match AuthenticationManager
"""

import base64
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText

from .auth_manager import GmailAuthenticationManager

logger = logging.getLogger(__name__)

class GmailClient:
    """
    Gmail API client with comprehensive error handling and automatic recovery.
    
    Implements reliable Gmail API access with:
    - Robust authentication management
    - Automatic service recovery
    - Detailed operation logging
    - Comprehensive error handling
    - Efficient batch processing
    
    Attributes:
        auth_manager: Authentication manager instance
        service: Authenticated Gmail API service
        batch_size: Maximum number of emails to process in one batch
        retry_count: Number of retry attempts for failed operations
    """
    
    def __init__(self, batch_size: int = 50, retry_count: int = 3):
        """
        Initialize Gmail client with configurable parameters.
        
        Args:
            batch_size: Maximum number of emails to process in one batch
            retry_count: Number of retry attempts for failed operations
            
        Raises:
            RuntimeError: If initial service initialization fails
        """
        self.auth_manager = GmailAuthenticationManager()
        self.batch_size = batch_size
        self.retry_count = retry_count
        
        # Initialize service with proper error handling
        self.service = self._initialize_service()
        if not self.service:
            raise RuntimeError("Failed to initialize Gmail service")
            
        logger.info("Gmail client initialized successfully")

    def _initialize_service(self) -> Optional[Any]:
        """
        Initialize Gmail service with robust error handling.
        
        Implements proper error recovery and logging during service
        initialization. Handles authentication failures gracefully.
        
        Returns:
            Authenticated Gmail service or None if initialization fails
        """
        try:
            service = self.auth_manager.create_gmail_service()
            if not service:
                logger.error("Failed to create Gmail service")
                return None
                
            logger.info("Gmail service initialized successfully")
            return service
            
        except Exception as e:
            logger.error(f"Service initialization failed: {str(e)}")
            return None

    def refresh_service(self) -> bool:
        """
        Refresh Gmail service with new authentication.
        
        Attempts to refresh the Gmail service when authentication
        expires or becomes invalid. Implements proper error handling
        and logging.
        
        Returns:
            bool: True if refresh successful, False otherwise
        """
        try:
            logger.info("Attempting service refresh")
            self.service = self.auth_manager.create_gmail_service()
            return bool(self.service)
            
        except Exception as e:
            logger.error(f"Service refresh failed: {str(e)}")
            return False

    def _extract_email_parts(self, msg: Dict) -> Tuple[str, List[Dict]]:
        """
        Extract email content and attachments with comprehensive parsing.
        
        Implements thorough MIME parsing with proper error handling for
        various email content types and encodings.
        
        Args:
            msg: Raw message dictionary from Gmail API
            
        Returns:
            Tuple containing (email_body, attachments_list)
        """
        body = ""
        attachments = []
        
        try:
            if 'parts' in msg['payload']:
                for part in msg['payload']['parts']:
                    content = self._process_message_part(msg['id'], part)
                    if content:
                        if isinstance(content, str):
                            body += content
                        else:
                            attachments.append(content)
            else:
                body = self._decode_body(msg['payload']['body'].get('data', ''))
                
            return body or 'No content available', attachments
            
        except Exception as e:
            logger.error(f"Error extracting email parts: {str(e)}")
            return 'Error processing content', []

    def _process_message_part(self, message_id: str, part: Dict) -> Optional[Any]:
        """
        Process individual message part with type-specific handling.
        
        Implements comprehensive MIME type handling with proper error
        recovery for various content types.
        
        Args:
            message_id: Gmail message ID
            part: Message part dictionary
            
        Returns:
            Processed content or None if processing fails
        """
        try:
            mime_type = part['mimeType']
            
            if mime_type == 'text/plain':
                if 'data' in part['body']:
                    return self._decode_body(part['body']['data'])
                elif 'attachmentId' in part['body']:
                    return self._fetch_attachment(message_id, part['body']['attachmentId'])
            elif mime_type.startswith('image/') or mime_type.startswith('application/'):
                if 'attachmentId' in part['body']:
                    return {
                        'id': part['body']['attachmentId'],
                        'mime_type': mime_type,
                        'filename': part.get('filename', 'unknown')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing message part: {str(e)}")
            return None

    def _decode_body(self, encoded_data: str) -> str:
        """
        Decode email body with robust error handling.
        
        Implements comprehensive decoding with proper error recovery
        for various encoding types.
        
        Args:
            encoded_data: Base64 encoded content
            
        Returns:
            Decoded content string or error message
        """
        if not encoded_data:
            return ''
            
        try:
            return base64.urlsafe_b64decode(encoded_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error decoding content: {str(e)}")
            return 'Error decoding content'

    def _fetch_attachment(self, message_id: str, attachment_id: str) -> Optional[str]:
        """
        Fetch and process email attachment with error handling.
        
        Implements secure attachment retrieval with proper error
        handling and logging.
        
        Args:
            message_id: Gmail message ID
            attachment_id: Attachment identifier
            
        Returns:
            Processed attachment content or None if fetch fails
        """
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            return self._decode_body(attachment['data'])
            
        except Exception as e:
            logger.error(f"Error fetching attachment: {str(e)}")
            return None

    def get_unread_emails(self, max_results: Optional[int] = None) -> List[Dict]:
        """
        Retrieve unread emails with comprehensive metadata.
        
        Implements efficient batch processing with proper error handling
        and automatic service recovery.
        
        Args:
            max_results: Maximum number of emails to retrieve
                        (defaults to class batch_size)
                        
        Returns:
            List of processed email dictionaries
        """
        if max_results is None:
            max_results = self.batch_size
            
        try:
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['UNREAD'],
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            return self._process_messages(messages)
            
        except RefreshError:
            logger.warning("Authentication refresh required")
            if self.refresh_service():
                return self.get_unread_emails(max_results)
            return []
            
        except Exception as e:
            logger.error(f"Error fetching unread emails: {str(e)}")
            return []

    def _process_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        Process message batch with comprehensive error handling.
        
        Implements thorough message processing with proper error
        recovery for each message.
        
        Args:
            messages: List of message metadata from Gmail API
            
        Returns:
            List of processed email dictionaries
        """
        processed_messages = []
        
        for message in messages:
            try:
                full_msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()
                
                email_data = self._extract_message_data(full_msg)
                if email_data:
                    processed_messages.append(email_data)
                    
            except Exception as e:
                logger.error(f"Error processing message {message['id']}: {str(e)}")
                continue
                
        return processed_messages

    def _extract_message_data(self, msg: Dict) -> Optional[Dict]:
        """
        Extract comprehensive message data with metadata.
        
        Implements thorough message parsing with proper error handling
        for all message components.
        
        Args:
            msg: Full message dictionary from Gmail API
            
        Returns:
            Processed email dictionary or None if extraction fails
        """
        try:
            headers = msg['payload']['headers']
            body, attachments = self._extract_email_parts(msg)
            
            return {
                "message_id": msg['id'],
                "thread_id": msg.get('threadId', ''),
                "thread_messages": self._get_thread_messages(msg.get('threadId', '')),
                "subject": self._get_header(headers, 'Subject', 'No Subject'),
                "sender": self._get_header(headers, 'From', 'No Sender'),
                "recipients": self._extract_recipients(headers),
                "received_at": self._get_header(headers, 'Date', 'No Date'),
                "content": body,
                "attachments": attachments,
                "labels": msg.get('labelIds', []),
                "processed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error extracting message data: {str(e)}")
            return None

    def _get_header(self, headers: List[Dict], name: str, default: str = '') -> str:
        """
        Extract header value with proper error handling.
        
        Args:
            headers: List of message headers
            name: Header name to extract
            default: Default value if header not found
            
        Returns:
            Header value or default
        """
        return next((h['value'] for h in headers if h['name'] == name), default)

    def _extract_recipients(self, headers: List[Dict]) -> List[str]:
        """
        Extract all recipient addresses with deduplication.
        
        Implements comprehensive recipient extraction with proper
        handling of various address formats.
        
        Args:
            headers: List of message headers
            
        Returns:
            List of unique recipient addresses
        """
        recipients = set()
        recipient_fields = ['To', 'Cc', 'Bcc']
        
        for field in recipient_fields:
            value = self._get_header(headers, field)
            if value:
                # Split and clean email addresses
                addresses = [addr.strip() for addr in value.split(',')]
                recipients.update(addresses)
                
        return list(recipients)

    def _get_thread_messages(self, thread_id: str) -> List[str]:
        """
        Retrieve all message IDs in a thread with error handling.
        
        Args:
            thread_id: Gmail thread identifier
            
        Returns:
            List of message IDs in the thread
        """
        if not thread_id:
            return []
            
        try:
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()
            
            return [msg['id'] for msg in thread['messages']]
            
        except Exception as e:
            logger.error(f"Error getting thread messages: {str(e)}")
            return []

    def modify_message_labels(
        self,
        message_id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None
    ) -> bool:
        """
        Modify message labels with comprehensive error handling.
        
        Implements robust label modification with proper error
        recovery and automatic service refresh.
        
        Args:
            message_id: Gmail message ID
            add_labels: Labels to add
            remove_labels: Labels to remove
            
        Returns:
            True if modification successful, False otherwise
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={
                    'addLabelIds': add_labels or [],
                    'removeLabelIds': remove_labels or []
                }
            ).execute()
            return True
            
        except RefreshError:
            if self.refresh_service():
                return self.modify_message_labels(message_id, add_labels, remove_labels)
            return False
            
        except Exception as e:
            logger.error(f"Error modifying message {message_id} labels: {str(e)}")
            return False

    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark message as read with error handling.
        
        Returns:
            True if operation successful, False otherwise
        """
        return self.modify_message_labels(message_id, remove_labels=['UNREAD'])

    def mark_as_unread(self, message_id: str) -> bool:
        """
        Mark message as unread with error handling.
        
        Returns:
            True if operation successful, False otherwise
        """
        return self.modify_message_labels(message_id, add_labels=['UNREAD'])
    
    def send_email(self, to_email: str, subject: str, message_text: str) -> bool:
        """
        Send an email using Gmail API with comprehensive error handling.
        
        Implements secure email transmission with proper authentication management,
        automatic token refresh, and detailed logging throughout the process.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            message_text: Plain text email body content
            
        Returns:
            bool: True if sending successful, False otherwise
        """
        try:
            # Create email MIME message
            message = MIMEText(message_text)
            message['to'] = to_email
            message['subject'] = subject
            
            # Convert to raw format required by Gmail API
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Process with proper error handling for authentication issues
            for attempt in range(self.retry_count + 1):
                try:
                    logger.info(f"Sending email to {self._mask_email(to_email)} with subject: {subject}")
                    
                    # Send the message using Gmail API
                    result = self.service.users().messages().send(
                        userId="me",
                        body={'raw': raw_message}
                    ).execute()
                    
                    message_id = result.get('id', '')
                    logger.info(f"Email sent successfully, message_id: {message_id}")
                    return True
                    
                except RefreshError:
                    logger.warning("Authentication refresh required during email sending")
                    if self.refresh_service():
                        continue  # Retry with refreshed service
                    return False
                    
                except Exception as e:
                    if attempt < self.retry_count:
                        logger.warning(f"Email sending attempt {attempt + 1} failed: {e}")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                        
                    logger.error(f"Failed to send email after {self.retry_count + 1} attempts: {e}")
                    return False
                
        except Exception as e:
            logger.error(f"Error preparing email for sending: {e}")
            return False
            
    def _mask_email(self, email: str) -> str:
        """
        Mask email addresses for privacy in logs.
        
        Implements privacy protection by masking parts of email addresses
        while preserving enough information for debugging purposes.
        
        Args:
            email: Email address to mask
            
        Returns:
            Masked email address
        """
        if not email or '@' not in email:
            return email
            
        try:
            username, domain = email.split('@', 1)
            if len(username) <= 2:
                masked_username = '*' * len(username)
            else:
                masked_username = username[0] + '*' * (len(username) - 2) + username[-1]
                
            domain_parts = domain.split('.')
            masked_domain = domain_parts[0][0] + '*' * (len(domain_parts[0]) - 1)
            
            return f"{masked_username}@{masked_domain}.{'.'.join(domain_parts[1:])}"
        except Exception:
            # If masking fails, return a generic masked value
            return "***@***.***"