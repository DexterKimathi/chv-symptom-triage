"""Request and response shapes. See docs/api.md."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Answer = Literal["yes", "no", "unknown"]
AgeBand = Literal["under_5", "5_to_14", "15_to_49", "50_plus"]
Sex = Literal["female", "male"]
Role = Literal["chv", "admin"]


# --- auth ------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role


# --- questions and conditions ----------------------------------------------- #
class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    text: str
    category: str
    display_order: int
    is_danger_sign: bool


class ConditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str
    referral_level: str
    guidance: str
    source: str


# --- assessments ------------------------------------------------------------ #
class AssessmentRequest(BaseModel):
    patient_ref: str = Field(
        min_length=1, max_length=40,
        description="Anonymous code chosen by the CHV. Never a name or ID number.",
    )
    age_band: AgeBand
    sex: Sex
    answers: dict[str, Answer] = Field(
        description="Every question code mapped to yes, no or unknown. "
                    "Unknown means not asked, and is not treated as no."
    )


class RankedCondition(BaseModel):
    code: str
    name: str
    probability: float


class ExplanationItem(BaseModel):
    question: str
    answer: Answer
    weight: float


class AssessmentResponse(BaseModel):
    id: int
    outcome: Literal["urgent_referral", "likely_condition", "low_confidence", "too_close_to_call"]
    headline: str
    danger_sign_triggered: bool
    danger_signs_present: list[str]
    top: list[RankedCondition]
    top_confidence: float
    explanation: list[ExplanationItem]
    referral_level: str
    guidance: str
    disclaimer: str
    model_version: str
    created_at: datetime


class AssessmentSummary(BaseModel):
    id: int
    patient_ref: str
    outcome: str
    top_condition: str | None
    top_confidence: float
    danger_sign_triggered: bool
    created_at: datetime


# --- admin ------------------------------------------------------------------ #
class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    area: str | None = Field(default=None, max_length=120)
    role: Role = "chv"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str
    role: Role
    area: str | None
    is_active: bool
