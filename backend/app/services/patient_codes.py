"""Patient codes, issued by the system so a volunteer never has to invent one, and so a
name or ID number can never be typed into the field.

A new patient gets a fresh code with their first assessment. A returning patient is
recorded under the code from their first visit, which the volunteer copies from the
patient's card; that code must be one the system issued.
"""

from __future__ import annotations

import re
import secrets

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models import Assessment

# No 0/O or 1/I, which are easy to confuse when a code is copied by hand.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LENGTH = 6
PATTERN = re.compile(rf"P-[{ALPHABET}]{{{LENGTH}}}")
EXAMPLE = "P-7K3QXM"


def normalise(code: str) -> str:
    """Codes are read off a card, so case and stray spaces are forgiven."""
    return code.strip().upper()


def is_well_formed(code: str) -> bool:
    return PATTERN.fullmatch(code) is not None


def is_issued(db: Session, code: str) -> bool:
    return bool(db.scalar(select(exists().where(Assessment.patient_ref == code))))


def new_code(db: Session) -> str:
    """A code no assessment uses yet. With 32^6 (about a billion) codes a repeat is rare,
    but it is checked rather than assumed."""
    while True:
        code = "P-" + "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
        if not is_issued(db, code):
            return code
