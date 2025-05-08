import os
import json
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Constants ---
SCOPES = ['https://www.googleapis.com/auth/gmail.modify'] # .modify includes .readonly
CLASSIFIED_EMAILS_FILE = 'classified_emails.json'
INBOX_SAVED_FILE = 'inbox_saved.txt'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- Gmail Authentication ---
def get_gmail_service():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # IMPORTANT: You'll need a credentials.json file from Google Cloud Console
            # for this to work. Download it and place it in the same directory.
            # See: https://developers.google.com/gmail/api/quickstart/python#authorize_credentials_for_a_desktop_application
            if not os.path.exists('credentials.json'):
                print("ERROR: credentials.json not found. Please download it from Google Cloud Console and place it in the project directory.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        print("Successfully connected to Gmail API.")
        return service
    except Exception as e:
        print(f"An error occurred building the Gmail service: {e}")
        return None

# --- File Handling ---
def load_classified_emails():
    """Loads example email classifications from the JSON file."""
    try:
        with open(CLASSIFIED_EMAILS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {CLASSIFIED_EMAILS_FILE} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {CLASSIFIED_EMAILS_FILE}.")
        return []

def load_inbox_saved_ids():
    """Loads message IDs that should be kept in the inbox."""
    try:
        with open(INBOX_SAVED_FILE, 'r') as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        # If the file doesn't exist, it's fine, just means no IDs are saved yet.
        return set()

def save_inbox_id(message_id):
    """Saves a message ID to the inbox_saved.txt file."""
    with open(INBOX_SAVED_FILE, 'a') as f:
        f.write(message_id + '\n')
    print(f"Saved message ID {message_id} to {INBOX_SAVED_FILE}")

# --- Gemini Classification ---
def classify_email_with_gemini(email_data, classified_examples):
    """Classifies an email using the Gemini API."""
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env file.")
        return None
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')

    prompt_parts = [
        "You are an email classification assistant. Your task is to decide if an email should be archived or kept in the inbox.",
        "Based on the provided subject, sender, and body snippet, respond with either '[ARCHIVE]' or '[INBOX]'. Do not add any other text.",
        "Here are some examples of how emails were classified:",
    ]

    for example in classified_examples:
        prompt_parts.append(f"Subject: {example['subject']}")
        prompt_parts.append(f"Sender: {example['sender']}")
        prompt_parts.append(f"Snippet: {example['body_snippet']}")
        prompt_parts.append(f"Reason: {example['reason']}")
        prompt_parts.append(f"Decision: [{example['action'].upper()}]")
        prompt_parts.append("---")


    prompt_parts.append("\n\nLikely topics for archival: TOS updates, promotional emails, newsletters, content that is otherwise not-actionable to contain information the user will ever need to reference.\n")
    prompt_parts.append("Likely topics for inbox: anything that is actionable, important, or time-sensitive. This includes emails from friends and family, recent orders, bills, medical documentation, school notifications, etc.\n\n----\n\n")

    prompt_parts.append("Now, classify the following email:")
    prompt_parts.append(f"Subject: {email_data['subject']}")
    prompt_parts.append(f"Sender: {email_data['sender']}")
    prompt_parts.append(f"Snippet: {email_data['snippet']}")
    prompt_parts.append("Decision:")

    prompt = "\n".join(prompt_parts)
    
    print(f"\n--- Sending request to Gemini for email: {email_data['id']}, {email_data['subject']}, {email_data['sender']} ---")
    # print(f"Prompt: {prompt[:500]}...") # Print a snippet of the prompt

    try:
        response = model.generate_content(prompt)
        decision = response.text.strip().upper()
        print(f"Gemini response: {decision}")
        if decision in ["[ARCHIVE]", "[INBOX]"]:
            return decision
        else:
            print(f"Warning: Gemini returned an unexpected response: {response.text}")
            return None
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

# --- Main Application Logic ---
def process_inbox():
    """Fetches emails, classifies them, and takes action."""
    gmail_service = get_gmail_service()
    if not gmail_service:
        print("Exiting due to Gmail service initialization failure.")
        return

    classified_examples = load_classified_emails()
    if not classified_examples:
        print(f"Warning: No examples found in {CLASSIFIED_EMAILS_FILE}. Classification might be less accurate.")
    
    saved_inbox_ids = load_inbox_saved_ids()
    print(f"Loaded {len(saved_inbox_ids)} IDs from {INBOX_SAVED_FILE}")

    page_token = None
    processed_count = 0
    archived_count = 0
    inbox_count = 0

    while True:
        try:
            print(f"\nFetching inbox page... (Page token: {page_token})")
            results = gmail_service.users().messages().list(userId='me', labelIds=['INBOX'], pageToken=page_token, maxResults=10).execute() # Fetch 10 at a time for now
            messages = results.get('messages', [])

            if not messages:
                print("No more messages found in the inbox.")
                break

            print(f"Found {len(messages)} messages on this page.")

            for message_stub in messages:
                msg_id = message_stub['id']
                
                if msg_id in saved_inbox_ids:
                    print(f"Skipping message ID {msg_id} (already saved to inbox).")
                    continue

                print(f"\nProcessing message ID: {msg_id}")
                msg = gmail_service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['subject', 'from']).execute()
                
                payload = msg.get('payload', {})
                headers = payload.get('headers', [])
                subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), 'N/A')
                sender = next((header['value'] for header in headers if header['name'].lower() == 'from'), 'N/A')
                snippet = msg.get('snippet', '')

                email_data = {
                    'id': msg_id,
                    'subject': subject,
                    'sender': sender,
                    'snippet': snippet
                }
                
                print(f"  Subject: {subject}")
                print(f"  Sender: {sender}")
                print(f"  Snippet: {snippet[:100]}...")

                decision = classify_email_with_gemini(email_data, classified_examples)
                processed_count += 1

                if decision == "[ARCHIVE]":
                    print(f"  Decision for {msg_id}: ARCHIVE. Archiving email...")
                    # To archive, we remove the INBOX label.
                    gmail_service.users().messages().modify(userId='me', id=msg_id, body={'removeLabelIds': ['INBOX']}).execute()
                    archived_count += 1
                    print(f"  Email {msg_id} archived.")
                elif decision == "[INBOX]":
                    print(f"  Decision for {msg_id}: INBOX. Saving ID to skip future checks.")
                    save_inbox_id(msg_id)
                    saved_inbox_ids.add(msg_id) # Add to current session's set as well
                    inbox_count += 1
                else:
                    print(f"  Could not get a clear decision for {msg_id}. Leaving in inbox.")
                    # Optionally, save to a separate file for manual review or treat as INBOX
                    # save_inbox_id(msg_id) 
                    # saved_inbox_ids.add(msg_id)


            page_token = results.get('nextPageToken')
            if not page_token:
                print("Processed all pages of the inbox.")
                break
        
        except Exception as e:
            print(f"An error occurred during email processing: {e}")
            # Potentially add a sleep here or break if it's a persistent error
            break 
            
    print("\n--- Processing Summary ---")
    print(f"Total emails processed in this run: {processed_count}")
    print(f"Emails archived: {archived_count}")
    print(f"Emails kept in inbox (and ID saved): {inbox_count}")
    print(f"Total IDs in {INBOX_SAVED_FILE}: {len(load_inbox_saved_ids())}")


if __name__ == '__main__':
    print("Starting Gmail Auto-Archiver...")
    process_inbox()
    print("Gmail Auto-Archiver finished.") 