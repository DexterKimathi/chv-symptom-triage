"""Create the tables and load the questions, conditions and demo accounts.

The 35 questions come from scripts/data/feature_schema.csv, copied from the ML repo. The
script checks their codes and order against the model bundle and stops if they differ,
so the questions the CHV sees always match the features the model expects.

Run:  python -m scripts.seed           (adds anything missing)
      python -m scripts.seed --reset   (drops every table first)
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import joblib
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Condition, Question, User

SCHEMA_CSV = Path(__file__).parent / "data" / "feature_schema.csv"

# Guidance is PROVISIONAL. It follows WHO IMCI referral principles and must be replaced
# with Ministry of Health Kenya community health guidance text, with the source recorded
# per condition, before any field use.
PROVISIONAL = ("PROVISIONAL: follows WHO IMCI referral principles. To be replaced with "
               "Ministry of Health Kenya community health guidance text.")

CONDITIONS = [
    {
        "code": "malaria", "name": "Malaria",
        "description": "A parasite infection spread by mosquitoes. Fever is the main sign, "
                       "often with chills, headache and body aches.",
        "referral_level": "refer_same_day",
        "guidance": "Refer today for a malaria test. Fever needs a test result before "
                    "treatment. Refer urgently if the patient becomes drowsy, cannot drink, "
                    "or has a fit.",
    },
    {
        "code": "typhoid", "name": "Typhoid fever",
        "description": "A bacterial infection spread through contaminated food or water. "
                       "Fever lasting several days, with stomach pain and weakness.",
        "referral_level": "refer_same_day",
        "guidance": "Refer today for assessment and a laboratory test. Typhoid cannot be "
                    "confirmed from symptoms alone and is easily confused with malaria.",
    },
    {
        "code": "urti_pneumonia", "name": "Respiratory infection or pneumonia",
        "description": "An infection of the nose, throat or lungs. Cough is the main sign; "
                       "fast breathing or chest indrawing suggests pneumonia.",
        "referral_level": "refer_same_day",
        "guidance": "Count the breaths for one full minute. If breathing is fast or the "
                    "lower chest pulls in, refer today. A cough with neither sign can usually "
                    "be cared for at home; refer if it lasts more than two weeks.",
    },
    {
        "code": "diarrhoeal", "name": "Acute diarrhoeal disease",
        "description": "Loose or watery stools, often with vomiting. The main danger is "
                       "losing too much fluid.",
        "referral_level": "home_care_and_monitor",
        "guidance": "Give extra fluids and oral rehydration salts. Refer today if there is "
                    "blood in the stool, sunken eyes, slow skin pinch, or if the patient "
                    "cannot drink.",
    },
    {
        "code": "uti", "name": "Urinary tract infection",
        "description": "An infection of the bladder or kidneys. Burning or pain when passing "
                       "urine, and passing urine often.",
        "referral_level": "refer_routine",
        "guidance": "Refer to a health facility for a urine test within the next day or two. "
                    "Refer today if there is fever with back or side pain.",
    },
]

# Demo accounts for local use and the check-in only. Change before any deployment.
DEMO_USERS = [
    {"name": "Demo Admin", "phone": "0700000000", "password": "admin-demo-2026",
     "role": "admin", "area": None},
    {"name": "Wanjiru Kamau", "phone": "0711111111", "password": "chv-demo-2026",
     "role": "chv", "area": "Kiambu"},
    {"name": "Otieno Odhiambo", "phone": "0722222222", "password": "chv-demo-2026",
     "role": "chv", "area": "Kisumu"},
]


def load_questions() -> list[dict]:
    with SCHEMA_CSV.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["data_type"] == "binary"]
    return [
        {"code": r["item_id"], "text_en": r["chv_question"], "category": r["category"],
         "display_order": i + 1, "is_danger_sign": r["is_danger_sign"].strip().lower() == "true"}
        for i, r in enumerate(rows)
    ]


def check_against_model(questions: list[dict]) -> None:
    bundle = joblib.load(get_settings().model_path)
    expected = [f for f in bundle["feature_order"] if f not in ("age_band", "sex")]
    found = [q["code"] for q in questions]
    if found != expected:
        raise SystemExit(
            "Question codes or order do not match the model bundle. Copy the matching "
            "feature_schema.csv from the ML repo. "
            f"Only in schema: {sorted(set(found) - set(expected))}; "
            f"only in model: {sorted(set(expected) - set(found))}"
        )
    danger = {q["code"] for q in questions if q["is_danger_sign"]}
    if danger != set(bundle["danger_signs"]):
        raise SystemExit("Danger signs in the schema do not match the model bundle.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    args = parser.parse_args()

    questions = load_questions()
    check_against_model(questions)

    if args.reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    added = {"questions": 0, "conditions": 0, "users": 0}
    with SessionLocal() as db:
        for q in questions:
            if not db.scalar(select(Question).where(Question.code == q["code"])):
                db.add(Question(**q))
                added["questions"] += 1
        for c in CONDITIONS:
            if not db.scalar(select(Condition).where(Condition.code == c["code"])):
                db.add(Condition(**c, source=PROVISIONAL))
                added["conditions"] += 1
        for u in DEMO_USERS:
            if not db.scalar(select(User).where(User.phone == u["phone"])):
                db.add(User(name=u["name"], phone=u["phone"], role=u["role"], area=u["area"],
                            password_hash=hash_password(u["password"])))
                added["users"] += 1
        db.commit()

    print(f"Database: {get_settings().database_url}")
    print(f"Added {added['questions']} questions, {added['conditions']} conditions, "
          f"{added['users']} users.")
    print(f"Questions match the model bundle ({len(questions)} codes, "
          f"{sum(q['is_danger_sign'] for q in questions)} danger signs).")
    print("\nDemo logins (local and check-in use only):")
    for u in DEMO_USERS:
        print(f"  {u['role']:5s}  {u['phone']}  /  {u['password']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
