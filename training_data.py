import json
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Path to the JSON file where classified emails will be saved
CLASSIFIED_EMAILS_FILE = 'classified_emails.json'
# Path for Gmail API credentials
# Make sure to download your credentials.json from Google Cloud Console
# and place it in the project root.
# See: https://developers.google.com/gmail/api/quickstart/python
GMAIL_CREDENTIALS_FILE = 'credentials.json'
GMAIL_TOKEN_FILE = 'token.json' # Will be created automatically after authorization


def authenticate_gmail():
    """Authenticates with the Gmail API and returns the service object."""
    creds = None
    SCOPES = ['https://www.googleapis.com/auth/gmail.modify'] # .modify to archive/move emails
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(GMAIL_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GMAIL_CREDENTIALS_FILE):
                print(f"Error: Gmail credentials file '{GMAIL_CREDENTIALS_FILE}' not found.")
                print("Please download it from Google Cloud Console and place it in the project root.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                GMAIL_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(GMAIL_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)
        print("Gmail API authenticated successfully.")
        return service
    except Exception as e:
        print(f"An error occurred building the Gmail service: {e}")
        return None


def fetch_emails(service, count=50):
    """Fetches a list of unread emails from the inbox."""
    if not service:
        print("Email service not available. Returning mock emails.")
        # Return mock emails for development if Gmail isn't set up
        return [
            {'id': 'mock_id_1', 'subject': 'Test Email 1: Important Update', 'sender': 'test1@example.com', 'body': 'This is the body of test email 1. It contains important information.'},
            {'id': 'mock_id_2', 'subject': 'Test Email 2: Your Weekly Newsletter', 'sender': 'newsletter@example.com', 'body': 'Hello! Here is your weekly newsletter with all the latest updates and news articles.'},
            {'id': 'mock_id_3', 'subject': 'FWD: Funny Cat Video', 'sender': 'friend@example.com', 'body': 'You have to see this hilarious cat video I found!'},
        ]

    try:
        # Call the Gmail API to fetch unread messages from INBOX
        results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=count).execute()
        messages_info = results.get('messages', [])
        emails = []

        if not messages_info:
            print('No unread messages found in your inbox.')
        else:
            print(f"Found {len(messages_info)} unread emails. Fetching details...")
            for msg_info in messages_info:
                # Get the full message details
                msg = service.users().messages().get(userId='me', id=msg_info['id']).execute()
                payload = msg.get('payload', {})
                headers = payload.get('headers', [])
                
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '[No Subject]')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), '[No Sender]')
                
                # The 'snippet' is a short part of the message text.
                # For the full body, more complex parsing of 'payload.parts' might be needed
                # depending on whether the email is plaintext, HTML, or multipart.
                # For this classification task, the snippet should be sufficient as per README.
                body_snippet = msg.get('snippet', '')

                emails.append({
                    'id': msg_info['id'],
                    'subject': subject,
                    'sender': sender,
                    'body': body_snippet # Using snippet as per README
                })
        return emails
    except Exception as e:
        print(f"An error occurred fetching emails: {e}")
        return []


def display_email(email):
    """Displays the email details to the user."""
    print("\n" + "=" * 30)
    print(f"Subject: {email['subject']}")
    print(f"Sender: {email['sender']}")
    print("-" * 10)
    # Truncate body for display if it's longer than, say, 200 chars for readability
    body_preview = email['body']
    if len(body_preview) > 200:
        body_preview = body_preview[:197] + "..."
    print(body_preview)
    print("=" * 30)


def load_classified_emails():
    """Loads previously classified emails from the JSON file."""
    if os.path.exists(CLASSIFIED_EMAILS_FILE):
        try:
            with open(CLASSIFIED_EMAILS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from {CLASSIFIED_EMAILS_FILE}. Starting with an empty list.")
            return []
    return []


def save_classified_email(email_data, classified_emails):
    """Saves the classified email data to the list and writes to JSON file."""
    data_to_save = {
        'subject': email_data['original_subject'],
        'sender': email_data['original_sender'],
        'body_snippet': email_data['original_body'][:100], # As per README
        'reason': email_data['reason'],
        'action': email_data['action']
    }
    classified_emails.append(data_to_save)
    with open(CLASSIFIED_EMAILS_FILE, 'w') as f:
        json.dump(classified_emails, f, indent=2)
    print(f"Saved classification to {CLASSIFIED_EMAILS_FILE}")


def archive_email(service, email_id):
    """Archives the email in Gmail."""
    if not service:
        print(f"Mock archiving email ID: {email_id}")
        return
    # TODO: Implement actual email archiving using Gmail API
    # try:
    #     # Remove 'UNREAD' and 'INBOX' labels, add 'ARCHIVED' or just remove from INBOX
    #     # Common practice is to remove 'INBOX' label to archive
    #     service.users().messages().modify(
    #         userId='me',
    #         id=email_id,
    #         body={'removeLabelIds': ['INBOX', 'UNREAD']}
    #     ).execute()
    #     print(f"Email ID {email_id} archived.")
    # except Exception as e:
    #     print(f"Error archiving email {email_id}: {e}")
    pass


def main():
    """Main application loop."""
    print("Starting Email Classification App...")

    gmail_service = authenticate_gmail()
    emails_to_classify = fetch_emails(gmail_service)
    classified_emails_history = load_classified_emails()

    if not emails_to_classify:
        print("No emails to classify at the moment.")
        if not gmail_service:
            print("Run the script again if you want to use mock emails for testing the flow.")
        return

    for email in emails_to_classify:
        display_email(email)

        while True:
            try:
                reason = input("Reason: ")
                action_input = input("Action (a for Archive, i for Inbox): ").strip().lower()
                if action_input in ['a', 'i']:
                    break
                else:
                    print("Invalid action. Please enter 'a' or 'i'.")
            except EOFError: # Handle Ctrl+D or unexpected end of input
                print("\nExiting classification for this email.")
                return # Or continue to next email, or exit app
            except KeyboardInterrupt:
                print("\nClassification interrupted. Exiting app.")
                return


        action = "archive" if action_input == 'a' else "inbox"

        email_data_to_save = {
            'original_subject': email['subject'],
            'original_sender': email['sender'],
            'original_body': email['body'], # Full body for context, snippet will be saved
            'reason': reason,
            'action': action,
            'id': email.get('id') # Original email ID for potential actions
        }

        save_classified_email(email_data_to_save, classified_emails_history)

        if action == "archive" and email.get('id'):
            if "mock_id" not in email.get('id'): # Don't try to "archive" actual mock emails
                 archive_email(gmail_service, email['id'])
            else:
                print(f"Mock email {email.get('id')} would be archived.")
        else:
            print(f"Email kept in Inbox (or mock email).")

        print("-" * 30)

    print("Finished classifying all fetched emails.")


if __name__ == '__main__':
    main() 