"""FastAPI dependencies — authentication."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.routes.auth import decode_access_token
from app.db.mongodb import get_user_by_id

_bearer = HTTPBearer()
_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise _UNAUTHORIZED
    user = await get_user_by_id(user_id)
    if not user:
        raise _UNAUTHORIZED
    return user
