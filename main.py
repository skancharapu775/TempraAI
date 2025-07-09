from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os
from emails import create_gmail_draft, gmail_authenticate
from email.mime.text import MIMEText
import base64

app = FastAPI(title="TempraAI API", version="1.0.0")

# Request/Response Models
class IntentRequest(BaseModel):
    message: str

class IntentResponse(BaseModel):
    intent: str
    message: str

class EmailRequest(BaseModel):
    message: str
    subject: str = "Draft Email"
    to: str = ""

class EmailResponse(BaseModel):
    status: str
    message: str
    draft_id: str = None

# Initialize OpenAI client
def create_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)

# Intent Classification Endpoint
@app.post("/classify-intent", response_model=IntentResponse)
async def classify_intent(request: IntentRequest):
    try:
        client = create_openai_client()
        
        role = '''
            Based on the intent of the message return one of these: "Schedule", "Remind", "Email", "General"
        '''
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": role},
                {"role": "user", "content": request.message}
            ],
            max_tokens=20,
            temperature=0.3
        )
        
        intent = response.choices[0].message.content.strip()
        
        return IntentResponse(intent=intent, message=request.message)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error classifying intent: {str(e)}")

# Email Drafting Endpoint
@app.post("/draft-email", response_model=EmailResponse)
async def draft_email_endpoint(request: EmailRequest):
    try:
        client = create_openai_client()
        
        # Generate email body using OpenAI
        prompt = f"""
        Draft a professional email based on the following user request. Only output the email body, do not include any headers or signatures.
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