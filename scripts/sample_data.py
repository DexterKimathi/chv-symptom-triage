"""Add made-up volunteers and assessments, to show the admin dashboard with data in it.

NONE OF THIS IS REAL. The answers are drawn from the model's synthetic training
frequencies, and one area is given a rise in malaria on purpose so that the dashboard has
something to flag. It must never be reported as a finding. The dashboard shows a notice
whenever sample data is included.

Every record goes through the same code as a real assessment, so the results are what the
app would actually have said.

Run:  python -m scripts.sample_data            (adds the sample data once)
      python -m scripts.sample_data --remove   (deletes it, leaving everything else)
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import Assessment, User
from app.routers.assessments import create_assessment
from app.schemas import AssessmentRequest
from app.services.predictor import get_predictor
from app.services.reporting import KENYA, SAMPLE_PHONE_PREFIX
from scripts.seed import masked

# Area, number of sample volunteers, and how common each condition is there.
CONDITIONS = ["malaria", "typhoid", "urti_pneumonia", "diarrhoeal", "uti"]
AREAS = [
    ("Kisumu",    3, [0.30, 0.14, 0.28, 0.18, 0.10]),
    ("Kakamega",  2, [0.28, 0.18, 0.26, 0.18, 0.10]),
    ("Kilifi",    2, [0.24, 0.14, 0.26, 0.26, 0.10]),
    ("Kiambu",    2, [0.06, 0.16, 0.44, 0.18, 0.16]),
    ("Turkana",   1, [0.12, 0.14, 0.24, 0.40, 0.10]),
]
DAYS = 168          # two 12-week periods, so every view has something to compare with
PER_VOLUNTEER_WEEK = 3.0
RISE_AREA, RISE_DAYS, RISE_PER_DAY = "Kisumu", 20, 2
DANGER_SHARE = 0.06


def sample_answers(rng: random.Random, frequencies: dict, condition: str, danger: list[str]) -> dict:
    answers = {}
    for code, by_condition in frequencies.items():
        p = by_condition[condition]
        answers[code] = rng.choices(["yes", "no", "unknown"], [p["yes"], p["no"], p["unknown"]])[0]
    for code in danger:
        answers[code] = "no"
    if rng.random() < DANGER_SHARE:
        answers[rng.choice(danger)] = "yes"
    return answers


def sample_users(db) -> list[User]:
    return list(db.scalars(select(User).where(User.phone.startswith(SAMPLE_PHONE_PREFIX))).all())


def remove(db) -> None:
    users = sample_users(db)
    ids = [u.id for u in users]
    records = db.scalars(select(Assessment).where(Assessment.chv_id.in_(ids))).all() if ids else []
    for record in records:   # one at a time, so each record's answers go with it
        db.delete(record)
    for user in users:
        db.delete(user)
    db.commit()
    print(f"Removed {len(users)} sample volunteers and {len(records)} sample assessments.")


def add(db, seed: int) -> None:
    if sample_users(db):
        print("Sample data is already there. Use --remove first to rebuild it.")
        return
    rng = random.Random(seed)
    frequencies = json.loads(open(get_settings().questions_path, encoding="utf-8").read())["questions"]
    danger = sorted(get_predictor().danger_signs)
    now = datetime.now(timezone.utc)
    today = now.astimezone(KENYA).date()

    volunteers: list[tuple[User, str, list[float]]] = []
    for area, count, weights in AREAS:
        for _ in range(count):
            n = len(volunteers) + 1
            user = User(
                name=f"Sample Volunteer {n:02d}", phone=f"{SAMPLE_PHONE_PREFIX}{n:03d}",
                # Nobody is meant to log in as these: the password is random and not kept.
                password_hash=hash_password(secrets.token_urlsafe(24)),
                role="chv", area=area,
            )
            db.add(user)
            volunteers.append((user, area, weights))
    db.commit()

    plan: list[tuple[datetime, User, str]] = []

    def moment(days_ago: int) -> datetime:
        day = today - timedelta(days=days_ago)
        at = datetime(day.year, day.month, day.day, rng.randint(8, 17), rng.randint(0, 59), tzinfo=KENYA)
        # Nothing is dated in the future: today's visits happened earlier than now.
        return min(at.astimezone(timezone.utc), now - timedelta(minutes=rng.randint(5, 90)))

    for user, area, weights in volunteers:
        for days_ago in range(DAYS):
            if rng.random() < PER_VOLUNTEER_WEEK / 7:
                plan.append((moment(days_ago), user, rng.choices(CONDITIONS, weights)[0]))
    rising = [user for user, area, _ in volunteers if area == RISE_AREA]
    for days_ago in range(RISE_DAYS):
        for _ in range(RISE_PER_DAY):
            plan.append((moment(days_ago), rng.choice(rising), "malaria"))

    for at, user, condition in sorted(plan, key=lambda item: item[0]):
        body = AssessmentRequest(
            age_band=rng.choices(["under_5", "5_to_14", "15_to_49", "50_plus"], [3, 2, 4, 2])[0],
            sex=rng.choice(["female", "male"]),
            answers=sample_answers(rng, frequencies, condition, danger),
        )
        result = create_assessment(body, user=user, db=db)
        db.get(Assessment, result.id).created_at = at
        db.commit()
    print(f"Added {len(volunteers)} sample volunteers and {len(plan)} sample assessments.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true", help="delete the sample data")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    print(f"Database: {masked(get_settings().database_url)}")
    with SessionLocal() as db:
        remove(db) if args.remove else add(db, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
