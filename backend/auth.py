from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests 
router = APIRouter()

SECRET = "BaM6BJS3wgaijrWCBABGgLow2Z_klM9u1aaubxmPK9I"
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

def create_token(email: str):
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    return {"access_token": token}