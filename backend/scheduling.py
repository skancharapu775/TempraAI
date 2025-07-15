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

    def summarize_events(self, time_min: str, time_max: str) -> list:
        """Fetch events between time_min and time_max (ISO 8601, RFC3339) and return a list of event dicts."""
        from datetime import datetime
        import re
        # Ensure time_min and time_max are in RFC3339 (with 'Z' for UTC if no tzinfo)
        def to_rfc3339(dt_str):
            # If already ends with 'Z' or has timezone, return as is
            if re.search(r'[+-][0-9]{2}:[0-9]{2}$', dt_str) or dt_str.endswith('Z'):
                return dt_str
            # If only date, add T00:00:00Z
            if len(dt_str) == 10:
                return dt_str + 'T00:00:00Z'
            # If no timezone, add Z
            if 'T' in dt_str and 'Z' not in dt_str and '+' not in dt_str:
                return dt_str + 'Z'
            return dt_str
        time_min = to_rfc3339(time_min)
        time_max = to_rfc3339(time_max)
        events_result = self.client.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        return events

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
        - "summarize": User wants to summarize events for a period (day, week, month)
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
        elif schedule_function == "summarize":
            summary = await self.summarize_events_intent(message)
            return summary, None, False
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

    async def summarize_events_intent(self, message: str) -> str:
        """Summarize events for a specific day, week, etc. based on user message, using LLM for a word summary."""
        # Use OpenAI to extract the period (day, week, month) and the reference date from the message
        system_prompt = '''
        Extract the period (day, week, month) and the reference date from the user's message. Return valid JSON like:
        {"period": "day", "date": "2025-07-16"}
        If no date is given, use today's date. Period must be one of: day, week, month.
        '''
        user_prompt = f"User message: {message}"
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
        try:
            import json
            from datetime import datetime, timedelta
            data = json.loads(content)
            period = data.get("period", "day")
            date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
            date = datetime.fromisoformat(date_str)
            if period == "day":
                time_min = date.replace(hour=0, minute=0, second=0).isoformat()
                time_max = (date + timedelta(days=1)).replace(hour=0, minute=0, second=0).isoformat()
            elif period == "week":
                start_of_week = date - timedelta(days=date.weekday())
                time_min = start_of_week.replace(hour=0, minute=0, second=0).isoformat()
                time_max = (start_of_week + timedelta(days=7)).replace(hour=0, minute=0, second=0).isoformat()
            elif period == "month":
                time_min = date.replace(day=1, hour=0, minute=0, second=0).isoformat()
                if date.month == 12:
                    next_month = date.replace(year=date.year+1, month=1, day=1)
                else:
                    next_month = date.replace(month=date.month+1, day=1)
                time_max = next_month.replace(hour=0, minute=0, second=0).isoformat()
            else:
                return "Sorry, I couldn't understand the period you want to summarize."
            events = self.schedule_service.summarize_events(time_min, time_max)
            if not events:
                return f"No events found for the selected {period}."
            # Prepare a compact list of event summaries
            event_summaries = []
            for event in events:
                event_data = {
                    "title": event.get("summary", "(No Title)"),
                    "start_time": event['start'].get('dateTime', event['start'].get('date', '')),
                    "end_time": event['end'].get('dateTime', event['end'].get('date', '')),
                    "attendees": [a['email'] for a in event.get('attendees', [])] if event.get('attendees') else []
                }
                event_summaries.append(event_data)
            # Use LLM to generate a word summary
            summary_prompt = f"""
            Summarize the following calendar events in a concise, natural language paragraph. Focus on the main themes, busy/quiet periods, and any notable meetings or patterns. The user's request was: '{message}'.
            Events:
            {json.dumps(event_summaries, indent=2)}
            """
            summary_response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an assistant that summarizes calendar events for users."},
                    {"role": "user", "content": summary_prompt}
                ],
                max_tokens=200,
                temperature=0.5
            )
            return summary_response.choices[0].message.content.strip()
        except Exception as e:
            return f"Sorry, I couldn't summarize your events. Error: {e}"
        
# Factory function to create schedule handler
def create_schedule_handler(access_token: str, refresh_token: str, client_id: str = CLIENT_ID, client_secret: str = SECRET) -> ScheduleIntentHandler:
    schedule_service = ScheduleService(access_token, refresh_token, client_id, client_secret)
    return ScheduleIntentHandler(schedule_service) 