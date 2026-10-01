from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
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
    if db.scalar(select(User).where(User.phone == body.phone)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A user with this phone already exists")
    user = User(
        name=body.name, phone=body.phone, password_hash=hash_password(body.password),
        role=body.role, area=body.area,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
