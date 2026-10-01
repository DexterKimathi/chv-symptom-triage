"""The core flow: answers in; danger check, ranking, explanation and guidance out."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Assessment, AssessmentAnswer, Condition, Question, User
from app.schemas import (
    AssessmentRequest,
    AssessmentResponse,
    AssessmentSummary,
    ExplanationItem,
    RankedCondition,
)
from app.services.predictor import InvalidAnswers, get_predictor
from app.services.triage import DISCLAIMER, decide

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _to_response(a: Assessment) -> AssessmentResponse:
    return AssessmentResponse(
        id=a.id,
        outcome=a.outcome,
        headline=a.headline,
        danger_sign_triggered=a.danger_sign_triggered,
        danger_signs_present=a.danger_signs_present or [],
        top=[RankedCondition(**r) for r in a.results],
        top_confidence=a.top_confidence,
        explanation=[ExplanationItem(**e) for e in a.explanation],
        referral_level=a.referral_level,
        guidance=a.guidance,
        disclaimer=DISCLAIMER,
        model_version=a.model_version,
        created_at=a.created_at,
    )


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    body: AssessmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentResponse:
    settings = get_settings()
    predictor = get_predictor()

    # 1. Validate: every question answered exactly once, no unknown codes.
    try:
        predictor.validate(body.answers)
    except InvalidAnswers as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))

    # 2. Danger signs are read before the model and override it.
    danger = predictor.danger_signs_present(body.answers)

    # 3. Rank conditions and explain the top one. Runs even when a danger sign fired,
    #    so every assessment keeps a complete record.
    prediction = predictor.predict(body.answers, body.age_band, body.sex)

    conditions = {c.code: c for c in db.scalars(select(Condition)).all()}
    names = {code: c.name for code, c in conditions.items()}
    decision = decide(
        danger_signs_present=danger,
        ranked=prediction.ranked,
        names=names,
        guidance_by_condition={code: (c.referral_level, c.guidance) for code, c in conditions.items()},
        low_confidence=settings.low_confidence,
        proximity_margin=settings.proximity_margin,
    )

    questions = {q.code: q for q in db.scalars(select(Question)).all()}
    assessment = Assessment(
        chv_id=user.id,
        patient_ref=body.patient_ref,
        age_band=body.age_band,
        sex=body.sex,
        danger_sign_triggered=bool(danger),
        danger_signs_present=danger,
        outcome=decision.outcome,
        headline=decision.headline,
        referral_level=decision.referral_level,
        guidance=decision.guidance,
        results=[{"code": c, "name": names.get(c, c), "probability": round(p, 4)}
                 for c, p in prediction.ranked],
        top_confidence=round(prediction.ranked[0][1], 4),
        explanation=[{"question": questions[q].text_en if q in questions else q,
                      "answer": a, "weight": round(w, 4)}
                     for q, a, w in prediction.explanation],
        model_version=settings.model_version,
        answers=[AssessmentAnswer(question_id=questions[code].id, answer=answer)
                 for code, answer in body.answers.items() if code in questions],
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _to_response(assessment)


@router.get("", response_model=list[AssessmentSummary])
def list_assessments(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AssessmentSummary]:
    query = select(Assessment).order_by(Assessment.created_at.desc())
    if user.role != "admin":
        query = query.where(Assessment.chv_id == user.id)
    return [
        AssessmentSummary(
            id=a.id, patient_ref=a.patient_ref, outcome=a.outcome,
            top_condition=a.results[0]["name"] if a.results else None,
            top_confidence=a.top_confidence,
            danger_sign_triggered=a.danger_sign_triggered, created_at=a.created_at,
        )
        for a in db.scalars(query).all()
    ]


@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(
    assessment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AssessmentResponse:
    assessment = db.get(Assessment, assessment_id)
    # 404 rather than 403 for someone else's record, so ids do not leak.
    if assessment is None or (user.role != "admin" and assessment.chv_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return _to_response(assessment)
