import os
from datetime import datetime, timedelta
import email.utils
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from integrations.groq.client_wrapper import EnhancedGroqClient

# Set up logging to track what's happening in our application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/mail_sorter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MeetingSorter:
    """A class that processes emails to identify and extract meeting-related information."""

    def __init__(self):
        """Initialize the MeetingSorter with necessary configurations and clients."""
        # Load environment variables for configuration
        load_dotenv(override=True)

        # Initialize our enhanced Groq client for AI processing
        self.groq_client = EnhancedGroqClient()

        # Set up file paths and ensure directories exist
        self.json_file = "data/cache/meeting_mails.json"
        Path(os.path.dirname(self.json_file)).mkdir(parents=True, exist_ok=True)

    def parse_email_content(self, raw_content: str) -> dict:
        """Parse raw email content into a structured format we can work with."""
        email_data = {"headers": {}, "body": ""}

        # Skip metadata lines and process the actual content
        content_lines = raw_content.split('\n')[2:]
        current_section = "headers"

        for line in content_lines:
            if line.startswith('Body:'):
                current_section = "body"
                continue
            elif line.strip() == '' or line.startswith('----'):
                continue

            if current_section == "headers":
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    email_data["headers"][key] = value.strip()
            else:
                email_data["body"] += line + "\n"

        return email_data

    async def extract_meeting_details(self, emails_content: str) -> str:
        """Extract meeting information from email content using AI processing."""
        try:
            # First parse the email into a structured format
            email_data = self.parse_email_content(emails_content)

            # Extract and format sender information
            from_header = email_data['headers'].get('From', '')
            sender_name = from_header.split(' <')[0] if ' <' in from_header else from_header
            sender_email = from_header.split('<')[-1].rstrip('>') if '<' in from_header else from_header

            # Format the content for our AI model to process
            formatted_content = f"""
From: {from_header}
Subject: {email_data['headers'].get('Subject', '')}
Date: {email_data['headers'].get('Date', '')}
Content: {email_data['body']}
"""

            # Define our AI system prompt for meeting detection
            system_prompt = """You are an expert email analyzer specialized in meeting request identification.
            Analyze the email and extract meeting information in the following JSON format:
            {
                "found_meetings": boolean,
                "meetings": [{
                    "date": "YYYY-MM-DD",
                    "time": "HH:MM",
                    "topic": "string",
                    "location": "string or null",
                    "sender_name": "string",
                    "sender_email": "string"
                }]
            }

            Follow these rules:
            - Convert all relative dates to YYYY-MM-DD format
            - Use 24-hour time format (HH:MM)
            - Include both physical and virtual meeting locations
            - Set found_meetings to false if time information is ambiguous"""

            # Process with our enhanced Groq client
            response = await self.groq_client.process_with_retry(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": formatted_content}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )

            # Extract and process the response
            content = response.choices[0].message.content.strip()
            logger.debug(f"Groq API Response: {content}")

            # Parse and validate the JSON response
            parsed_json = json.loads(content)

            # Process any relative dates in the response
            if parsed_json.get("found_meetings", False):
                email_date = email.utils.parsedate_to_datetime(
                    email_data['headers'].get('Date', '')
                )
                parsed_json = self._process_relative_dates(parsed_json, email_date)

            return json.dumps(parsed_json, indent=2)

        except Exception as e:
            logger.error(f"Error extracting meeting details: {str(e)}", exc_info=True)
            return json.dumps({
                "found_meetings": False,
                "meetings": [],
                "error": str(e)
            }, indent=2)

    def _process_relative_dates(self, data: Dict, reference_date: datetime) -> Dict:
        """Convert relative dates to absolute dates based on the email's date."""
        date_keywords = {
            "tomorrow": timedelta(days=1),
            "next week": timedelta(days=7),
            "day after tomorrow": timedelta(days=2),
            "next month": timedelta(days=30),
        }

        for meeting in data.get("meetings", []):
            if meeting.get("date"):
                date_str = meeting["date"].lower()

                # Handle relative date expressions
                for keyword, delta in date_keywords.items():
                    if keyword in date_str:
                        new_date = reference_date + delta
                        meeting["date"] = new_date.strftime("%Y-%m-%d")
                        break

        return data

    async def process_emails(self, email_file_path: str) -> str:
        """Main method to process emails and extract meeting information."""
        try:
            # Try to read the email file with UTF-8 encoding first
            emails_content = self._read_email_file(email_file_path)

            # Extract and process meeting details
            json_response = await self.extract_meeting_details(emails_content)

            # Save results and return formatted output
            self.save_to_json(json_response)
            return self.format_results(json_response)

        except Exception as e:
            logger.error(f"Error processing emails: {str(e)}", exc_info=True)
            return f"Error processing emails: {str(e)}"

    def _read_email_file(self, file_path: str) -> str:
        """Read email file with encoding fallback."""
        encodings = ['utf-8', 'latin-1', 'ascii']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()
            except UnicodeDecodeError:
                continue

        raise ValueError(f"Could not read file with any of the encodings: {encodings}")

    def format_results(self, json_response: str) -> str:
        """Format the JSON response into a human-readable string."""
        try:
            data = json.loads(json_response)
        except json.JSONDecodeError:
            return "Error: Could not parse meeting data"

        if not data.get("found_meetings", False):
            return "No meeting emails found."

        output = "Meeting-related emails found:\n\n"
        for meeting in data.get("meetings", []):
            output += f"Date: {meeting.get('date', 'Not specified')}\n"
            output += f"Time: {meeting.get('time', 'Not specified')}\n"
            output += f"Topic: {meeting.get('topic', 'Not specified')}\n"
            output += f"From: {meeting.get('sender_name', 'Unknown')} "
            output += f"<{meeting.get('sender_email', 'unknown')}>\n"
            if meeting.get('location'):
                output += f"Location: {meeting['location']}\n"
            output += "-" * 50 + "\n"

        return output

    def save_to_json(self, json_response: str) -> None:
        """Save the extracted meeting information to a JSON file with deduplication."""
        try:
            data = json.loads(json_response)
            current_time = datetime.now().isoformat()

            # Load or initialize stored data
            try:
                with open(self.json_file, 'r') as f:
                    stored_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                stored_data = {
                    "last_updated": current_time,
                    "meetings": []
                }

            # Add new meetings only if they don't exist
            if data.get("found_meetings", False):
                for new_meeting in data.get("meetings", []):
                    if not self._is_duplicate_meeting(stored_data, new_meeting):
                        stored_data["meetings"].append({
                            "date": new_meeting.get("date"),
                            "time": new_meeting.get("time"),
                            "topic": new_meeting.get("topic"),
                            "sender": {
                                "name": new_meeting.get("sender_name"),
                                "email": new_meeting.get("sender_email")
                            },
                            "location": new_meeting.get("location"),
                            "added_on": current_time
                        })

            stored_data["last_updated"] = current_time

            # Save updated data
            with open(self.json_file, 'w') as f:
                json.dump(stored_data, f, indent=2, sort_keys=True, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error saving to JSON: {str(e)}", exc_info=True)

    def _is_duplicate_meeting(self, stored_data: Dict, new_meeting: Dict) -> bool:
        """Check if a meeting already exists in stored data."""
        return any(
            existing_meeting.get("date") == new_meeting.get("date") and
            existing_meeting.get("time") == new_meeting.get("time") and
            existing_meeting.get("topic", "").lower() == new_meeting.get("topic", "").lower() and
            existing_meeting.get("sender", {}).get("email") == new_meeting.get("sender_email")
            for existing_meeting in stored_data.get("meetings", [])
        )
