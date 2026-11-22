# Symptom-to-Illness Classification Model

Supporting code for the BSc ICS project *"A Logistic Regression Classification Model for
Triage Support in Rural Kenyan Community Health Settings"* (Dexter Kimathi, 166889,
Strathmore University).

Five target conditions: malaria, typhoid fever, upper respiratory tract infection or
pneumonia, acute diarrhoeal disease, urinary tract infection.

**Student:** Dexter Kimathi (166889) · **Group:** U-CS 31

## Repos

- ML: https://github.com/RAM-AS-RAP/ucs31-kimathi-ml (this repo)
- Backend: https://github.com/RAM-AS-RAP/ucs31-kimathi-backend
- Frontend: https://github.com/RAM-AS-RAP/ucs31-kimathi-frontend
- All three together: https://github.com/DexterKimathi/chv-symptom-triage

## Model v1.0

The deployed model is **Logistic Regression**, chosen over Random Forest and XGBoost on
validation macro F1, with malaria examples weighted 1.5 times. It is released as the tag
[`v1.0`](https://github.com/RAM-AS-RAP/ucs31-kimathi-ml/releases/tag/v1.0) and stored in
`results/model.joblib`, together with the ordered list of its 37 inputs (35 symptom
questions, age band and sex), the referral thresholds, the danger-sign items, the config
hash of the data it was trained on and the library versions. The backend loads that file
and records the model version on every assessment.

Results on the held-out test partition (2,999 records, opened once):

| Measure | Result | Criterion | Met |
|---|---|---|---|
| Macro F1 | 0.853 | At least 0.80 | Yes |
| Expected calibration error | 0.042 | At most 0.10 | Yes |
| Recall: malaria | 0.864 | At least 0.90 | No |
| Recall: URTI or pneumonia | 0.900 | At least 0.90 | No (0.8998) |
| Recall: typhoid fever | 0.756 | At least 0.75 | Yes |
| Recall: acute diarrhoeal disease | 0.875 | At least 0.75 | Yes |
| Recall: urinary tract infection | 0.866 | At least 0.75 | Yes |

A condition is named only when its probability is at least 0.30 and leads the runner-up
by at least 0.30. On test that happened for 85.5% of patients, and named results were
correct 90.4% of the time. A patient whose result is not named is referred for same-day
assessment.

These figures measure agreement with the generated data, not clinical accuracy. Rerunning
the pipeline on five further generated corpora gave a test macro F1 of 0.844 ± 0.011, and
the typhoid floor was met only on the seed-42 corpus (see the project document,
Section 5.4.2).

## Dataset

Synthetic, generated in this repo. No public dataset covers the five target conditions
together, so the corpus (20,000 records, 4,000 per condition) is produced from
`config/symptom_probability_table.csv`, which holds 175 cells (35 questions by five
conditions). Each cell records its tier, source and status:

| Tier | Cells | Basis |
|---|---|---|
| Published frequency | 8 | Typhoid, from Habte et al. (2018) and De Santis et al. (2017); `VERIFY` until the extraction is re-checked |
| Guideline ordinal band | 61 | 44 from the WHO malaria guidelines and the WHO IMCI chart booklet; 17 (10 UTI, 7 typhoid) still `VERIFY`, with no confirmed source |
| Background rule | 106 | The declared background rate (0.03) for a symptom that is not characteristic |

Ordinal bands are turned into probabilities by one uniform rule in `config/generator.yaml`
(cardinal 0.85, common 0.60, frequent 0.40, occasional 0.20, background 0.03).
`config/source_notes.md` records what each source supports and what is still missing.

Rebuild the exact corpus from config and seed alone:

```
python -m src.probability_table
python -m src.generator --seed 42
```

`data/generated/` and `data/splits/` are not tracked because they are reproducible.

## Design constraints

1. **All five classes are generated.** DDXPlus is *not* training data. It is used only as
   an external reference for the respiratory class. Mixing it into training would let the
   model separate classes by data provenance rather than by clinical presentation.
2. **Every probability is traceable.** Each cell names its source or the declared rule
   that set it; cells without a confirmed source are marked `VERIFY`, not hidden.
3. **Generation is seeded and config-driven**, reproducible from the scripts and
   `config/` alone.
4. **The test partition is opened once**, after every setting has been fixed on
   validation. `src.evaluate` refuses to run if a test report already exists.
5. **Macro F1 > 0.95 is a failure signal, not a success.** It indicates residual generator
   separability and must be reported as such.

## Environment

```
winget install Python.Python.3.12
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.lock.txt` records the exact versions used, for reproducibility.

## Layout

```
src/             logic, importable and runnable as modules
config/          generator configuration, feature schema, probability table, source notes
data/raw/ddxplus/   DDXPlus release files (external, not tracked)
data/generated/  synthetic corpus (reproducible from seed + config)
data/splits/     train, validation and test partitions with the group audit
results/         published results and the v1.0 model (tracked)
outputs/         scratch output the pipeline rewrites (not tracked)
notebooks/       thin presentation notebooks; import from src, hold no logic
tests/           checks on the generator, preparation, training and helpers
```

## Pipeline

Each step runs with one command, in this order.

| Step | Command | Output |
|---|---|---|
| 1. Probability table | `python -m src.probability_table` | `config/symptom_probability_table.csv` |
| 2. Generate corpus | `python -m src.generator --seed 42` | `data/generated/corpus.csv` |
| 3. Corpus report | `python -m src.corpus_report` | format checks, class counts, exact matches, source counts |
| 4. Partitions | `python -m src.prepare_data`, then `--write` | grouped 70/15/15 split in `data/splits/`; refuses to overwrite |
| 5. Baseline | `python -m src.train` | first Logistic Regression baseline on validation |
| 6. Compare models | `python -m src.compare` | Naive Bayes reference, LR, RF and XGBoost on validation |
| 7. Finalise | `python -m src.finalise` | malaria weight and referral thresholds, on validation; `results/model.joblib` |
| 8. Evaluate | `python -m src.evaluate` | single test evaluation: `results/test_report.json` |
| 9. Adaptive questioning | `python -m src.adaptive --test` | question order, stop threshold and its test check |
| 10. DDXPlus comparison | `python -m src.calibration` | `results/ddxplus_comparison.csv` and `.json` |

Run the tests with `python -m unittest discover -s tests -v`.

### Partitions

`prepare_data` keeps identical symptom vectors, and vectors differing in exactly one
answer, in the same partition; linked chains form indivisible groups (SciPy connected
components). Groups are allocated towards per-condition 70/15/15 targets, larger groups
first, so the proportions are approximate. Not asked (`-1`) counts as a distinct answer.
`split_audit.csv` maps each row back to its record and group; it is never a model input.

### Adaptive questioning

The three danger signs are asked first, and a Yes ends questioning with an urgent
referral. After that, the next question is the one with the largest expected information
gain, and questioning stops once the model's top probability reaches 0.85. On test this
asked a median of 18 of the 35 questions for non-urgent patients and agreed with the full
checklist for 99.5% of them.

### DDXPlus comparison

`src.calibration` maps the 18 schema items that have a DDXPlus equivalent onto the DDXPlus
training partition (URTI and Pneumonia, 90,129 records) and compares their frequencies
with the generated respiratory records, band by band. 8 items agree, 7 are one band away
and 3 diverge (drenching sweats, body aches, wheeze); the divergent cells are flagged for
revision in a later version of the table. DDXPlus is itself synthetic and simulates only
each pathology's own evidence list, so this is a plausibility check, not real-patient
validation. Download the release files from
https://doi.org/10.6084/m9.figshare.20043374 into `data/raw/ddxplus/` first.

## Acceptance thresholds

Committed to in the proposal and not loosened.

- Macro F1 >= 0.80 on the held-out test partition
- Per-class recall >= 0.90 for malaria and URTI/pneumonia
- Per-class recall >= 0.75 for the other three classes
- Expected calibration error <= 0.10
- Macro F1 > 0.95 => flag as separability artefact

## Limitations

The data are synthetic, so every result is internal validity on the generated corpus. The
planned set of hand-encoded clinical vignettes has not been built, 17 probability cells
await a confirmed source, and the model has not been evaluated on real patients.
