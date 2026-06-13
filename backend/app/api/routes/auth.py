"""Auth routes — email/password register & login, Google OAuth."""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=40)
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    login: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── JWT helpers (kept local to avoid circular import) ─────────────────────────

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain[:72], hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    from app.db.mongodb import create_user, get_user_by_email, get_user_by_username

    if await get_user_by_email(request.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists")
    if await get_user_by_username(request.username):
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is already taken")

    user_id = await create_user(
        email=request.email,
        username=request.username,
        hashed_password=hash_password(request.password),
    )
    return TokenResponse(access_token=create_access_token(user_id))


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    from app.db.mongodb import get_user_by_email, get_user_by_username

    user = await get_user_by_email(request.login) or await get_user_by_username(request.login)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No account found with that email or username")
    if not user.get("hashed_password"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account uses Google login")
    if not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password")

    return TokenResponse(access_token=create_access_token(user["_id"]))


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google")
def google_login():
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(500, "Google OAuth is not configured")
    params = "&".join([
        f"client_id={settings.GOOGLE_CLIENT_ID}",
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}",
        "response_type=code",
        "scope=openid email profile",
        "access_type=online",
    ])
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/google/callback")
async def google_callback(code: Optional[str] = None, error: Optional[str] = None):
    if error or not code:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=oauth_cancelled")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })

    if token_resp.status_code != 200:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=oauth_failed")

    g_token = token_resp.json().get("access_token")
    async with httpx.AsyncClient() as client:
        profile_resp = await client.get(GOOGLE_USER_URL, headers={"Authorization": f"Bearer {g_token}"})

    if profile_resp.status_code != 200:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=oauth_failed")

    profile = profile_resp.json()
    google_id = profile.get("sub")
    email = profile.get("email", "").lower().strip()
    name = profile.get("name") or email.split("@")[0]

    if not google_id or not email:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=oauth_failed")

    user = await _get_or_create_google_user(google_id, email, name)
    token = create_access_token(user["_id"])
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={token}")


async def _get_or_create_google_user(google_id: str, email: str, name: str) -> dict:
    from app.db.mongodb import (
        create_user, get_user_by_email, get_user_by_google_id,
        get_user_by_id, link_google_id,
    )

    user = await get_user_by_google_id(google_id)
    if user:
        return user

    user = await get_user_by_email(email)
    if user:
        await link_google_id(user["_id"], google_id)
        return {**user, "google_id": google_id}

    base = name.replace(" ", "").lower()[:30]
    username = base
    for suffix in range(1, 11):
        try:
            uid = await create_user(email=email, username=username, google_id=google_id)
            return await get_user_by_id(uid)
        except Exception:
            username = f"{base}{suffix}"

    raise HTTPException(500, "Could not create user account")
