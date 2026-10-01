# Symptom-to-Illness Classification Model

Supporting code for the BSc ICS project *"An XGBoost Symptom-to-Illness Classification
Model for Triage Support in Rural Kenyan Community Health Settings"* (Dexter Kimathi, 166889,
Strathmore University).

Five target conditions: malaria, typhoid fever, upper respiratory tract infection or
pneumonia, acute diarrhoeal disease, urinary tract infection.

**Student:** Dexter Kimathi (166889) · **Group:** U-CS 31

## Repos

- ML: https://github.com/RAM-AS-RAP/ucs31-kimathi-ml (this repo)
- Backend: https://github.com/RAM-AS-RAP/ucs31-kimathi-backend
- Frontend: https://github.com/RAM-AS-RAP/ucs31-kimathi-frontend

## Dataset

Synthetic, generated in this repo. No public dataset covers the five target conditions
together, so the corpus is produced from `config/symptom_probability_table.csv`, in which
every one of the 170 cells records its clinical source and status.

Rebuild the exact corpus from config and seed alone:

```
python -m src.probability_table
python -m src.generator --seed 42
```

`data/generated/` is not tracked because it is reproducible from the two commands above.
The probability table, feature schema and clinical profiles **are** tracked: they are the
sourced inputs, not outputs.

## Model file

The chosen model is exported with `joblib`, together with the ordered list of the 34
feature codes and the config hash of the data it was trained on, and tagged as a release
in this repo. The backend loads that file and records the model version on every
assessment. Not yet produced; due week 2.

## Design constraints this repository must satisfy

These come from the submitted proposal and are not optional:

1. **All five classes are synthetically generated.** DDXPlus is *not* training data. It is
   used only as an external calibration reference for the respiratory class. Mixing it into
   training would let the model separate classes by data provenance rather than by clinical
   presentation (proposal 1.5.2, 3.2.1).
2. **Every probability is traceable to a named clinical source.** No cell in the probability
   table may be set by researcher judgement (proposal 3.2.1).
3. **Generation is seeded and config-driven**, reproducible from the script and its
   configuration file alone (proposal 3.2.1, 3.7.2).
4. **Macro F1 > 0.95 is a failure signal, not a success.** It indicates residual generator
   separability and must be reported as such (proposal 3.2.4).

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
src/          logic, importable and runnable as modules
config/       generator configuration, feature schema, probability table
data/raw/     DDXPlus release files (external, not tracked)
data/generated/  synthetic corpus (reproducible from seed + config)
data/external/   hand-encoded clinical vignette test set
outputs/      figures and reports for Chapter 5
notebooks/    thin presentation notebooks; import from src, hold no logic
tests/        checks on the generator and schema
```

## Pipeline

Each step runs with one command.

| Step | Command | Output |
|---|---|---|
| 1. Generate corpus | `python -m src.generator --seed 42` | `data/generated/corpus.csv` |
| 2. Corpus report | `python -m src.corpus_report` | format checks, class counts, exact matches, source counts |
| 2a. Preview partitions | `python -m src.prepare_data` | approximate 70/15/15 split, one-answer-apart screening, label-conflict audit; no writes |
| 2b. Save reviewed partitions | `python -m src.prepare_data --write` | `data/splits/`; refuses to overwrite |
| 3. DDXPlus calibration (planned) | `python -m src.calibration` | generated vs DDXPlus synthetic respiratory frequencies |
| 4. First baseline | `python -m src.train` | Logistic Regression pipeline and preliminary validation metrics |
| 4b. Compare candidates (planned) | Not implemented | LR, RF, XGBoost under identical grouped CV |
| 5. Evaluate (planned) | `python -m src.evaluate` | final test confusion matrix, per-class recall, macro F1, ECE |

*(Steps are added incrementally; see the ClickUp board for current status.)*

## Before training

Run `python -m unittest discover -s tests -p "test_prepare_data.py" -v` to check the
preparation logic on small artificial fixtures. No training is performed.

`prepare_data` keeps identical symptom vectors and vectors differing in exactly one
recorded symptom answer together, even if their age, sex or recorded labels differ.
Linked chains form indivisible groups: if A matches B and B matches C by this rule,
all three stay together, even if A and C differ in two answers. SciPy connected
components implements this grouping without constructing an all-pairs distance matrix.
Groups are allocated directly toward per-disease 70/15/15 record targets for
training/validation/test. Larger groups are placed first; the configured seed (or
`--seed`) orders groups of equal size. Each placement minimises the increase in
`sum((count - target)^2 / target)` across partition and disease counts. This greedy
rule uses counts only, never model scores, and replaces the earlier combination of
20 folds, which overshot training size in the presence of a large connected group.
Counts remain approximate because groups are indivisible; exact proportions are not
guaranteed. The original corpus, labels and metadata are not changed.

Saved partitions contain only schema-approved features and `label`. Use `model_inputs`
from `src.prepare_data` to separate features from the answer. IDs and metadata are
excluded. `split_audit.csv` maps each zero-based `row_in_split` to its original record
and symptom group; it is an audit/CV-group lookup, never an input to a model. Future
cross-validation must respect these same groups. `preparation.json` records the seed,
source-file hash, library versions, counts and unresolved limitations. Existing saved
partitions cannot be overwritten by this command; do not keep re-splitting after seeing
test performance.

The operational near-duplicate rule is **at most one differing symptom answer**.
Unanswered (`-1`) counts as a distinct answer, not a wildcard. No cases are deleted or
relabelled. The preview independently counts one-answer pairs crossing partitions and
stops if any remain. It reports the largest linked group's size, destination and disease composition;
review these and the partition counts before saving. Chains may create large groups
and make 70/15/15 or class balance harder to achieve. This is a stricter unseen-group
evaluation, not a claim that similar cases are invalid or necessarily copied. It is
an explicit numerical definition for the proposal's near-duplicate screening, not a
clinically validated similarity measure. Grouping does not change the symptom rules
used to generate the data and cannot establish real-patient accuracy.
A large connected group appears in only one partition. Matching the target disease
counts does not make the held-out set representative of the symptom patterns in that
group. Report this limitation alongside the grouping policy and evaluation results.

These are exploratory synthetic-data partitions. Numeric guideline bands, background
rates, atypical cases, label changes, missing answers and age/sex distributions contain
modelling assumptions; a format check does not verify them. Source verification and
independent evaluation cases remain unfinished. DDXPlus is also synthetic, according to
its [publishers](https://github.com/mila-iqia/ddxplus), so comparisons with it are not
real-patient validation. Final test performance must not guide changes to the generator
or model settings. No acceptance thresholds have been relaxed.

## First Logistic Regression baseline

After saving and reviewing the partitions, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_train.py" -v
.\.venv\Scripts\python.exe -m src.train
```

The tests fit tiny artificial fixtures only. The training command fits a fixed baseline
on `train.csv`, then reports accuracy, macro F1, per-class recall and a confusion matrix
on `validation.csv`. It never opens `test.csv` or the full source corpus. It checks
schema, values, class counts and the saved group audit; IDs, audit metadata and `label`
are not predictors. This is an initial experiment, not the planned model comparison
or final evaluation. No cross-validation, hyperparameter tuning, asymmetric class
weighting or probability calibration is performed yet. Group-aware CV must be added
before comparing candidate algorithms; the validation set is not a final test.

The pipeline converts all approved inputs to separate indicator categories. Symptom
answers -1, 0 and 1 mean unanswered, no and yes, respectively; none is treated as a
numeric severity score. Permitted categories come from the schema/config, not validation
observations. Age and sex are included as specified, although their simulation assumptions
remain provisional. Logistic Regression uses `solver="lbfgs"`, `C=1.0`, `max_iter=2000`,
no class weighting and the saved preparation seed. A convergence warning stops the run.

The command saves `pipeline.joblib`, `validation_report.json` and
`validation_confusion_matrix.csv` under `outputs/baseline_logistic_regression/`.
The report includes settings, input file hashes (not the final test file), feature
schema, library versions, preparation metadata and unresolved limitations. The encoder
and classifier are saved together so inference can use the same transformations.
Existing baseline output is never overwritten. Only load joblib artifacts you trust;
loading untrusted serialized Python objects can execute code. Keep the recorded library
versions when reusing the model.

A validation macro F1 above 0.95 is flagged as potential generator separability. All
acceptance thresholds below remain unchanged and apply to the eventual final evaluation,
not this preliminary run. Reported validation probabilities are not clinically calibrated.
Source verification, independent evaluation and the large connected-group limitation
remain unresolved. No original data or saved splits are modified by training.

## Acceptance thresholds

Committed to in the proposal. Do not loosen.

- Macro F1 >= 0.80 on the held-out test partition
- Per-class recall >= 0.90 for malaria and URTI/pneumonia
- Per-class recall >= 0.75 for the other three classes
- Expected calibration error <= 0.10
- Macro F1 > 0.95 => flag as separability artefact
