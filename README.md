# CHV Symptom Triage

**Dexter Kimathi** (166889) · BSc Informatics and Computer Science, Strathmore University

Decision support for community health volunteers in rural Kenya. A volunteer answers 35
yes/no symptom questions and gets back a likely illness among five high-burden
conditions, a confidence score and referral guidance. Danger signs are checked before the
model and always trigger urgent referral. **It never presents a result as a diagnosis.**

Conditions: malaria, typhoid fever, upper respiratory infection or pneumonia, acute
diarrhoeal disease, urinary tract infection.

## Structure

| Folder | What it holds | Run instructions |
|---|---|---|
| [`ml/`](ml/) | Feature schema, sourced symptom probability table, synthetic data generator, model comparison and the exported model | [ml/README.md](ml/README.md) |
| [`backend/`](backend/) | FastAPI service: auth, the assessment flow, danger-sign rules, tests and the API contract | [backend/README.md](backend/README.md) |
| [`frontend/`](frontend/) | Next.js app for volunteers and admins | [frontend/README.md](frontend/README.md) |

## How the parts connect

```
ml/        builds the probability table, generates the data, trains and exports model.joblib
  |
  v
backend/   loads model.joblib at startup and serves POST /assessments
  |
  v
frontend/  volunteers answer the checklist and see the result
```

## Stack

Python, FastAPI, PostgreSQL (SQLite in development), scikit-learn, XGBoost, Next.js.

## History

Each folder carries the full commit history of the repo it came from, with original
dates. Day-to-day development happens in the per-part repos; this repository brings them
together. To pull in their latest changes, run `./sync.sh` from the repository root.
