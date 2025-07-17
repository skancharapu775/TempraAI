from fastapi import APIRouter, Depends, HTTPException, Request, Cookie, Header
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from firebase import db
from firebase_admin import auth as firebase_auth
import json
router = APIRouter()

SECRET = "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"
CLIENT_ID = "1090386684531-io9ttj5vpiaj6td376v2vs8t3htknvnn.apps.googleusercontent.com"
ALGORITHM = "HS256"

class GoogleToken(BaseModel):
    token: str

# Helpers
def get_google_creds(email: str):
    doc = db.collection("users").document(email).get()
    data = doc.to_dict()
    creds = Credentials(
        token=data["access_token"],
        refresh_token=data["refresh_token"],
        client_id=CLIENT_ID,
        client_secret=SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    if creds.expired:
        creds.refresh(Request())
        # update Firestore
        db.collection("users").document(email).update({
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "expires_at": creds.expiry.isoformat()
        })
    return creds

# Routes



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

@router.post("/auth/firebase")
def firebase_login(data: dict):
    id_token = data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="Missing ID token")
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        email = decoded_token.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="No email in token")
        # Optionally, create user record in Firestore if not exists
        if not db.collection("users").document(email).get().exists:
            db.collection("users").document(email).set({})
        return create_token(email)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {e}")

@router.get("/me")
def get_user(
    session_token: str = Cookie(None),
    authorization: str = Header(None)
):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    elif session_token:
        token = session_token
    if not token:
        raise HTTPException(status_code=401, detail="No session token provided")
        return None
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return {"email": payload["sub"]}
    except JWTError as e:
        print("JWTError:", e)
        raise HTTPException(status_code=401, detail="Invalid session")


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
        scopes=["openid",
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/userinfo.email"],
        redirect_uri="http://localhost:8000/auth/callback"
    )
    flow.redirect_uri = "http://localhost:8000/auth/callback"
    # Add prompt=consent to force the consent screen
    flow.authorization_url = lambda **kwargs: flow.client_config["web"]["auth_uri"] + "?" + "&".join([
        f"client_id={CLIENT_ID}",
        f"redirect_uri=http://localhost:8000/auth/callback",
        f"response_type=code",
        f"scope={' '.join(flow.scopes)}",
        f"prompt=consent",
        "access_type=offline"
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
    redirect.set_cookie(
    key="session_token",
    value=session_token,
    httponly=False,
    secure=False,  # True in production
    samesite="Lax"
    )
    redirect.set_cookie(
    key="email",
    value=email,
    httponly=False,
    secure=False,  # True in production
    samesite="Lax"
    )

    print(creds.token)
    print(email)
    db.collection("users").document(email).set({
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expires_at": creds.expiry.isoformat(),
    })
    return redirect

def create_token(email: str):
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=2)
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    return {"access_token": token}