import os
import base64
import argparse
from string import Template
from email.message import EmailMessage
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Load environment variables from .env
load_dotenv()

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def send_email(to_email, subject, body):
    """Shows basic usage of the Gmail API to send an email."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json') and os.path.getsize('token.json') > 2:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json') or os.path.getsize('credentials.json') <= 2:
                print("Error: credentials.json is empty or missing. Please configure Google OAuth credentials first.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # Call the Gmail API
        service = build('gmail', 'v1', credentials=creds)

        message = EmailMessage()
        message.set_content(body)
        message['To'] = to_email
        message['From'] = 'me' # 'me' indicates the authenticated user
        message['Subject'] = subject

        # encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {
            'raw': encoded_message
        }

        # Send the email
        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        print(f"Success! Message sent to {to_email}. Message Id: {send_message['id']}")
        return send_message

    except Exception as error:
        print(f'An error occurred: {error}')
        return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Send an email via Gmail API.')
    parser.add_argument('--to', required=True, help='Recipient email address')
    parser.add_argument('--subject', required=True, help='Email subject line (supports $VAR substitution from environment)')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--body', help='Email body text (supports $VAR substitution from environment)')
    group.add_argument('--template', help='Path to a text file containing the email body template (supports $VAR substitution)')
    
    args = parser.parse_args()

    # Read template if provided
    if args.template:
        with open(args.template, 'r') as f:
            raw_body = f.read()
    else:
        raw_body = args.body

    # Substitute variables using os.environ
    # Template.safe_substitute leaves missing variables as $VAR instead of throwing KeyError
    body = Template(raw_body).safe_substitute(os.environ)
    subject = Template(args.subject).safe_substitute(os.environ)

    send_email(args.to, subject, body)
