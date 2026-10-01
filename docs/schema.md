# Database schema

Five tables. Created and seeded by `python -m scripts.seed`.

## users

| Field | Type | Notes |
|---|---|---|
| id | int, PK | |
| name | string | |
| phone | string, unique | Login identifier |
| password_hash | string | bcrypt. Plain passwords are never stored or returned |
| role | string | `chv` or `admin` |
| area | string, nullable | Where the CHV works |
| is_active | bool | Deactivated users cannot log in |
| created_at | datetime | |

## questions

| Field | Type | Notes |
|---|---|---|
| id | int, PK | |
| code | string, unique | **Must equal the model's feature name.** Checked against the model bundle at seed time |
| text_en | text | The question the CHV reads out |
| category | string | constitutional, respiratory, gastrointestinal, hydration, urinary, neurological, other |
| display_order | int | 1 to 35 |
| is_danger_sign | bool | True for convulsions, lethargy or reduced alertness, unable to drink or feed |

Loaded from `scripts/data/feature_schema.csv`, the same file the model was trained from.
Seeding stops if the codes, their order or the danger signs differ from the model bundle,
so the questions and the model cannot drift apart.

## conditions

| Field | Type | Notes |
|---|---|---|
| id | int, PK | |
| code | string, unique | Matches the model's class label |
| name | string | Shown to the CHV |
| description | text | |
| referral_level | string | `refer_same_day`, `refer_routine` or `home_care_and_monitor` |
| guidance | text | What the CHV should do |
| source | text | Where the guidance came from |

Guidance is currently **provisional**, following WHO IMCI referral principles. It must be
replaced with Ministry of Health Kenya community health guidance text, with the source
recorded per condition, before any field use.

## assessments

| Field | Type | Notes |
|---|---|---|
| id | int, PK | |
| chv_id | int, FK users | Who carried out the assessment |
| patient_ref | string | **Anonymous code only. Never a name or ID number** |
| age_band | string | |
| sex | string | |
| danger_sign_triggered | bool | |
| danger_signs_present | JSON | Which danger signs were answered yes |
| outcome | string | `urgent_referral`, `likely_condition`, `low_confidence`, `too_close_to_call` |
| headline | text | What the CHV was told, as shown |
| referral_level | string | As shown |
| guidance | text | As shown |
| results | JSON | Top 3: code, name, probability |
| top_confidence | float | |
| explanation | JSON | Answers that most supported the top result |
| model_version | string | Which model produced this result |
| created_at | datetime | |

`headline`, `referral_level` and `guidance` record **what the CHV was told at the time**.
Re-opening an assessment returns these, not a fresh computation under today's thresholds.
For a health tool the record has to show what was actually said.

## assessment_answers

| Field | Type | Notes |
|---|---|---|
| id | int, PK | |
| assessment_id | int, FK assessments | |
| question_id | int, FK questions | |
| answer | string | `yes`, `no` or `unknown`. Unknown is not stored as no |

## Privacy

Health data is sensitive under Kenya's Data Protection Act (2019) and the Digital Health
Act (2023). No patient names or ID numbers are stored anywhere in this schema.
