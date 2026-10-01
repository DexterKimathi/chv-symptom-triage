# Source notes for the symptom probability table

Working record of every clinical source consulted, what it supports, and its limitations.
Each probability cell in `symptom_probability_table.csv` must point to an entry here.

**Rule: no value enters the table without an entry below. Nothing is estimated silently.**

---

## S001 — Habte et al. (2018), typhoid fever, Ethiopia

Habte, L., Tadesse, E., Ferede, G., & Amsalu, A. (2018). Typhoid fever: clinical
presentation and associated factors in febrile patients visiting Shashemene Referral
Hospital, southern Ethiopia. *BMC Research Notes, 11*, 605.
https://doi.org/10.1186/s13104-018-3713-y

Design: prospective, febrile outpatients, blood culture confirmed.
**n = 21 confirmed cases** out of 421 screened.

| Symptom | n | % |
|---|---|---|
| Fatigue | 17 | 81.0 |
| Fever >= 5 days | 15 | 71.4 |
| Loss of appetite | 13 | 61.9 |
| Cough | 11 | 52.4 |
| Abdominal pain | 8 | 38.1 |
| Constipation | 7 | 33.3 |
| Diarrhoea | 6 | 28.6 |
| Skin rash | 3 | 14.3 |

**Limitation — must be recorded in the proposal.** n = 21 is small; each patient moves a
proportion by 4.8 percentage points, so these values carry wide confidence intervals. East
African setting and culture confirmation make it relevant, but it is too small to be the sole
basis for the typhoid column. Status for cells drawn from it alone: `VERIFY`, pending a
larger corroborating study.

Maps to schema items: `fatigue_weakness`, `fever_over_3_days` (approximate; source uses
>= 5 days, schema uses > 3 days — **not a clean match, flag**), `poor_appetite`, `cough`,
`abdominal_pain`, `diarrhoea`, `skin_rash`.

---

## S002 — De Santis et al. (2017), febrile children, Tanzania — HIGH PRIORITY LEAD

De Santis, O., Kilowoko, M., Kyungu, E., Sangu, W., Cherpillod, P., Kaiser, L., Genton, B.,
& D'Acremont, V. (2017). Predictive value of clinical and laboratory features for the main
febrile diseases in children living in Tanzania: A prospective observational study.
*PLoS ONE, 12*(5), e0173314. https://doi.org/10.1371/journal.pone.0173314

Data: https://doi.org/10.5281/zenodo.166713 (DOI resolves; Zenodo returned 504 on
2026-09-13, files not yet inspected)

Design: prospective, 1,005 consecutive febrile children (axillary temp >= 38 C), aged
2 months to 10 years, two Tanzanian outpatient clinics — Dar es Salaam (urban, n=510) and
Ifakara (rural, n=500). Diagnoses by pre-defined WHO / IDSA criteria with microbiological
or radiological confirmation.

Labelled cases relevant to this project:

| Condition | n |
|---|---|
| Malaria | 105 |
| Urinary tract infection | 59 |
| Typhoid fever | 37 |
| Radiological pneumonia | 31 |

**Why this matters:** East African, outpatient, four of the five target conditions, real
patients. A far closer calibration reference than DDXPlus, which supplies only the
respiratory class.

**Why it cannot be the training corpus:**
1. Children only (94% under 5); project targets the general CHV caseload.
2. Conditioned on fever >= 38 C, so afebrile UTI, afebrile URTI and most acute diarrhoea are
   structurally absent — every symptom distribution is biased by that inclusion criterion.
3. Per-class counts far too small for a five-class model (typhoid 37, pneumonia 31).
4. **Acute diarrhoeal disease is not a diagnostic category in this study.** Confirmed.
5. No distinct URTI label; only radiological pneumonia.
6. Strongest published predictors need instruments the schema excludes — temperature >= 40 C
   (thermometer), abnormal auscultation (stethoscope), radiological pneumonia (X-ray).
7. Data collected 2008; Tanzanian malaria prevalence has fallen substantially since.
8. 21 children carry multiple diagnoses (multi-label).

**Note on what the paper does and does not give.** The published tables report adjusted
likelihood ratios, not raw symptom prevalences (the one exception found: jaundice in 22% of
typhoid cases). Raw per-symptom frequencies by diagnosis require the row-level Zenodo
database. **Retrieve and inspect that file before relying on this source.**

---

## S003 — Rautman et al. (2024), febrile children, Ghana — secondary lead

Longitudinal hospital study of febrile children, Ghana. *Tropical Medicine & International
Health*. Data and R script: https://doi.org/10.5281/zenodo.8220138 (not yet inspected).
More recent than S002 but West rather than East African.

---

## Datasets deliberately rejected

**Kaggle-style "symptom to disease" tables** (e.g. the 50-symptom, 9-disease table used in
some published XAI papers). These are typically expert-elicited or synthetically expanded
with no per-cell provenance, no population, and no sampling frame. Adopting one would be
*weaker* than this project's own generator, which at least carries a traceable source per
cell. Do not use as training data or as a calibration reference.

---

## Still to source

| Condition | Status |
|---|---|
| Malaria | not started — WHO Guidelines for Malaria (2023) for cardinal signs; need East African frequency study |
| Typhoid fever | partial (S001, underpowered) — need larger cohort |
| URTI / pneumonia | not started — IMCI chart booklet defines fast breathing and chest indrawing thresholds |
| Acute diarrhoeal disease | not started — IMCI dehydration classification signs |
| Urinary tract infection | not started — need primary-care UTI symptom-frequency study |
