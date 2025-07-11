from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, List
from auth import router as auth_router
import json
import os
# from emails import create_gmail_draft, gmail_authenticate
# from email.mime.text import MIMEText
import base64

app = FastAPI(title="TempraAI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # or your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/auth")

# Request/Response Models
class ScheduleRequest(BaseModel):
    message: str
    prior_state: Optional[dict] = None

class ScheduleProposal(BaseModel):
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    attendees: List[str] = []
    missing_fields: List[str] = []
    confirmation_message: str
    type: str = "schedule"

class ProcessMessageRequest(BaseModel):
    message: str
    session_id: str
    conversation_history: Optional[List[dict]] = None
    current_intent: Optional[str] = None
    pending_changes: Optional[dict] = None

class ProcessMessageResponse(BaseModel):
    reply: str
    pendingChanges: Optional[dict] = None
    intent: Optional[str] = None
    showAcceptDeny: bool = False

# Request/Response Models for change actions
class ChangeActionRequest(BaseModel):
    action: str  # "accept" or "deny"
    session_id: str
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
        Classify the user's intent into one of these categories: "Schedule", "Remind", "Email", "General".
        
        - "Schedule": User wants to schedule a meeting, appointment, or event
        - "Remind": User wants to set a reminder or create a todo
        - "Email": User wants to send, draft, or compose an email
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
    prompt = f"""
You are managing a smart assistant's conversation. The current task is: {current_intent}.
Determine whether the user's message continues this task or changes topics.

IMPORTANT: If the user mentions scheduling, reminders, or emails, they are switching to a new intent, even if they were previously in general conversation.

User message: "{message}"

Reply only with "CONTINUE" or "EXIT".
    """
    messages = [{"role": "system", "content": "Decide if a user is continuing their current intent or not."}]
    if conversation_history:
        filtered_history = [
            msg for msg in conversation_history
            if msg.get("content") is not None and msg.get("content").strip() != ""
        ]
        messages.extend(filtered_history)
    messages.append({"role": "user", "content": prompt})
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=10,
        temperature=0
    )
    decision = response.choices[0].message.content.strip().upper()
    print(f"Intent continuation check: {decision}")
    return decision == "CONTINUE"

async def handle_schedule_intent(client, message: str, pending_changes: dict = None) -> tuple[str, dict, bool]:
    """Handle scheduling intent and return (reply, pending_changes, show_accept_deny)"""
    system_prompt = """
You are an assistant that extracts scheduling details from the user's last inputs. Your job is to guess title, start_time, end_time, and attendees from natural text. 
Then, list any missing or unclear fields and generate a polite confirmation message asking the user to confirm or correct.
Use ISO 8601 format for times.
Reply *only* with valid JSON. Example:
{
  "title": "...",
  "start_time": "...",   // ISO-8601
  "end_time": "...",     // ISO-8601 or null
  "attendees": ["email1", ...], OPTIONAL. Do not ask for it unless the user mentions to address other attendees.
  "missing_fields": ["start_time", ...],
  "confirmation_message": "..."
}
if there is any current known details, merge it with the JSON that you will return.
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
        model="gpt-4",
        messages=messages,
        temperature=0.4
    )

    content = response.choices[0].message.content.strip()
    
    try:
        data = json.loads(content)
        data["type"] = "schedule"
        print(f"Schedule proposal: {data}")
        return data["confirmation_message"], data, True
    except Exception as e:
        return f"Sorry, I couldn't parse the scheduling details. Could you please provide the meeting information again?", None, False

async def handle_general_chat(client, message: str, conversation_history: List[dict] = None) -> str:
    """Handle general chat and return reply"""
    messages = [{"role": "system", "content": "You are a helpful life secretary. Be open and friendly."}]
    
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
        reply, pending_changes, show_accept_deny = await handle_schedule_intent(
            client, request.message, request.pending_changes
        )
    elif intent == "General":
        reply = await handle_general_chat(
            client, request.message, request.conversation_history
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
    """Handle accept/deny actions for pending changes"""
    client = create_openai_client()
    
    if request.action.lower() == "accept":
        # Handle acceptance
        if request.change_details.get("type") == "schedule":
            # Extract schedule details
            title = request.change_details.get("title", "Meeting")
            start_time = request.change_details.get("start_time")
            end_time = request.change_details.get("end_time")
            attendees = request.change_details.get("attendees", [])
            
            # Generate confirmation message
            if start_time and end_time:
                time_info = f"from {start_time} to {end_time}"
            elif start_time:
                time_info = f"at {start_time}"
            else:
                time_info = "at the specified time"
            
            attendee_info = ""
            if attendees:
                attendee_info = f" with {', '.join(attendees)}"
            
            message = f"Perfect! I've successfully scheduled '{title}' {time_info}{attendee_info}. Is there anything else I can help you with?"
            
            return ChangeActionResponse(
                success=True,
                message=message,
                intent="General"  # Switch back to general conversation
            )
        else:
            # Handle other change types (reminders, emails, etc.)
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