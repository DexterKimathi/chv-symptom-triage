"""Request and response shapes. See docs/api.md."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

Answer = Literal["yes", "no", "unknown"]
AgeBand = Literal["under_5", "5_to_14", "15_to_49", "50_plus"]
Sex = Literal["female", "male"]
Role = Literal["chv", "admin"]

_KENYAN_MOBILE = re.compile(r"^(?:0|\+?254)([17]\d{8})$")


def _normalise_phone(value: str) -> str:
    """Accept 0712345678, 254712345678 or +254712345678, with spaces or hyphens.

    Always returns the local form, 0712345678, so one person cannot hold two accounts
    under two spellings of the same number, and can log in with either.
    """
    match = _KENYAN_MOBILE.match(re.sub(r"[\s-]", "", value))
    if match is None:
        raise ValueError("Enter a Kenyan mobile number, such as 0712345678 or +254712345678")
    return "0" + match.group(1)


Phone = Annotated[str, Field(min_length=7, max_length=20), AfterValidator(_normalise_phone)]


def _as_utc(value: datetime) -> datetime:
    """Timestamps are written in UTC, but SQLite hands them back without a timezone.

    Label those as UTC so the API always sends an unambiguous time ending in Z; without
    it a browser reads the value as local time, three hours out in Kenya.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


# --- auth ------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    phone: Phone
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    # Shown on the home screen so the volunteer can see whose account is open.
    name: str
    area: str | None = None


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
    patient_ref: str
    age_band: AgeBand
    sex: Sex
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
    created_at: UtcDatetime


class AssessmentSummary(BaseModel):
    id: int
    patient_ref: str
    outcome: str
    top_condition: str | None
    top_confidence: float
    danger_sign_triggered: bool
    created_at: UtcDatetime


# --- admin ------------------------------------------------------------------ #
class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: Phone
    password: str = Field(min_length=8, max_length=128)
    area: str | None = Field(default=None, max_length=120)
    role: Role = "chv"

    @field_validator("password")
    @classmethod
    def _fits_bcrypt(cls, value: str) -> str:
        # bcrypt hashes at most 72 bytes and raises on anything longer. Counted in bytes,
        # not characters, because non-ASCII characters take more than one.
        if len(value.encode()) > 72:
            raise ValueError("Password must be at most 72 bytes long")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str
    role: Role
    area: str | None
    is_active: bool
