# Results

Published evaluation results and the v1.0 model. These are committed, unlike `outputs/`,
which is scratch space the pipeline rewrites on every run.

| File | Written by | What it holds |
|---|---|---|
| `validation_report.json`, `validation_comparison.csv`, `validation_confusion_*.csv` | `src.compare` | Naive Bayes reference, LR, RF and XGBoost on validation |
| `reweighting_trials.csv`, `final_selection.json` | `src.finalise` | malaria weight trials, chosen weight and referral thresholds |
| `model.joblib` | `src.finalise` | model v1.0 with its feature order, thresholds and config hash |
| `test_report.json`, `test_confusion_matrix.csv`, `mistake_tolerance.csv` | `src.evaluate` | the single test evaluation, the referral system and the answer-error check |
| `question_frequencies.json`, `adaptive_validation.csv`, `adaptive_test.json` | `src.adaptive` | adaptive questioning: answer frequencies, stop threshold and its test check |
| `ddxplus_comparison.csv`, `ddxplus_comparison.json` | `src.calibration` | generated respiratory frequencies against DDXPlus URTI and Pneumonia |

Only load `model.joblib` from this repository: loading an untrusted joblib file can run code.
