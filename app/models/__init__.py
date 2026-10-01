"""Database tables. See docs/schema.md."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(10))  # "chv" or "admin"
    area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Must match the model's feature name exactly; validated at seed time.
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    text_en: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40))
    display_order: Mapped[int] = mapped_column(Integer)
    is_danger_sign: Mapped[bool] = mapped_column(Boolean, default=False)


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    referral_level: Mapped[str] = mapped_column(String(40))
    guidance: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chv_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Anonymous code chosen by the CHV. Never a name or national ID number.
    patient_ref: Mapped[str] = mapped_column(String(40))
    age_band: Mapped[str] = mapped_column(String(20))
    sex: Mapped[str] = mapped_column(String(10))
    danger_sign_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    danger_signs_present: Mapped[list] = mapped_column(JSON, default=list)
    outcome: Mapped[str] = mapped_column(String(30))
    # What the CHV was told, stored as shown. Re-opening an assessment returns this, not a
    # re-computation under whatever thresholds apply today.
    headline: Mapped[str] = mapped_column(Text)
    referral_level: Mapped[str] = mapped_column(String(40))
    guidance: Mapped[str] = mapped_column(Text)
    results: Mapped[list] = mapped_column(JSON)
    top_confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[list] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    answers: Mapped[list["AssessmentAnswer"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    # "yes", "no" or "unknown". Unknown is a distinct state, not a recorded no.
    answer: Mapped[str] = mapped_column(String(10))

    assessment: Mapped[Assessment] = relationship(back_populates="answers")
