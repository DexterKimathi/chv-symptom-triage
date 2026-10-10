from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import DUMMY_HASH, create_access_token, verify_password
from app.db import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.phone == body.phone))
    if user is None or not user.is_active:
        # Do the same amount of work as a real password check. Without this an unknown
        # number is rejected instantly and a registered one after ~0.3 s of bcrypt, which
        # gives the registered numbers away by timing.
        verify_password(body.password, DUMMY_HASH)
    # Same message whether the phone or the password is wrong, so the endpoint does not
    # reveal which phone numbers are registered.
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect phone or password")
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        role=user.role, name=user.name, area=user.area,
    )
