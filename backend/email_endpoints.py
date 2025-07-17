from fastapi import APIRouter, Depends, HTTPException, Request, Cookie, Header, Body
from fastapi.responses import RedirectResponse
import yagmail

app = APIRouter

@app.post("/send-email-reminder")
async def send_email_reminder(data: dict = Body(...)):
    from_email = "ricochandra128@gmail.com"
    to_email = data["email"]
    title = data["title"]
    due_datetime = data["due_datetime"]
    description = data.get("description", "")

    yag = yagmail.SMTP(from_email, "your_app_password")
    yag.send(
        to=to_email,
        subject=f"Reminder: {title}",
        contents=f"This is your reminder for: '{title}' at {due_datetime}.\n\nDetails: {description}",
    )
    return {"status": "sent"}