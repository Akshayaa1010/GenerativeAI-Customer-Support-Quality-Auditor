import sys
import os
import json
import logging
import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Get project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)

def extract_selected_emails(server=None, port=None, email_user=None, email_pass=None, folder="INBOX"):
    """
    Connects to email server via IMAP, retrieves the latest email from the specified folder,
    extracts the subject and body (stripping HTML tags if present), and saves the results.
    """
    # Fallback to env variables if not provided
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    
    server = server or os.getenv("IMAP_SERVER", "imap.gmail.com")
    port = port or os.getenv("IMAP_PORT", "993")
    email_user = email_user or os.getenv("IMAP_EMAIL")
    email_pass = email_pass or os.getenv("IMAP_PASSWORD")
    
    if not email_user or not email_pass:
        return {"success": False, "error": "IMAP credentials not provided or configured in .env"}
        
    try:
        port = int(port)
    except ValueError:
        return {"success": False, "error": f"Invalid port: {port}"}

    logger.info(f"Connecting to {server}:{port} via IMAP SSL...")
    try:
        # Connect and login
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(email_user, email_pass)
        
        # Select folder
        status, select_info = mail.select(folder)
        if status != 'OK':
            mail.logout()
            return {"success": False, "error": f"Failed to select folder '{folder}': {select_info}"}
            
        # Search all emails
        status, messages = mail.search(None, 'ALL')
        if status != 'OK':
            mail.logout()
            return {"success": False, "error": "Failed to search mailbox"}
            
        mail_ids = messages[0].split()
        if not mail_ids:
            mail.logout()
            return {"success": False, "error": f"No emails found in folder '{folder}'"}
            
        # Get the latest message ID
        latest_email_id = mail_ids[-1]
        
        # Fetch the message content
        status, data = mail.fetch(latest_email_id, '(RFC822)')
        if status != 'OK':
            mail.logout()
            return {"success": False, "error": "Failed to fetch email data"}
            
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        # Decode the email subject
        subject = "No Subject"
        if msg["Subject"]:
            decoded_header_parts = decode_header(msg["Subject"])
            subject_parts = []
            for part, encoding in decoded_header_parts:
                if isinstance(part, bytes):
                    try:
                        subject_parts.append(part.decode(encoding or "utf-8", errors="replace"))
                    except Exception:
                        subject_parts.append(part.decode("latin-1", errors="replace"))
                else:
                    subject_parts.append(str(part))
            subject = "".join(subject_parts)
            
        # Extract email body
        body = ""
        if msg.is_multipart():
            # Walk multipart email
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Fetch text plain
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                        break
                    except Exception:
                        pass
                # Fetch text HTML if plain text not found
                elif content_type == "text/html" and "attachment" not in content_disposition and not body:
                    try:
                        html_content = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                        soup = BeautifulSoup(html_content, "html.parser")
                        body = soup.get_text()
                    except Exception:
                        pass
        else:
            # Single part email
            content_type = msg.get_content_type()
            try:
                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="replace")
                if content_type == "text/html":
                    soup = BeautifulSoup(body, "html.parser")
                    body = soup.get_text()
            except Exception:
                pass
                
        body = body.strip()
        if not body:
            body = "No text content found in the email."
            
        email_data = {
            "subject": subject,
            "body": body,
            "platform": "IMAP"
        }
        
        # Save to extracted_email.json (for backwards-compatibility/pipelines)
        data_dir = os.path.join(PROJECT_ROOT, "data")
        os.makedirs(data_dir, exist_ok=True)
        output_path = os.path.join(data_dir, "extracted_email.json")
        with open(output_path, "w") as f:
            json.dump(email_data, f)
            
        logger.info(f"Success! Extracted email subject: {subject}")
        mail.close()
        mail.logout()
        return {"success": True, "data": email_data}
        
    except Exception as e:
        logger.error(f"IMAP Extraction failed: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # If run directly, read from env and extract
    result = extract_selected_emails()
    if result["success"]:
        print(json.dumps(result["data"], indent=2))
        sys.exit(0)
    else:
        print(f"Error: {result['error']}")
        sys.exit(1)
