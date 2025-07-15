import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from format import format_event_details
from openai import OpenAI

CAL_SCOPES = ['https://www.googleapis.com/auth/calendar']
SECRET = "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"
CLIENT_ID = "1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com"

class ScheduleService:
    def __init__(self, access_token: str, refresh_token: str, client_id: str = CLIENT_ID, client_secret: str = SECRET):
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=CAL_SCOPES
        )
        self.client = build('calendar', 'v3', credentials=creds)

class ScheduleIntentHandler:
    def __init__(self, schedule_service: ScheduleService):
        self.schedule_service = schedule_service
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def classify_schedule_function(self, message: str) -> str:
        """Classify what schedule function the user wants to perform"""
        system_prompt = '''
        Classify the user's scheduling request into one of these categories:
        - "add": User wants to add a new event
        - "edit": User wants to edit an existing event
        - "delete": User wants to delete an event
        Return ONLY ONE WORD from the choices above.
        '''
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=20,
            temperature=0.3
        )
        return response.choices[0].message.content.strip().lower()

    async def handle_schedule_intent(self, message: str, pending_changes: dict = None) -> Tuple[str, dict, bool]:
        """Main handler for schedule intents"""
        schedule_function = await self.classify_schedule_function(message)
        if schedule_function == "add":
            return await self.add_event(message, pending_changes)
        elif schedule_function == "edit":
            return await self.edit_event(message, pending_changes)
        elif schedule_function == "delete":
            return await self.delete_event(message, pending_changes)
        else:
            return await self.add_event(message, pending_changes)

    async def add_event(self, message: str, pending_changes: dict = None) -> Tuple[str, dict, bool]:
        """Extract event details and return confirmation"""
        system_prompt = f"""
        Today is {datetime.now()}.
        You are an assistant that extracts scheduling details from the user's last inputs. Your job is to guess title, start_time, end_time, and attendees from natural text. 
        Then, list any missing or unclear fields and generate a polite confirmation message asking the user to confirm or correct.
        Strictly use ISO 8601 format for times. This means, each time NEEDS A DATE. If the date is unclear, prompt the user. 
        If no specific date is given, then default to today's date. If no end_time is given, assume the event will last one hour.

        REQUIRED FIELDS: title, start_time
        OPTIONAL FIELDS: end_time, attendees

        Reply *only* with valid JSON. Example:

        "title": "...",
        "start_time": "...",   // ISO-8601, if not ISO-8601, convert first. It must be this format.
        "end_time": "...",     // ISO-8601, if not ISO-8601, convert first. It must be this format. or null (optional)
        "attendees": ["email1", ...], // optional
        "missing_fields": ["start_time", ...], // only include required fields that are missing
        "confirmation_message": "..."

        If there are any current known details, merge them with the JSON that you will return.
        MAKE SURE THE START/END TIMES ARE IN A FORMAT like this "2025-07-14T22:00:00"
        """
        user_prompt = f"User message: {message}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        if pending_changes:
            messages.append({
                "role": "assistant",
                "content": f"Current known details (JSON): {json.dumps(pending_changes)}"
            })
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.4
        )
        content = response.choices[0].message.content.strip()
        try:
            data = json.loads(content)
            data["type"] = "schedule_add"
            missing_fields = data.get("missing_fields", [])
            show_accept_deny = len(missing_fields) == 0
            confirmation_message = data["confirmation_message"]
            details = format_event_details(data)
            if details:
                confirmation_message += f"\n\n---\n**📋 Current Details:**\n{details}\n---"
            return confirmation_message, data, show_accept_deny
        except Exception as e:
            return f"Sorry, I couldn't parse the event details. Could you please provide the event information again?", None, False

    async def edit_event(self, message: str, pending_changes: dict = None) -> Tuple[str, dict, bool]:
        """Extract edit details and return confirmation"""
        system_prompt = '''
        You are an assistant that extracts event edit details from the user's input. Guess which fields to update (title, start_time, end_time, attendees). List any missing or unclear fields and generate a polite confirmation message asking the user to confirm or correct. Use ISO 8601 for times.
        REQUIRED FIELDS: event_id, at least one field to update
        OPTIONAL FIELDS: title, start_time, end_time, attendees
        Reply *only* with valid JSON. Example:
        {"event_id": "...", "updates": {"title": "..."}, "missing_fields": ["event_id"], "confirmation_message": "..."}
        If there are any current known details, merge them with the JSON you return.
        '''
        user_prompt = f"User message: {message}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        if pending_changes:
            messages.append({
                "role": "assistant",
                "content": f"Current known details (JSON): {json.dumps(pending_changes)}"
            })
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.4
        )
        content = response.choices[0].message.content.strip()
        try:
            data = json.loads(content)
            data["type"] = "schedule_edit"
            missing_fields = data.get("missing_fields", [])
            show_accept_deny = len(missing_fields) == 0
            confirmation_message = data["confirmation_message"]
            details = format_event_details(data.get("updates", {}))
            if details:
                confirmation_message += f"\n\n---\n**📋 Update Details:**\n{details}\n---"
            return confirmation_message, data, show_accept_deny
        except Exception as e:
            return f"Sorry, I couldn't parse the edit details. Could you please provide the update information again?", None, False

    async def delete_event(self, message: str, pending_changes: dict = None) -> Tuple[str, dict, bool]:
        """Extract delete details and return confirmation"""
        system_prompt = '''
        You are an assistant that extracts event deletion details from the user's input. Guess which event to delete (event_id, title, or time). List any missing or unclear fields and generate a polite confirmation message asking the user to confirm or correct.
        REQUIRED FIELDS: event_id
        OPTIONAL FIELDS: title, start_time, end_time
        Reply *only* with valid JSON. Example:
        {"event_id": "...", "title": "...", "missing_fields": ["event_id"], "confirmation_message": "..."}
        If there are any current known details, merge them with the JSON you return.
        '''
        user_prompt = f"User message: {message}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        if pending_changes:
            messages.append({
                "role": "assistant",
                "content": f"Current known details (JSON): {json.dumps(pending_changes)}"
            })
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.4
        )
        content = response.choices[0].message.content.strip()
        try:
            data = json.loads(content)
            data["type"] = "schedule_delete"
            missing_fields = data.get("missing_fields", [])
            show_accept_deny = len(missing_fields) == 0
            confirmation_message = data["confirmation_message"]
            details = self.format_event_details(data)
            if details:
                confirmation_message += f"\n\n---\n**📋 Event to Delete:**\n{details}\n---"
            return confirmation_message, data, show_accept_deny
        except Exception as e:
            return f"Sorry, I couldn't parse the delete details. Could you please provide the event information again?", None, False

# Factory function to create schedule handler

def create_schedule_handler(access_token: str, refresh_token: str, client_id: str = CLIENT_ID, client_secret: str = SECRET) -> ScheduleIntentHandler:
    schedule_service = ScheduleService(access_token, refresh_token, client_id, client_secret)
    return ScheduleIntentHandler(schedule_service) 