import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from auth import create_access_token, hash_password, verify_password
from DATABASE import (
    create_user,
    get_user_by_email,
    get_user_by_google_id,
    link_google_id,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Config ────────────────────────────────────────────────────────────────────

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://localhost:5173")

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:    EmailStr
    username: str   = Field(..., min_length=3, max_length=40)
    password: str   = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str   = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"


# ── Email / password ──────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    if get_user_by_email(request.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        )

    user_id = create_user(
        email=request.email,
        username=request.username,
        hashed_password=hash_password(request.password),
    )
    return TokenResponse(access_token=create_access_token(user_id))


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    user = get_user_by_email(request.email)
    if not user or not user.get("hashed_password"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return TokenResponse(access_token=create_access_token(user["id"]))


# ── Google OAuth 2.0 ──────────────────────────────────────────────────────────

@router.get("/google")
def google_login():
    """Redirect the browser to Google's consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")

    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "online",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback")
async def google_callback(code: Optional[str] = None, error: Optional[str] = None):
    """
    Google redirects here with ?code=...
    We exchange it for the user's profile, create/find the user,
    then redirect the browser to the frontend with the JWT as a query param.
    """
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_cancelled")

    # Step 1: Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  GOOGLE_REDIRECT_URI,
            "grant_type":    "authorization_code",
        })

    if token_response.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_failed")

    google_access_token = token_response.json().get("access_token")

    # Step 2: Fetch user profile from Google
    async with httpx.AsyncClient() as client:
        profile_response = await client.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
        )

    if profile_response.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_failed")

    profile     = profile_response.json()
    google_id   = profile.get("sub")
    email       = profile.get("email", "").lower().strip()
    name        = profile.get("name") or email.split("@")[0]

    if not google_id or not email:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_failed")

    # Step 3: Find or create user
    user = _get_or_create_google_user(google_id, email, name)

    # Step 4: Issue our own JWT and redirect to frontend
    token = create_access_token(user["id"])
    return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={token}")


def _get_or_create_google_user(google_id: str, email: str, name: str) -> dict:
    """
    Resolution order:
    1. User already exists with this google_id → return them
    2. User exists with same email (registered via password) → link accounts
    3. No user found → create a new one
    """
    # 1. Returning Google user
    user = get_user_by_google_id(google_id)
    if user:
        return user

    # 2. Existing email/password account — link Google to it
    user = get_user_by_email(email)
    if user:
        link_google_id(user["id"], google_id)
        return {**user, "google_id": google_id}

    # 3. Brand new user
    # Ensure username is unique by appending google_id suffix if needed
    base_username = name.replace(" ", "").lower()[:30]
    username = base_username
    suffix = 1
    while True:
        existing = None
        try:
            user_id = create_user(
                email=email,
                username=username,
                google_id=google_id,
            )
            from DATABASE import get_user_by_id
            return get_user_by_id(user_id)
        except Exception:
            username = f"{base_username}{suffix}"
            suffix += 1
            if suffix > 10:
                raise HTTPException(status_code=500, detail="Could not create user account")