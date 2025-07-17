import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from format import format_event_details
from openai import OpenAI
import pytz
import re

eastern = pytz.timezone("America/New_York")
now = datetime.now(eastern)
today_str = now.strftime("%Y-%m-%d")
default_time_min = now.strftime("%Y-%m-%dT00:00:00-05:00")  # or use .isoformat()
default_time_max = (now + timedelta(days=7)).strftime("%Y-%m-%dT23:59:59-05:00")

CAL_SCOPES = ['https://www.googleapis.com/auth/calendar']
SECRET = "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"
CLIENT_ID = "1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com"

def clean_llm_json(content):
    # Remove code block markers
    content = re.sub(r'^```(json)?', '', content.strip(), flags=re.IGNORECASE)
    content = re.sub(r'```$', '', content.strip())
    # Remove BOM
    content = content.encode('utf-8').decode('utf-8-sig')
    # Remove trailing commas before }
    content = re.sub(r',\s*}', '}', content)
    content = re.sub(r',\s*]', ']', content)
    return content.strip()

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
        - "edit": User wants to edit or move an existing event
        - "delete": User wants to delete an event
        - "summarize": User wants to summarize events for a period (day, week, month)
        Return ONLY ONE WORD from the choices above.
        '''
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
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
            model="gpt-4",
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

    async def extract_date_range_from_message(self, message: str) -> tuple:
        system_prompt = f'''
        Today is {today_str}.
        Extract the date or date range from the user's message. Return valid JSON like:
        {{"time_min": "2025-07-16T00:00:00Z", "time_max": "2025-07-16T23:59:59Z"}}
        or for a range:
        {{"time_min": "2025-07-16T00:00:00Z", "time_max": "2025-07-20T23:59:59Z"}}
        If no date is given, use today's date as time_min and 7 days from today as time_max.
        All times must be in ISO 8601 format with Z (UTC).
        '''
        user_prompt = f"User message: {message}"
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            time_min = data.get("time_min", default_time_min)
            time_max = data.get("time_max", default_time_max)
            return time_min, time_max
        except Exception:
            return default_time_min, default_time_max

    async def edit_event(self, message: str, pending_changes: dict = None) -> Tuple[str, dict, bool]:
        """Extract edit details and return confirmation"""
        user_prompt = f"User message: {message}"
        # Use LLM to extract date range
        time_min, time_max = await self.extract_date_range_from_message(message)
        # Expand the window by 24 hours on either side
        from datetime import datetime, timedelta
        def parse_iso(dt_str):
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except Exception:
                return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        dt_min = parse_iso(time_min) - timedelta(hours=24)
        dt_max = parse_iso(time_max) + timedelta(hours=24)
        time_min = dt_min.isoformat().replace("+00:00", "Z")
        time_max = dt_max.isoformat().replace("+00:00", "Z")
        print(f"[edit_event] Fetching events from {time_min} to {time_max}")
        events = self.schedule_service.summarize_events(time_min, time_max)
        event_list = [
            {
                "event_id": e["id"],
                "title": e.get("summary", "(No Title)"),
                "start_time": e["start"].get("dateTime", e["start"].get("date", "")),
                "end_time": e["end"].get("dateTime", e["end"].get("date", "")),
            }
            for e in events
        ]
        event_list_str = json.dumps(event_list, indent=2)
        system_prompt = f"""
            You are an assistant that helps users edit calendar events. Here is a list of upcoming events:

            {event_list_str}

            The user wants to edit an event. Match the user's request to the most likely event from the list above, even if the match is not exact. If the event title is similar or the date is within a day of the user's request, consider it a match. If there are multiple possible matches, pick the closest one.
            Reply ONLY with a valid JSON object, and nothing else. Do NOT include any natural language, explanations, or code block markers. Example:
            ```json
            {{
            "event_id": "abc123",
            "updates": {{"title": "New Title", "start_time": "2024-07-18T14:00:00Z"}},
            "missing_fields": [],
            "confirmation_message": "Are you sure you want to update 'Meeting with Rico' to the new details?"
            }}
            ```
            If you cannot find a matching event, reply with:
            ```json
            {{
            "event_id": null,
            "updates": {{}},
            "missing_fields": ["event_id"],
            "confirmation_message": "I couldn't find a matching event. Please specify the event you want to edit."
            }}
            ```
            """
        print("LLM system prompt for edit_event:\n", system_prompt)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if pending_changes:
            messages.append({
                "role": "assistant",
                "content": f"Current known details (JSON): {json.dumps(pending_changes)}"
            })
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.4
        )
        content = response.choices[0].message.content.strip()
        import re
        # Robust JSON cleaning (same as delete_event)
        content = clean_llm_json(content)
        print("LLM raw response for edit event:", content)
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
            print("Error parsing edit event JSON:", e)
            print("Raw content that failed to parse:", repr(content))
            return f"Sorry, I couldn't parse the edit details. Could you please provide the update information again?", None, False

    async def delete_event(self, message: str, pending_changes: dict = None) -> Tuple[str, dict, bool]:
        """Extract delete details and return confirmation"""

        user_prompt = f"User message: {message}"

        # Use LLM to extract date range
        time_min, time_max = await self.extract_date_range_from_message(message)
        # Expand the window by 24 hours on either side
        from datetime import datetime, timedelta
        def parse_iso(dt_str):
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except Exception:
                return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        dt_min = parse_iso(time_min) - timedelta(hours=24)
        dt_max = parse_iso(time_max) + timedelta(hours=24)
        time_min = dt_min.isoformat().replace("+00:00", "Z")
        time_max = dt_max.isoformat().replace("+00:00", "Z")
        print(f"[delete_event] Fetching events from {time_min} to {time_max}")
        events = self.schedule_service.summarize_events(time_min, time_max)
        event_list = [
            {
                "event_id": e["id"],
                "title": e.get("summary", "(No Title)"),
                "start_time": e["start"].get("dateTime", e["start"].get("date", "")),
                "end_time": e["end"].get("dateTime", e["end"].get("date", "")),
            }
            for e in events
        ]
        event_list_str = json.dumps(event_list, indent=2)
        system_prompt = f"""
            You are an assistant that helps users delete calendar events. Here is a list of upcoming events:

            {event_list_str}

            The user wants to delete an event. Match the user's request to the most likely event from the list above, even if the match is not exact. If the event title is similar or the date is within a day of the user's request, consider it a match. If there are multiple possible matches, pick the closest one.
            Reply ONLY with a valid JSON object, and nothing else. Do NOT include any natural language, explanations, or code block markers. Example:
            ```json
            {{
            "event_id": "abc123",
            "confirmation_message": "Are you sure you want to delete 'Meeting with Rico' on 2024-07-18 at 2:00pm?"
            }}
            ```
            If you cannot find a matching event, reply with:
            ```json
            {{
            "event_id": null,
            "confirmation_message": "I couldn't find a matching event. Please specify the event you want to delete."
            }}
            ```
            """
        print("LLM system prompt for delete_event:\n", system_prompt)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if pending_changes:
            messages.append({
                "role": "assistant",
                "content": f"Current known details (JSON): {json.dumps(pending_changes)}"
            })
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.4
        )
        content = response.choices[0].message.content.strip()
        import re
        # Remove code block markers if present
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        content = content.strip()
        print("LLM raw response for delete event:", content)
        try:
            data = json.loads(content)
            data["type"] = "schedule_delete"
            missing_fields = data.get("missing_fields", [])
            show_accept_deny = len(missing_fields) == 0
            confirmation_message = data["confirmation_message"]
            details = format_event_details(data)
            if details:
                confirmation_message += f"\n\n---\n**📋 Event to Delete:**\n{details}\n---"
            return confirmation_message, data, show_accept_deny
        except Exception as e:
            print("Error parsing delete event JSON:", e)
            print("Raw content that failed to parse:", repr(content))
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
            model="gpt-4",
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
                model="gpt-4",
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