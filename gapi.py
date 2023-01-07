import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from oauth_setup import SCOPES

def _get_gapi_credential() -> Credentials:
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(os.path.join('.secrets', 'token.json')):
        creds = Credentials.from_authorized_user_file(os.path.join('.secrets', 'token.json'), SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception
        # Save the credentials for the next run
        with open(os.path.join('.secrets', 'token.json'), 'w') as token:
            token.write(creds.to_json())
    return creds

def get_calendar_api():
    return build('calendar', 'v3', credentials=_get_gapi_credential())