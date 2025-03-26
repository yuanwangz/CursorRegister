import time
import imaplib
import email
import re
from email.policy import default
from datetime import datetime
import sys

from ._email_server import EmailServer

# Safe print function to handle encoding errors
def safe_print(*args, **kwargs):
    """
    A print function that handles encoding errors safely.
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Try to encode to ASCII with replace for error characters
        new_args = []
        for arg in args:
            if isinstance(arg, str):
                try:
                    # Replace non-ASCII characters with their ASCII approximation or '?'
                    new_args.append(arg.encode('ascii', 'replace').decode('ascii'))
                except:
                    new_args.append("<non-ASCII text>")
            else:
                new_args.append(str(arg))
        
        try:
            print(*new_args, **kwargs)
        except:
            print("<Error printing message>")

class GmailImap(EmailServer):
    """Gmail IMAP client for verification code retrieval"""

    def __init__(self, username, password):
        """
        Initialize Gmail IMAP connection
        
        Parameters:
            username: Gmail email address
            password: Gmail app password
        """
        self.username = username
        self.password = password
        self.imap_server = "imap.gmail.com"
        self.email_address = username
        
        # Connect to Gmail IMAP server
        self.mail = imaplib.IMAP4_SSL(self.imap_server)
        self.mail.login(username, password)
        self.mail.select('inbox')
        
        # Record initialization timestamp as baseline, only get emails after this time
        self.init_timestamp = time.time()
        safe_print(f"[GmailImap] Initialization timestamp: {self.init_timestamp}")
        
        # Record latest email ID to only retrieve new emails
        self.latest_id = self._get_latest_email_id()
        
        # Record processed email IDs to avoid duplicates
        self.processed_ids = set()
        if self.latest_id:
            self.processed_ids.add(self.latest_id)
        
        safe_print(f"[GmailImap] Successfully initialized, email: {username}, latest email ID: {self.latest_id}")

    def _get_latest_email_id(self):
        """Get latest email ID"""
        try:
            _, data = self.mail.uid("SEARCH", None, 'ALL')
            email_ids = data[0].split()
            if email_ids:
                latest_id = email_ids[-1]
                safe_print(f"[GmailImap] Retrieved latest email ID: {latest_id}")
                return latest_id
            return None
        except Exception as e:
            safe_print(f"[GmailImap] Error getting latest email ID: {e}")
            return None
        
    def get_email_address(self):
        """Return Gmail email address"""
        return self.email_address
    
    def fetch_new_emails(self):
        """Get new emails, only retrieve emails received after initialization"""
        # Ensure inbox is selected for each call
        self.mail.select('inbox')
        
        try:
            # Search all emails
            _, data = self.mail.uid("SEARCH", None, 'ALL')
            email_ids = data[0].split()
            
            if not email_ids:
                safe_print("[GmailImap] No emails found")
                return None
                
            # Get latest email ID
            newest_id = email_ids[-1]
            
            # If latest ID is the same and already processed, no new emails
            if newest_id in self.processed_ids:
                safe_print(f"[GmailImap] No new emails, latest ID: {newest_id}")
                return None
            
            # Get latest email
            _, data = self.mail.uid('FETCH', newest_id, '(RFC822)')
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email, policy=default)
            
            # Get email receive time
            received_time = None
            if 'Date' in msg:
                date_str = msg['Date']
                try:
                    # Try to parse email date
                    date_tuple = email.utils.parsedate_tz(date_str)
                    if date_tuple:
                        received_time = email.utils.mktime_tz(date_tuple)
                except:
                    pass
            
            # If receive time is available, verify it's after initialization
            if received_time and received_time < self.init_timestamp:
                safe_print(f"[GmailImap] Skipping email from before initialization, email time: {received_time}, init time: {self.init_timestamp}")
                # Mark as processed
                self.processed_ids.add(newest_id)
                return None
                
            # Extract email information
            from_header = msg.get('From', '')
            subject = msg.get('Subject', '')
            
            # Only process emails from Cursor
            if "cursor" not in from_header.lower() and "cursor" not in subject.lower():
                safe_print(f"[GmailImap] Skipping non-Cursor email, from: {from_header}, subject: {subject}")
                # Mark as processed
                self.processed_ids.add(newest_id)
                return None
            
            # Extract content
            content = ""
            if msg.is_multipart():
                # Handle multipart emails
                for part in msg.get_payload():
                    if part.get_content_type() == 'text/plain':
                        content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                # Handle single part emails
                content = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            # Update latest ID and mark as processed
            self.latest_id = newest_id
            self.processed_ids.add(newest_id)
            
            safe_print(f"[GmailImap] Successfully retrieved new email, ID: {newest_id}, subject: {subject}")
            
            return {
                "from": from_header,
                "subject": subject,
                "text": content,
                "date": msg.get('Date', '')
            }
        except Exception as e:
            safe_print(f"[GmailImap] Error retrieving new email: {e}")
            return None
    
    def extract_verification_code(self, text):
        """
        Extract 6-digit verification code from email content
        """
        if not text:
            return None
            
        # Try multiple patterns to match verification code
        # 1. Direct match of 6 digits
        pattern1 = re.compile(r'\b(\d{6})\b')
        # 2. Match common verification code patterns
        pattern2 = re.compile(r'code[:\s]*(\d{6})', re.IGNORECASE)
        pattern3 = re.compile(r'verification[:\s]*(\d{6})', re.IGNORECASE)
        # 3. Match formatted verification code (e.g., "9 9 2 2 8 2")
        pattern4 = re.compile(r'(\d\s+\d\s+\d\s+\d\s+\d\s+\d)')
        
        for pattern in [pattern1, pattern2, pattern3]:
            match = pattern.search(text)
            if match:
                return match.group(1)
                
        # Handle formatted verification code
        match = pattern4.search(text)
        if match:
            # Remove all spaces
            formatted_code = re.sub(r'\s+', '', match.group(1))
            if formatted_code.isdigit() and len(formatted_code) == 6:
                return formatted_code
                
        return None
    
    def wait_for_new_message(self, delay=5, timeout=300):
        """
        Wait for and return new email with verification code
        
        Parameters:
            delay: Delay between checks (seconds)
            timeout: Timeout period (seconds)
        """
        safe_print(f"[GmailImap] Starting to wait for new emails, timeout: {timeout} seconds")
        start_time = time.time()
        
        while time.time() - start_time <= timeout:
            try:
                email_data = self.fetch_new_emails()
                if email_data and "text" in email_data:
                    safe_print(f"[GmailImap] Successfully received new email: {email_data.get('subject', 'No subject')}")
                    return email_data
            except Exception as e:
                safe_print(f"[GmailImap] Error while waiting for new email: {e}")
                
            # Print remaining wait time
            remaining = timeout - (time.time() - start_time)
            if remaining > 0:
                safe_print(f"[GmailImap] Continuing to wait for new emails, remaining time: {int(remaining)} seconds")
            time.sleep(delay)
        
        safe_print(f"[GmailImap] Timeout waiting for new emails")
        return None
        
    def wait_for_message(self, delay=5, timeout=300):
        """Compatible with EmailServer interface"""
        return self.wait_for_new_message(delay, timeout) 