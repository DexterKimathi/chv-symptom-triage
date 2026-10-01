"""Questions and conditions: read-only reference data for the CHV app."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Condition, Question, User
from app.schemas import ConditionOut, QuestionOut

router = APIRouter(tags=["reference"])


@router.get("/questions", response_model=list[QuestionOut])
def list_questions(
    _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[QuestionOut]:
    questions = db.scalars(select(Question).order_by(Question.display_order)).all()
    return [
        QuestionOut(code=q.code, text=q.text_en, category=q.category,
                    display_order=q.display_order, is_danger_sign=q.is_danger_sign)
        for q in questions
    ]


@router.get("/conditions/{condition_id}", response_model=ConditionOut)
def get_condition(
    condition_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Condition:
    condition = db.get(Condition, condition_id)
    if condition is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Condition not found")
    return condition
