import os
import webbrowser
from openai import OpenAI
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def gmail_authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def create_gmail_draft(subject, body, to=""):
    service = gmail_authenticate()
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft = service.users().drafts().create(
        userId='me',
        body={'message': {'raw': raw}}
    ).execute()
    print(f"Draft created: https://mail.google.com/mail/u/0/#drafts?compose={draft['id']}")

def draft_email(client, message):
    prompt = f"""
    Draft a professional email based on the following user request. Only output the email body, do not include any headers or signatures.
    User request: {message}
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an assistant that drafts professional emails."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.5
    )
    email_body = response.choices[0].message.content.strip().replace('\n', '%0D%0A')
    # Open the default mail client with the draft
    return email_body

def list_messages(service, user_id='me', max_results=10):
    results = service.users().messages().list(userId=user_id, maxResults=max_results).execute()
    messages = results.get('messages', [])
    for msg in messages:
        msg_id = msg['id']
        msg_detail = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
        snippet = msg_detail.get('snippet', '')
        print(f"Message ID: {msg_id}")
        print(f"Snippet: {snippet}")
        print('-' * 40)

if __name__ == '__main__':
    service = gmail_authenticate()
    list_messages(service)
