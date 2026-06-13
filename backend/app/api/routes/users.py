"""User profile route."""
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    return {
        "id": current_user["_id"],
        "email": current_user["email"],
        "username": current_user["username"],
        "created_at": current_user.get("created_at"),
    }
