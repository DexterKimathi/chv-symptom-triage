from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db import get_db
from app.deps import require_admin
from app.models import User
from app.schemas import CreateUserRequest, UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> User:
    duplicate = HTTPException(status.HTTP_409_CONFLICT, detail="A user with this phone already exists")
    if db.scalar(select(User).where(User.phone == body.phone)):
        raise duplicate
    user = User(
        name=body.name, phone=body.phone, password_hash=hash_password(body.password),
        role=body.role, area=body.area,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two requests for the same phone can both pass the check above; the unique
        # index then refuses the second one.
        db.rollback()
        raise duplicate
    db.refresh(user)
    return user
