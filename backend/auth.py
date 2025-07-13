from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests 
router = APIRouter()

SECRET = "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"
CLIENT_ID = "1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com"
ALGORITHM = "HS256"

class GoogleToken(BaseModel):
    token: str

@router.post("/google")
# db: Session = Depends(get_db)
def login_with_google(data: GoogleToken):
    token = data.token
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), CLIENT_ID)
        email = idinfo['email']
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token")

    # user = db.query(models.User).filter(models.User.email == email).first()
    # if not user:
    #     # new_user = models.User(email=email, hashed_password="", auth_provider="Google")
    #     try:
    #         db.add(new_user)
    #         db.commit()
    #         db.refresh(new_user)
    #     except Exception as e:
    #         print("❌ DB error:", e)
    #         raise HTTPException(status_code=500, detail="Server error")
    # # Return user's JWT
    return create_token(email)


@router.get("/callback")
def google_oauth_callback(request: Request, code: str):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": SECRET,
                "redirect_uris": ["http://localhost:8000/auth/callback"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=["openid", "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/gmail.modify"],
        redirect_uri="http://localhost:8000/auth/callback"
    )
    flow.redirect_uri = "http://localhost:8000/auth/callback"
    # Add prompt=consent to force the consent screen
    flow.authorization_url = lambda **kwargs: flow.client_config["web"]["auth_uri"] + "?" + "&".join([
        f"client_id={CLIENT_ID}",
        f"redirect_uri=http://localhost:8000/auth/callback",
        f"response_type=code",
        f"scope={' '.join(flow.scopes)}",
        f"prompt=consent"
    ])
    flow.fetch_token(code=code)
    creds = flow.credentials
    idinfo = id_token.verify_oauth2_token(creds.id_token, google_requests.Request(), CLIENT_ID)
    if not creds.id_token:
        raise HTTPException(status_code=400, detail="Missing ID token. Add prompt=consent to your OAuth URL.")
    email = idinfo['email']
    session_token = jwt.encode({
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=2)
    }, SECRET, algorithm="HS256")
    
    redirect = RedirectResponse("http://localhost:5173/")
    redirect.set_cookie(key="access_token", value=creds.token, httponly=False)
    redirect.set_cookie(key="refresh_token", value=creds.refresh_token, httponly=False)
    redirect.set_cookie(key="session_token", value=session_token, httponly=False)
    return redirect

def create_token(email: str):
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=2)
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    return {"access_token": token}