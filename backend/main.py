from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, List
from auth import router as auth_router
from format import *
from emails import create_email_handler
import json
import os
from auth import get_google_creds
import base64
from datetime import datetime, date
import tzlocal
from scheduling import create_schedule_handler
from todo import create_todo_handler
from goals import create_goals_handler

app = FastAPI(title="TempraAI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # or your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/auth")

class ProcessMessageRequest(BaseModel):
    message: str
    session_id: str
    conversation_history: Optional[List[dict]] = None
    current_intent: Optional[str] = None
    pending_changes: Optional[dict] = None
    email: str

class ProcessMessageResponse(BaseModel):
    reply: str
    pendingChanges: Optional[dict] = None
    intent: Optional[str] = None
    showAcceptDeny: bool = False

# Request/Response Models for change actions
class ChangeActionRequest(BaseModel):
    action: str  # "accept" or "deny"
    session_id: str
    email: str
    change_details: dict  # The pending changes being acted upon
    conversation_history: Optional[List[dict]] = None

class ChangeActionResponse(BaseModel):
    success: bool
    message: str
    intent: Optional[str] = None

load_dotenv()

# Initialize OpenAI client
def create_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)

# Helper functions for process-message endpoint

async def classify_intent_for_message(client, message: str, conversation_history: List[dict] = None) -> str:
    """Classify the intent of a user message"""
    role = '''
        Classify the user's intent into one of these categories: "Schedule", "Remind", "Email", "Todo", "Goal", "General".
        
        - "Schedule": User wants to schedule a meeting, appointment, or event
        - "Remind": User wants to set a reminder or create a todo
        - "Email": User wants to send, draft, or compose an email
        - "Todo": An item to be added, removed, or deleted from the todo list
        - "Goal": User wants to set, plan, or break down a goal
        - "General": General conversation, questions, or other topics
        
        Return ONLY ONE WORD from the choices above.
    '''
    messages = [{"role": "system", "content": role}]
    if conversation_history:
        filtered_history = [
            msg for msg in conversation_history
            if msg.get("content") is not None and msg.get("content").strip() != ""
        ]
        messages.extend(filtered_history)
    messages.append({"role": "user", "content": message})
    
    print(f"DEBUG: Classifying intent for message: '{message}'")
    print(f"DEBUG: Messages sent to LLM: {messages}")
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=20,
        temperature=0.3
    )
    intent = response.choices[0].message.content.strip()
    print(f"DEBUG: LLM response: '{response.choices[0].message.content}'")
    print(f"New intent classified: {intent}")
    return intent

async def check_intent_continuation(client, current_intent: str, message: str, conversation_history: List[dict] = None) -> bool:
    """Check if user wants to continue current intent or switch topics"""
    system_prompt = f"""
        You are managing a smart assistant's conversation. The current active task/intent is: {current_intent}.

        Your job is to determine if the user's message continues working on this current task or if they want to switch to a different topic.

        Available intents:
        - "Schedule": Scheduling meetings, appointments, or events. For any scheduling related activities, remember to use ISO-8601
        - "Remind": Setting reminders or creating todos
        - "Email": Sending, drafting, or composing emails
        - "Todo": An item to be added, removed, or deleted from the todo list
        - "Goal": Setting, planning, or breaking down a goal
        - "General": General conversation, questions, or other topics

        IMPORTANT: If the user mentions SCHEDULING, REMINDERS, EMAILS, TODOS, or GOALS while in general intent, they are switching topics and you should respond "EXIT".

        If the user's message:
        - Continues providing information for the current task → respond "CONTINUE"
        - Asks to do something different or changes topic → respond "EXIT"
        - Important: Mentions scheduling, reminders, emails, todos, or goals while in General → respond "EXIT"
        - Is unclear or could go either way → respond "EXIT" (default to switching)

        Respond with ONLY "CONTINUE" or "EXIT".
        """

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add recent conversation context (last 3 messages to avoid confusion)
    if conversation_history:
        recent_history = conversation_history[-3:]  # Only last 3 messages
        filtered_history = [
            msg for msg in recent_history
            if msg.get("content") is not None and msg.get("content").strip() != ""
        ]
        messages.extend(filtered_history)
    
    messages.append({"role": "user", "content": message})
    
    print(f"DEBUG: Checking intent continuation for '{current_intent}' with message: '{message}'")
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        max_tokens=10,
        temperature=0
    )
    decision = response.choices[0].message.content.strip().upper()
    print(f"DEBUG: Intent continuation decision: {decision}")
    return decision == "CONTINUE"

async def handle_email_intent(client, message: str, pending_changes: dict = None, access_token: str = None, refresh_token: str = None) -> tuple[str, dict, bool]:
    """Handle email intent and return (reply, pending_changes, show_accept_deny)"""
    # Create email handler (default to Gmail, can be made configurable)
    email_handler = create_email_handler(
        provider="gmail",
        access_token=access_token,
        refresh_token=refresh_token,
        client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
        client_secret="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"
    )
    
    # Use the new email handler to process the message
    return await email_handler.handle_email_intent(message, pending_changes)

async def handle_remind_intent(client, message: str, pending_changes: dict = None) -> tuple[str, dict, bool]:
    """Handle reminder intent and return (reply, pending_changes, show_accept_deny)"""
    system_prompt = """
        You are an assistant that extracts reminder details from the user's inputs. Your job is to guess title, description, due_date, due_time, priority, category, and recurrence pattern from natural text.

        REQUIRED FIELDS: title, due_date, due_time, recurrence
        OPTIONAL FIELDS: description, priority, category

        RECURRENCE PATTERNS:
        - "once": One-time reminder (default)
        - "daily": Every day
        - "weekly": Every week on the same day
        - "monthly": Every month on the same date
        - "yearly": Every year on the same date
        - "every_other_day": Every other day
        - "weekdays": Monday through Friday
        - "weekends": Saturday and Sunday
        - "custom": Custom pattern (specify in description)

        Reply *only* with valid JSON. Example:
        {
        "title": "...",
        "description": "...",   // optional
        "due_date": "...",      // date in YYYY-MM-DD format
        "due_time": "...",      // time in HH:MM format
        "priority": "...",      // optional: "high", "medium", "low"
        "category": "...",      // optional: "work", "personal", "health", etc.
        "recurrence": "...",    // optional: "once", "daily", "weekly", "monthly", "yearly", "every_other_day", "weekdays", "weekends", "custom"
        "missing_fields": ["title", ...], // only include required fields that are missing
        "confirmation_message": "..."
        }

        If there are any current known details, merge them with the JSON that you will return.
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

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.4
    )

    content = response.choices[0].message.content.strip()
    
    try:
        data = json.loads(content)
        data["type"] = "reminder"
        print(f"Reminder proposal: {data}")
        
        # Check if all required fields are present
        missing_fields = data.get("missing_fields", [])
        show_accept_deny = len(missing_fields) == 0
        
        # Format current details for display
        current_details = format_reminder_details(data)
        confirmation_message = data["confirmation_message"]
        
        if current_details:
            confirmation_message += f"\n\n---\n**📋 Current Details:**\n{current_details}\n---"
        
        return confirmation_message, data, show_accept_deny
    except Exception as e:
        return f"Sorry, I couldn't parse the reminder details. Could you please provide the reminder information again?", None, False

async def handle_schedule_intent(client, message: str, pending_changes: dict = None, access_token: str = None, refresh_token: str = None) -> tuple[str, dict, bool]:
    """Delegate scheduling intent to scheduling.py handler, just like handle_email_intent."""
    schedule_handler = create_schedule_handler(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
        client_secret="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"
    )
    return await schedule_handler.handle_schedule_intent(message, pending_changes)

async def handle_general_chat(client, message: str, conversation_history: List[dict] = None) -> str:
    """Handle general chat and return reply"""
    messages = [{"role": "system", "content": "You are a helpful life secretary, but be comedic (not cringe) like TARS from the movie Interstellar."}]
    
    if conversation_history:
        filtered_history = [
            msg for msg in conversation_history
            if msg.get("content") is not None and msg.get("content").strip() != ""
        ]
        messages.extend(filtered_history)
    
    messages.append({"role": "user", "content": message})
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=300,
        temperature=0.7
    )
    
    return response.choices[0].message.content.strip()

async def handle_todo_intent(client, message: str, pending_changes: dict = None) -> tuple[str, dict, bool]:
    """Delegate todo intent to todo.py handler."""
    todo_handler = create_todo_handler()
    return await todo_handler.handle_todo_intent(message, pending_changes)

async def handle_goal_intent(client, message: str, pending_changes: dict = None) -> tuple[str, dict, bool]:
    """Delegate goal intent to goals.py handler."""
    goals_handler = create_goals_handler()
    return await goals_handler.handle_goal_intent(message)

@app.post("/process-message", response_model=ProcessMessageResponse)
async def process_message(request: ProcessMessageRequest = Body(...)):
    client = create_openai_client()
    # 1. Determine intent
    intent = request.current_intent
    show_accept_deny = False
    pending_changes = None
    reply = ""

    # If there's a current intent, check if user is continuing or switching
    if intent:
        # Use follow-up-intent logic to check if user continues current intent
        continue_current = await check_intent_continuation(
            client, intent, request.message, request.conversation_history
        )
        
        if not continue_current:
            print(f"Intent change detected: {intent} -> new intent")
            intent = None
            pending_changes = None  # Reset pending changes when switching intents

    # If no current intent (or user switched), classify new intent
    if not intent:
        intent = await classify_intent_for_message(
            client, request.message, request.conversation_history
        )

    # 2. Route to appropriate handler
    if intent == "Schedule":
        creds = get_google_creds(request.email)
        reply, pending_changes, show_accept_deny = await handle_schedule_intent(
            client, request.message, request.pending_changes, creds.token, creds.refresh_token
        )
    elif intent == "Email":
        creds = get_google_creds(request.email)
        reply, pending_changes, show_accept_deny = await handle_email_intent(
            client, request.message, request.pending_changes, creds.token, creds.refresh_token
        )
    elif intent == "Remind":
        reply, pending_changes, show_accept_deny = await handle_remind_intent(
            client, request.message, request.pending_changes
        )
    elif intent == "Todo":
        reply, pending_changes, show_accept_deny = await handle_todo_intent(
            client, request.message, request.pending_changes
        )
    elif intent == "General":
        reply = await handle_general_chat(
            client, request.message, request.conversation_history
        )
    elif intent == "Goal":
        reply, pending_changes, show_accept_deny = await handle_goal_intent(
            client, request.message, request.pending_changes
        )
    else:
        # Default to general chat for unhandled intents
        reply = await handle_general_chat(
            client, request.message, request.conversation_history
        )

    return ProcessMessageResponse(
        reply=reply,
        pendingChanges=pending_changes,
        intent=intent,
        showAcceptDeny=show_accept_deny
    )

@app.post("/handle-change-action", response_model=ChangeActionResponse)
async def handle_change_action(request: ChangeActionRequest):
    print("Received /handle-change-action request:", request)
    client = create_openai_client()
    try: 
        credentials = get_google_creds(request.email)
        print(credentials)
    except:
        print("cldn't get crednetials")
        return ChangeActionResponse(
                success=False,
                message="Please try logging in again and retry.",
                intent="General"  # Switch back to general conversation
            )
    
    if request.action.lower() == "accept":
        # Handle acceptance
        if request.change_details.get("type") in ["schedule_add", "schedule_edit", "schedule_delete"]:
            schedule_type = request.change_details.get("type")
            schedule_handler = create_schedule_handler(
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
                client_secret="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"
            )
            if schedule_type == "schedule_add":
                # Actually add the event to Google Calendar
                data = request.change_details
                event = {
                    'summary': data.get('title'),
                    'start': {
                        'dateTime': data.get('start_time'),
                        'timeZone': 'America/New_York',
                    },
                    'end': {
                        'dateTime': data.get('end_time'),
                        'timeZone': 'America/New_York',
                    },
                }
                if data.get('attendees'):
                    event['attendees'] = [{'email': email} for email in data['attendees']]
                created_event = schedule_handler.schedule_service.client.events().insert(calendarId='primary', body=event).execute()
                message = f"Perfect! I've successfully scheduled '{data.get('title')}' from {data.get('start_time')} to {data.get('end_time')}. Here's the link {created_event.get('htmlLink')}. Is there anything else I can help you with?"
                return ChangeActionResponse(
                    success=True,
                    message=message,
                    intent="General"
                )
            elif schedule_type == "schedule_edit":
                # Actually edit the event in Google Calendar
                data = request.change_details
                event_id = data.get('event_id')
                updates = data.get('updates', {})
                event = schedule_handler.schedule_service.client.events().get(calendarId='primary', eventId=event_id).execute()
                event.update(updates)
                updated_event = schedule_handler.schedule_service.client.events().update(calendarId='primary', eventId=event_id, body=event).execute()
                message = f"Perfect! I've updated your event '{updated_event.get('summary')}'. Is there anything else I can help you with?"
                return ChangeActionResponse(
                    success=True,
                    message=message,
                    intent="General"
                )
            elif schedule_type == "schedule_delete":
                # Actually delete the event in Google Calendar
                data = request.change_details
                event_id = data.get('event_id')
                event = schedule_handler.schedule_service.client.events().get(calendarId='primary', eventId=event_id).execute()
                schedule_handler.schedule_service.client.events().delete(calendarId='primary', eventId=event_id).execute()
                message = f"Perfect! I've deleted your event '{event.get('summary')}'. Is there anything else I can help you with?"
                return ChangeActionResponse(
                    success=True,
                    message=message,
                    intent="General"
                )
        elif request.change_details.get("type") in ["email", "email_compose", "email_schedule", "email_organize"]:
            email_type = request.change_details.get("type")
            if email_type == "email_compose" or email_type == "email":
                # Handle composing a new email (draft, send, etc.)
                subject = request.change_details.get("subject", "Email")
                recipient = request.change_details.get("recipient", "recipient")
                body = request.change_details.get("body", "")
                attachments = request.change_details.get("attachments", [])
                folder = request.change_details.get("folder", "")
                email_handler = create_email_handler(
                    provider="gmail",
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
                    client_secret="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"
                )
                recipient_info = f" to {recipient}" if recipient else ""
                attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""
                folder_info = f" in folder '{folder}'" if folder else ""
                message = f"Perfect! I've successfully created an email draft with subject '{subject}'{recipient_info}{folder_info}{attachment_info}. The email has been saved as a draft. Is there anything else I can help you with?"
                return ChangeActionResponse(
                    success=True,
                    message=message,
                    intent="General"
                )
            elif email_type == "email_schedule":
                # Handle scheduling an email to be sent later
                subject = request.change_details.get("subject", "Email")
                recipient = request.change_details.get("recipient", "recipient")
                folder = request.change_details.get("folder", "")
                scheduled_time = request.change_details.get("scheduled_time", "")
                email_handler = create_email_handler(
                    provider="gmail",
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
                    client_secret="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"
                )
                recipient_info = f" to {recipient}" if recipient else ""
                folder_info = f" in folder '{folder}'" if folder else ""
                schedule_info = f" (scheduled for {scheduled_time})" if scheduled_time else ""
                message = f"Perfect! I've scheduled an email with subject '{subject}'{recipient_info}{folder_info}{schedule_info}. Is there anything else I can help you with?"
                return ChangeActionResponse(
                    success=True,
                    message=message,
                    intent="General"
                )
            elif email_type == "email_organize":
                # Handle organizing emails into folders/labels
                created_folders = request.change_details.get("created_folders", [])
                existing_folders = request.change_details.get("existing_folders", [])
                criteria = request.change_details.get("criteria", "organize emails")
                email_count = request.change_details.get("email_count", 25)
                email_handler = create_email_handler(
                    provider="gmail",
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    client_id="1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com",
                    client_secret="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"
                )
                created_folder_names = []
                if created_folders:
                    for folder_name in created_folders:
                        try:
                            folder_id = await email_handler.email_service.create_folder(folder_name)
                            created_folder_names.append(folder_name)
                        except Exception as e:
                            print(f"Error creating folder {folder_name}: {e}")
                folder_info = ""
                if created_folder_names:
                    folder_info = f"Created folders: {', '.join(created_folder_names)}. "
                folder_info += f"Using existing folders: {', '.join(existing_folders)}"
                message = f"Perfect! I've successfully organized your emails based on '{criteria}'. {folder_info}. Approximately {email_count} emails were processed. Is there anything else I can help you with?"
                return ChangeActionResponse(
                    success=True,
                    message=message,
                    intent="General"
                )
        elif request.change_details.get("type") == "reminder":
            # Extract reminder details
            title = request.change_details.get("title", "Reminder")
            description = request.change_details.get("description", "")
            due_date = request.change_details.get("due_date", "")
            due_time = request.change_details.get("due_time", "")
            priority = request.change_details.get("priority", "")
            category = request.change_details.get("category", "")
            recurrence = request.change_details.get("recurrence", "once")
            
            # Generate confirmation message
            time_info = ""
            if due_date and due_time:
                time_info = f" due on {due_date} at {due_time}"
            elif due_date:
                time_info = f" due on {due_date}"
            elif due_time:
                time_info = f" due at {due_time}"
            
            priority_info = ""
            if priority:
                priority_info = f" (Priority: {priority})"
            
            category_info = ""
            if category:
                category_info = f" in category '{category}'"
            
            recurrence_info = ""
            if recurrence and recurrence != "once":
                recurrence_info = f" (Recurring: {recurrence})"
            
            message = f"Perfect! I've successfully created a reminder '{title}'{time_info}{recurrence_info}{priority_info}{category_info}. Is there anything else I can help you with?"
            
            return ChangeActionResponse(
                success=True,
                message=message,
                intent="General"  # Switch back to general conversation
            )
        elif request.change_details.get("type") == "goal":
            # On accept, generate the week plan and return it
            goals_handler = create_goals_handler()
            goal = request.change_details.get("goal")
            duration = request.change_details.get("duration")
            calendar = request.change_details.get("calendar")
            plan, plan_text = await goals_handler.generate_week_plan(goal, duration, calendar)
            message = f"Goal plan accepted and saved!\n\nHere is your week-by-week plan:\n\n{plan_text}"
            return ChangeActionResponse(
                success=True,
                message=message,
                intent="General"
            )
        else:
            # Handle other change types
            return ChangeActionResponse(
                success=True,
                message="Great! I've confirmed your request. Is there anything else I can help you with?",
                intent="General"
            )
    
    elif request.action.lower() == "deny":
        # Handle denial
        return ChangeActionResponse(
            success=True,
            message="No problem! Let me know if you'd like to try something else or if there's anything else I can help you with.",
            intent="General"  # Switch back to general conversation
        )
    
    else:
        # Invalid action
        return ChangeActionResponse(
            success=False,
            message="Invalid action. Please use 'accept' or 'deny'.",
            intent=None
        )

# Health Check Endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "TempraAI API is running"}

# Root Endpoint
@app.get("/")
async def root():
    return {
        "message": "TempraAI API",
        "endpoints": {
            "process_message": "POST /process-message",
            "handle_change_action": "POST /handle-change-action",
            "health": "GET /health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 