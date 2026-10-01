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
3. `cp .env.example .env` (optional: every value has a working default)
4. `python -m scripts.seed --reset` to create the tables and load questions, conditions
   and demo accounts
5. `uvicorn app.main:app --reload`
6. Open http://localhost:8000/docs, log in with `POST /auth/login`, then use
   **Authorize** with the token

Runs on a local SQLite file by default. Set `DATABASE_URL` in `.env` to use PostgreSQL;
nothing else changes.

Demo logins, local and check-in use only:

| Role | Phone | Password |
|---|---|---|
| admin | 0700000000 | admin-demo-2026 |
| chv | 0711111111 | chv-demo-2026 |

The API contract is in [docs/api.md](docs/api.md) and the tables in
[docs/schema.md](docs/schema.md).

## Run the tests

```
pytest
```

## Model

Dataset: synthetic, generated in the ML repo from a 170-cell symptom probability table in
which every cell records its clinical source. No public dataset covers the five target
conditions together. Rebuildable from config and seed; see the ML repo README.

Model version used: `v0.1-lr-uncalibrated`. Logistic Regression, chosen on validation
macro F1 over Random Forest and XGBoost, and compared against a Naive Bayes reference
computed from the probability table. Not yet reweighted for malaria recall and not yet
evaluated on the held-out test set.

Model file: `app/services/model/model.joblib`, exported by `src/compare.py` in the ML repo
with its feature order, danger signs and data config hash. The scikit-learn version is
pinned in `requirements.txt` to the one it was trained with.

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

- [x] Week 1: backend endpoints
- [x] Week 2: tests + real model (32 tests; model pending malaria reweighting and test-set evaluation)
- [ ] Week 3: frontend
- [ ] Week 4: deployed + demo
