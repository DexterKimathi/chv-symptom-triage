# API contract

Base URL in development: `http://localhost:8000` · Interactive docs: `/docs`

Every endpoint except `/health` and `/auth/login` needs `Authorization: Bearer <token>`.

## Endpoints

| Method | Endpoint | Who | Purpose |
|---|---|---|---|
| GET | `/health` | anyone | Liveness, model version and data hash being served |
| POST | `/auth/login` | anyone | Phone and password in, JWT out |
| GET | `/questions` | CHV, admin | The 35 checklist questions in display order |
| POST | `/assessments/next` | CHV, admin | Adaptive questioning: the next question to ask, or done. Saves nothing |
| POST | `/assessments` | CHV, admin | **The core flow.** Answers in, referral decision out, saved |
| GET | `/assessments` | CHV, admin | History. A CHV sees only their own; an admin sees all |
| GET | `/assessments/{id}` | CHV, admin | One assessment, exactly as it was shown at the time |
| GET | `/conditions/{id}` | CHV, admin | Description, referral level and guidance for a condition |
| POST | `/admin/users` | admin | Create a CHV or admin account |

## POST /auth/login

Request `{"phone": "0711111111", "password": "..."}`. Response `200`:

```json
{"access_token": "<jwt>", "token_type": "bearer", "role": "chv", "name": "Wanjiru Kamau", "area": "Kiambu"}
```

`name` and `area` are for display only. The token alone decides what the user may do.
Wrong phone or password gives `401` with the same message either way.

## POST /assessments/next

Adaptive questioning. Send the answers given so far (the three danger signs first, yes or
no); questions not yet asked are left out. Nothing is saved.

```json
{"age_band": "15_to_49", "sex": "female",
 "answers": {"lethargy_reduced_alertness": "no", "unable_to_drink_or_feed": "no", "convulsions": "no"}}
```

Response `200`: either the next question, or `done` with the reason.

```json
{"done": false, "reason": null, "next_question": "fever_current", "asked": 3, "total": 35}
{"done": true, "reason": "confident", "next_question": null, "asked": 14, "total": 35}
```

- `danger_sign`: a danger sign is yes, so the result is an urgent referral.
- `confident`: the model's top probability reached the stop threshold (0.85, chosen on
  validation in the ML repo, `src/adaptive.py`, and read from `question_frequencies.json`).
- `complete`: every question has been asked.

The next question is the unasked one that most reduces the expected uncertainty about the
condition, from per-condition answer frequencies in the training data. When done, send the
assessment to `POST /assessments` with every unasked question as `unknown`.

`422` if a danger sign is missing or not yes/no, or a question code is unknown.

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

1. **Validate.** Exactly the 35 known codes, each `yes`/`no`/`unknown`. The three danger signs
   (`lethargy_reduced_alertness`, `unable_to_drink_or_feed`, `convulsions`) must be `yes` or `no`.
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

The thresholds travel inside the model file. For model v1.0 they were chosen on
validation data so that named results are correct at least 90% of the time: a condition
is named only when it leads the runner-up by **0.30** (the low-confidence value, 0.30, is
implied by that lead). On the held-out test set this named a condition for 85.5% of
patients, correct 90.4% of the time.

### Response `201`

```json
{
  "id": 12,
  "patient_ref": "P-001",
  "age_band": "15_to_49",
  "sex": "female",
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
  "model_version": "v1.0",
  "created_at": "2026-10-01T14:02:11Z"
}
```

`outcome` is one of `urgent_referral`, `likely_condition`, `low_confidence`,
`too_close_to_call`. Only `likely_condition` names a condition in the headline.

### Errors

| Status | When |
|---|---|
| 401 | Missing, invalid or expired token |
| 422 | A question code missing or unknown, an answer other than yes/no/unknown, a danger sign answered `unknown`, or an invalid age band or sex |

## Other errors

| Endpoint | Status | When |
|---|---|---|
| `POST /auth/login` | 401 | Wrong phone or password. Same message either way, so registered numbers are not revealed |
| `GET /assessments/{id}` | 404 | Not found, **or belongs to another CHV**. Both look identical, so ids do not leak |
| `GET /conditions/{id}` | 404 | Not found |
| `GET /assessments/{id}`, `GET /conditions/{id}` | 422 | Id not a whole number from 1 to 2147483647 |
| `POST /admin/users` | 403 | Caller is not an admin |
| `POST /admin/users` | 409 | Phone already registered |
| `POST /admin/users` | 422 | Password under 8 characters or over 72 bytes, phone not a Kenyan mobile number, or missing fields |
| `POST /auth/login` | 422 | Phone not a Kenyan mobile number |

## Not in this version

Follow-ups, condition editing, model-version switching and the stats endpoint from the
build guide are on the cut list until the core flow is complete. Condition guidance is
loaded by `scripts/seed.py`.

## Phone numbers

`phone` must be a Kenyan mobile number: `0712345678`, `254712345678` or `+254712345678`
(spaces and hyphens are ignored). It is always stored and returned in the local form,
`0712345678`, and login accepts any of the three spellings.
