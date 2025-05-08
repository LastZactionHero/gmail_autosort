import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Constants ---
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# --- Gmail Authentication (copied from main.py) ---
def get_gmail_service():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("ERROR: credentials.json not found. Please download it from Google Cloud Console and place it in the project directory.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        print("Successfully connected to Gmail API.")
        return service
    except Exception as e:
        print(f"An error occurred building the Gmail service: {e}")
        return None

def archive_emails_before_date(service, year, month, day):
    """
    Fetches and archives emails in the inbox received before the specified date.
    """
    date_str = f"{year}/{month:02d}/{day:02d}"
    query = f"in:inbox before:{date_str}"
    print(f"Searching for emails with query: '{query}'")

    page_token = None
    archived_count = 0
    processed_count = 0

    while True:
        try:
            print(f"Fetching page of emails... (Page token: {page_token})")
            results = service.users().messages().list(userId='me', q=query, pageToken=page_token, maxResults=100).execute()
            messages = results.get('messages', [])

            if not messages:
                print("No more messages found matching the criteria.")
                break
            
            print(f"Found {len(messages)} messages on this page.")
            
            # Prepare batch request
            batch = service.new_batch_http_request()
            ids_to_archive_this_batch = []

            for message_stub in messages:
                msg_id = message_stub['id']
                print(f"  Adding message ID {msg_id} to batch for archiving.")
                ids_to_archive_this_batch.append(msg_id)
                processed_count +=1

            if ids_to_archive_this_batch:
                print(f"Archiving batch of {len(ids_to_archive_this_batch)} emails...")
                # To archive, we remove the INBOX label.
                # Note: The batch modify endpoint is more efficient for many messages.
                # However, for simplicity and to ensure each is processed, 
                # we'll iterate, or use batch if it's simple enough.
                # The API allows batching modify requests. Let's try a simple loop first for clarity,
                # then consider batching if performance is an issue for very large numbers.

                # Gmail API batch modify is actually for labels on a *single* message,
                # or batchDelete, batchModify of *multiple messages* but with the same body.
                # The most straightforward way to archive multiple messages is to iterate and call modify.
                # For a very large number of messages, a batch request would be more complex to set up.
                # Let's use individual modify calls within the loop.

                for msg_id_to_archive in ids_to_archive_this_batch:
                    try:
                        service.users().messages().modify(
                            userId='me',
                            id=msg_id_to_archive,
                            body={'removeLabelIds': ['INBOX']}
                        ).execute()
                        print(f"  Successfully archived message ID {msg_id_to_archive}.")
                        archived_count += 1
                    except HttpError as error:
                        print(f"  An error occurred archiving message ID {msg_id_to_archive}: {error}")
                    except Exception as e:
                         print(f"  A non-HTTP error occurred archiving message ID {msg_id_to_archive}: {e}")


            page_token = results.get('nextPageToken')
            if not page_token:
                print("Processed all pages.")
                break
        
        except HttpError as error:
            print(f"An HTTP error occurred: {error}")
            print("This might be a rate limiting issue. Try running the script again later.")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break
            
    print("--- Archiving Summary ---")
    print(f"Total emails processed (checked against date): {processed_count}")
    print(f"Total emails archived: {archived_count}")

def main():
    print("Starting bulk email archiver...")
    gmail_service = get_gmail_service()
    if not gmail_service:
        print("Exiting due to Gmail service initialization failure.")
        return

    # Archive emails before May 1st of the current year
    current_year = datetime.datetime.now().year
    archive_emails_before_date(gmail_service, current_year, 5, 1)
    
    print("Bulk email archiver finished.")

if __name__ == '__main__':
    main() 