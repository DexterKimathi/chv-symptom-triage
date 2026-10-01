# API contract

Base URL in development: `http://localhost:8000` · Interactive docs: `/docs`

Every endpoint except `/health` and `/auth/login` needs `Authorization: Bearer <token>`.

## Endpoints

| Method | Endpoint | Who | Purpose |
|---|---|---|---|
| GET | `/health` | anyone | Liveness, model version and data hash being served |
| POST | `/auth/login` | anyone | Phone and password in, JWT out |
| GET | `/questions` | CHV, admin | The 35 checklist questions in display order |
| POST | `/assessments` | CHV, admin | **The core flow.** Answers in, referral decision out, saved |
| GET | `/assessments` | CHV, admin | History. A CHV sees only their own; an admin sees all |
| GET | `/assessments/{id}` | CHV, admin | One assessment, exactly as it was shown at the time |
| GET | `/conditions/{id}` | CHV, admin | Description, referral level and guidance for a condition |
| POST | `/admin/users` | admin | Create a CHV or admin account |

## POST /assessments

### Request

```json
{
  "patient_ref": "P-001",
  "age_band": "15_to_49",
  "sex": "female",
  "answers": {
    "fever_current": "yes",
    "chills_rigors": "yes",
    "cough": "no",
    "sore_throat": "unknown"
  }
}
```

- `patient_ref`: an anonymous code chosen by the CHV. **Never a name or ID number.**
- `age_band`: `under_5` | `5_to_14` | `15_to_49` | `50_plus`
- `sex`: `female` | `male`
- `answers`: **every one of the 35 question codes**, each `yes`, `no` or `unknown`.

`unknown` means the question was not asked. It is not treated as `no`: the model was
trained with "not asked" as its own state, so collapsing it to `no` would feed the model
inputs it never saw in training.

### Processing order

1. **Validate.** Exactly the 35 known codes, each `yes`/`no`/`unknown`.
2. **Danger signs.** Convulsions, lethargy or reduced alertness, and inability to drink or
   feed are checked **before** the model. Any one answered `yes` makes the outcome
   `urgent_referral`, whatever the model says.
3. **Rank.** The model returns probabilities for all five conditions; the top 3 are kept.
   This runs in every case, so a danger-sign referral still has a complete record.
4. **Decide**, first rule that applies:
   - danger sign present -> `urgent_referral`
   - top probability below the low-confidence threshold -> `low_confidence`
   - top two closer than the proximity margin -> `too_close_to_call`
   - otherwise -> `likely_condition`
5. **Explain.** The answers that pushed the top condition most, relative to the others.
6. **Save and return**, with the disclaimer.

Both thresholds are **provisional** (low confidence 0.50, proximity margin 0.10) and will
be set from held-out test results and stated in the report.

### Response `201`

```json
{
  "id": 12,
  "outcome": "likely_condition",
  "headline": "Likely: Malaria",
  "danger_sign_triggered": false,
  "danger_signs_present": [],
  "top": [
    {"code": "malaria", "name": "Malaria", "probability": 0.9937},
    {"code": "typhoid", "name": "Typhoid fever", "probability": 0.0055},
    {"code": "uti", "name": "Urinary tract infection", "probability": 0.0004}
  ],
  "top_confidence": 0.9937,
  "explanation": [
    {"question": "Has the patient had episodes of heavy sweating?", "answer": "yes", "weight": 1.21}
  ],
  "referral_level": "refer_same_day",
  "guidance": "Refer today for a malaria test. ...",
  "disclaimer": "This is decision support, not a diagnosis. ...",
  "model_version": "v0.1-lr-uncalibrated",
  "created_at": "2026-10-01T14:02:11Z"
}
```

`outcome` is one of `urgent_referral`, `likely_condition`, `low_confidence`,
`too_close_to_call`. Only `likely_condition` names a condition in the headline.

### Errors

| Status | When |
|---|---|
| 401 | Missing, invalid or expired token |
| 422 | A question code missing or unknown, an answer other than yes/no/unknown, or an invalid age band or sex |

## Other errors

| Endpoint | Status | When |
|---|---|---|
| `POST /auth/login` | 401 | Wrong phone or password. Same message either way, so registered numbers are not revealed |
| `GET /assessments/{id}` | 404 | Not found, **or belongs to another CHV**. Both look identical, so ids do not leak |
| `GET /conditions/{id}` | 404 | Not found |
| `POST /admin/users` | 403 | Caller is not an admin |
| `POST /admin/users` | 409 | Phone already registered |
| `POST /admin/users` | 422 | Password under 8 characters, or missing fields |

## Not in this version

Follow-ups, condition editing, model-version switching and the stats endpoint from the
build guide are on the cut list until the core flow is complete. Condition guidance is
loaded by `scripts/seed.py`.
