from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
router = APIRouter()


SECRET = "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"
CLIENT_ID = "1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com"

class GcalData(BaseModel):
    access_token: str
    start_time: str  # ISO 8601 format
    end_time: str    # ISO 8601 format
    title: str
    # personal_email: str

def create_google_event(access_token, refresh_token, start_time, end_time, title):
    creds = Credentials(token=access_token, refresh_token=refresh_token, token_uri="https://oauth2.googleapis.com/token", client_id=CLIENT_ID, client_secret=SECRET)
    service = build('calendar', 'v3', credentials=creds)

    event = {
        'summary': title,
        'start': {
            'dateTime': start_time,
            'timeZone': 'America/New_York',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'America/New_York',
        },
        # 'attendees': [{'email': personal_email}],
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    return event.get('htmlLink')
