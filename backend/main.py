from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, List
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

# Request/Response Models
class IntentRequest(BaseModel):
    message: str
    conversation_history: Optional[List[dict]] = None  # Add this

class IntentResponse(BaseModel):
    intent: str
    message: str

class ScheduleRequest(BaseModel):
    message: str
    prior_state: Optional[dict] = None

class ScheduleResponse(BaseModel):
    title: str
    start_time: str
    end_time: str
    attendees: list[str] = []

class EmailRequest(BaseModel):
    message: str
    subject: str = "Draft Email"
    to: str = ""

class EmailResponse(BaseModel):
    status: str
    message: str
    draft_id: str = None

class ScheduleProposal(BaseModel):
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    attendees: List[str] = []
    missing_fields: List[str] = []
    confirmation_message: str
    type: str = "schedule"

load_dotenv()

# Initialize OpenAI client
def create_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)


@app.post("/propose-schedule", response_model=ScheduleProposal)
async def propose_schedule(request: ScheduleRequest):
    client = create_openai_client()

    system_prompt = """
You are an assistant that extracts scheduling details from user input. Your job is to guess title, start_time, end_time, and attendees from natural text. 
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

    user_prompt = f"User message: {request.message}"
    messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    if request.prior_state:
        messages.append(
        {
            "role": "assistant",
            "content": f"Current known details (JSON): {json.dumps(request.prior_state)}"
        })

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.4
    )

    content = response.choices[0].message.content.strip()

    try:
        data = json.loads(content) 
        # Add type field for frontend change tracking
        data["type"] = "schedule"
        print(data)
        return ScheduleProposal(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse schedule proposal: {e}")


# Intent Classification Endpoint
@app.post("/classify-intent", response_model=IntentResponse)
async def classify_intent(request: IntentRequest):
    try:
        client = create_openai_client()
        
        role = '''
            Based on the intent of the message return one of these: "Schedule", "Remind", "Email", "General".
            Specifically ONLY ONE WORD RESPONSES FROM THESE CHOICES. 
            If it is general, just answer it like a human would. 
            If it is a task that is not schedule, remind, or email, and is instead a task to be performed with another third party
            say that it is not currently possible. 
        '''
        
        # Build messages array with conversation history
        messages = [{"role": "system", "content": role}]
        
        # Add conversation history if provided (filter out messages with null content)
        if request.conversation_history:
            filtered_history = [
                msg for msg in request.conversation_history 
                if msg.get("content") is not None and msg.get("content").strip() != ""
            ]
            messages.extend(filtered_history)
        
        # Add current message
        messages.append({"role": "user", "content": request.message})
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=20,
            temperature=0.3
        )
        
        intent = response.choices[0].message.content.strip()
        
        return IntentResponse(intent=intent, message=request.message)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error classifying intent: {str(e)}")


class FollowUpRequest(BaseModel):
    current_intent: str
    message: str
    conversation_history: Optional[List[dict]] = None

@app.post("/follow-up-intent")
async def follow_up_intent(request: FollowUpRequest):
    client = create_openai_client()
    
    prompt = f"""
You are managing a smart assistant's conversation. The current task is: {request.current_intent}.
Determine whether the user's message continues this task or changes topics.

User message: "{request.message}"

Reply only with "CONTINUE" or "EXIT".
    """

    # Build messages array with conversation history
    messages = [{"role": "system", "content": "Decide if a user is continuing their current intent or not."}]
    
    # Add conversation history if provided (filter out messages with null content)
    if request.conversation_history:
        filtered_history = [
            msg for msg in request.conversation_history 
            if msg.get("content") is not None and msg.get("content").strip() != ""
        ]
        messages.extend(filtered_history)
    
    # Add current message
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=1,
        temperature=0
    )

    decision = response.choices[0].message.content.strip().upper()
    return { "decision": decision }

# endpoint for scheduling.
@app.post("/parse-schedule", response_model=ScheduleResponse)
async def parse_schedule(request: ScheduleRequest):
    client = create_openai_client()

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": """
            You're an assistant that extracts meeting details from natural language and returns a JSON with title, start_time, end_time, and attendees (optional emails). Use ISO format for dates.
            """},
            {"role": "user", "content": request.message}
        ],
        temperature=0.3
    )

    # You'll parse the structured text into a dict manually for now
    content = response.choices[0].message.content.strip()

    try:
        # Use eval safely or switch to json.loads() if GPT outputs JSON
        parsed = eval(content)
        return ScheduleResponse(**parsed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not parse GPT response: {e}")



# Chat Endpoint for General Conversation
class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[dict]] = None

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        client = create_openai_client()
        
        # Build messages array with conversation history
        messages = [{"role": "system", "content": "You are a helpful AI assistant. Be conversational and friendly."}]
        
        # Add conversation history if provided (filter out messages with null content)
        if request.conversation_history:
            filtered_history = [
                msg for msg in request.conversation_history 
                if msg.get("content") is not None and msg.get("content").strip() != ""
            ]
            messages.extend(filtered_history)
        
        # Add current message
        messages.append({"role": "user", "content": request.message})
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=300,
            temperature=0.7
        )
        
        response_text = response.choices[0].message.content.strip()
        
        return ChatResponse(response=response_text)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in chat: {str(e)}")

# Email Drafting Endpoint
@app.post("/draft-email", response_model=EmailResponse)
async def draft_email(request: EmailRequest):
    try:
        client = create_openai_client()
        
        # Generate email body using OpenAI
        prompt = f"""
        Draft an email based on the following user request. Only output the email body, do not include any headers or signatures.
        User request: {request.message}
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
        
        email_body = response.choices[0].message.content.strip()
        
        # Create Gmail draft
        service = gmail_authenticate()
        message = MIMEText(email_body)
        message['to'] = request.to
        message['subject'] = request.subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = service.users().drafts().create(
            userId='me',
            body={'message': {'raw': raw}}
        ).execute()
        
        return EmailResponse(
            status="success",
            message="Draft email created successfully",
            draft_id=draft['id']
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating email draft: {str(e)}")

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
            "classify_intent": "POST /classify-intent",
            "draft_email": "POST /draft-email",
            "health": "GET /health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 