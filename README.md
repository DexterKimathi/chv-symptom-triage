# CHV Symptom Triage

**Student:** Dexter Kimathi (166889) · **Group:** U-CS 31

## Repos

- Backend: https://github.com/RAM-AS-RAP/ucs31-kimathi-backend (this repo)
- ML: https://github.com/RAM-AS-RAP/ucs31-kimathi-ml
- Frontend: https://github.com/RAM-AS-RAP/ucs31-kimathi-frontend

## Core flow

A community health volunteer answers 34 yes/no symptom questions; the backend checks for
danger signs, runs the model, explains the result and returns referral guidance, and the
assessment is saved.

## Stack

Backend: FastAPI · Database: PostgreSQL · Frontend: Next.js ·
Model: XGBoost (compared against Logistic Regression, Random Forest and a Naive Bayes
reference built from the probability table)

## Run the backend

1. `python -m venv venv && venv\Scripts\activate` (Windows) or `source venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in values
4. `uvicorn app.main:app --reload`
5. Open http://localhost:8000/docs

## Run the tests

```
pytest
```

## Model

Dataset: synthetic, generated in the ML repo from a 170-cell symptom probability table in
which every cell records its clinical source. No public dataset covers the five target
conditions together. Rebuildable from config and seed; see the ML repo README.

Model version used: none yet, the prediction endpoint returns a stubbed result until
week 2.

Model file: exported with `joblib` from the ML repo and tagged as a release there.

## Safety rules

These are not optional and are checked before anything else runs:

- Danger-sign questions are evaluated **before** the model. Any danger sign answered yes
  returns "refer urgently now", whatever the model says.
- A result is never presented as a diagnosis. Every response carries a disclaimer and a
  seek-professional-care message.
- Low confidence returns "symptoms do not clearly match; refer for assessment" rather than
  naming a condition.
- Patients are stored under an anonymous code. No names, no ID numbers.

## Status

- [ ] Week 1: backend endpoints
- [ ] Week 2: tests + real model
- [ ] Week 3: frontend
- [ ] Week 4: deployed + demo
