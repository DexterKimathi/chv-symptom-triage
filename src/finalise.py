"""Finalise the model: malaria reweighting and referral thresholds, on validation only.

Both selection rules are fixed here, before any result is seen:

  Reweighting. Train Logistic Regression with malaria examples weighted 1, 1.25, 1.5, 2,
  2.5 and 3 times. Choose the smallest weight that reaches malaria recall 0.90 while every
  other proposal floor still holds (other recall floors, macro F1 >= 0.80). If none
  reaches 0.90, choose the weight with the highest malaria recall that keeps the other
  floors, and report the shortfall.

  Thresholds. A condition is named only when its probability is at least `low_confidence`
  and leads the runner-up by at least `proximity_margin`. Choose the pair that names a
  condition for the largest share of patients while named results are correct at least
  90% of the time. Ties go to the lower thresholds.

The test set is not opened. Run src.evaluate afterwards, once.

Run:  python -m src.finalise
"""

from __future__ import annotations

import hashlib
import json
import sys
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from src.compare import evaluate, with_classifier
from src.config_io import ROOT, load_config, load_schema
from src.prepare_data import model_inputs
from src.train import BASELINE_SETTINGS, load_development_data

MALARIA_WEIGHTS = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
MALARIA_TARGET = 0.90
NAMED_PRECISION_TARGET = 0.90
LOW_CONFIDENCE_GRID = [round(x, 2) for x in np.arange(0.30, 0.96, 0.05)]
PROXIMITY_GRID = [round(x, 2) for x in np.arange(0.0, 0.41, 0.05)]


def other_floors_met(result: dict) -> bool:
    floors = dict(result["recall_floors_met"])
    floors.pop("malaria")
    return all(floors.values()) and result["macro_f1_floor_met"]


def choose_weight(trials: list[dict]) -> tuple[dict, bool]:
    """Apply the declared reweighting rule. Returns (chosen trial, target reached)."""
    eligible = [t for t in trials if other_floors_met(t["result"])]
    if not eligible:
        raise ValueError("No weight keeps the other proposal floors; nothing can be chosen.")
    reaching = [t for t in eligible if t["result"]["per_class_recall"]["malaria"] >= MALARIA_TARGET]
    if reaching:
        return min(reaching, key=lambda t: t["weight"]), True
    return max(eligible, key=lambda t: (t["result"]["per_class_recall"]["malaria"], -t["weight"])), False


def named_mask(probs: np.ndarray, low_confidence: float, proximity_margin: float) -> np.ndarray:
    ordered = np.sort(probs, axis=1)
    return (ordered[:, -1] >= low_confidence) & (ordered[:, -1] - ordered[:, -2] >= proximity_margin)


def choose_thresholds(probs: np.ndarray, correct: np.ndarray) -> dict:
    """Apply the declared threshold rule over the grid."""
    candidates = []
    for low in LOW_CONFIDENCE_GRID:
        for margin in PROXIMITY_GRID:
            named = named_mask(probs, low, margin)
            if not named.any():
                continue
            precision = float(correct[named].mean())
            if precision >= NAMED_PRECISION_TARGET:
                candidates.append({"low_confidence": low, "proximity_margin": margin,
                                   "named_share": float(named.mean()),
                                   "named_precision": precision})
    if not candidates:
        raise ValueError("No threshold pair reaches the named-result precision target.")
    return max(candidates, key=lambda c: (c["named_share"], -c["low_confidence"], -c["proximity_margin"]))


def main() -> int:
    try:
        schema, config = load_schema(), load_config()
        conditions = config["corpus"]["conditions"]
        frames, preparation = load_development_data(ROOT / "data" / "splits", schema, config)
        seed = int(preparation["seed"])
        x_train, y_train = model_inputs(frames["train"], schema)
        x_val, y_val = model_inputs(frames["validation"], schema)
        print("Training and validation loaded. The test set is not opened.\n")

        trials = []
        for weight in MALARIA_WEIGHTS:
            model = with_classifier(schema, config, seed,
                                    LogisticRegression(**BASELINE_SETTINGS, random_state=seed))
            sample_weight = np.where(y_train.to_numpy() == "malaria", weight, 1.0)
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                model.fit(x_train, y_train, classifier__sample_weight=sample_weight)
            result = evaluate(f"LR malaria x{weight}", model, x_val, y_val, conditions)
            trials.append({"weight": weight, "model": model, "result": result})
            r = result["per_class_recall"]
            print(f"  weight {weight:<4}  malaria {r['malaria']:.3f}  typhoid {r['typhoid']:.3f}  "
                  f"macro F1 {result['macro_f1']:.3f}  ECE {result['ece']:.3f}  "
                  f"other floors {'met' if other_floors_met(result) else 'FAILED'}")

        chosen, reached = choose_weight(trials)
        model, result = chosen["model"], chosen["result"]
        print(f"\nChosen weight: {chosen['weight']}  "
              f"({'malaria target reached' if reached else 'malaria target NOT reached; best available'})")

        probs = model.predict_proba(x_val)
        probs = probs[:, [list(model.classes_).index(c) for c in conditions]]
        predicted = np.asarray(conditions)[probs.argmax(axis=1)]
        correct = predicted == y_val.to_numpy()
        thresholds = choose_thresholds(probs, correct)
        print(f"Thresholds: name a condition when probability >= {thresholds['low_confidence']} "
              f"and lead >= {thresholds['proximity_margin']}")
        print(f"  on validation: {thresholds['named_share']:.1%} of patients get a named condition, "
              f"correct {thresholds['named_precision']:.1%} of the time")

        out = ROOT / "results"
        config_hash = hashlib.sha256(b"".join((ROOT / p).read_bytes() for p in [
            "config/feature_schema.csv", "config/symptom_probability_table.csv",
            "config/generator.yaml"])).hexdigest()
        bundle = {
            "model": model,
            "model_name": "Logistic Regression",
            "model_version": "v1.0",
            "malaria_weight": chosen["weight"],
            "thresholds": {"low_confidence": thresholds["low_confidence"],
                           "proximity_margin": thresholds["proximity_margin"]},
            "feature_order": schema["item_id"].tolist(),
            "danger_signs": schema.loc[schema["is_danger_sign"].astype(bool), "item_id"].tolist(),
            "conditions": conditions,
            "unanswered_code": int(config["unanswered"]["encoding"]),
            "config_hash": config_hash,
            "seed": seed,
            "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__,
                         "pandas": pd.__version__},
        }
        joblib.dump(bundle, out / "model.joblib")

        report = {
            "evaluation_partition": "validation",
            "test_set_opened": False,
            "reweighting_rule": __doc__.split("Reweighting.")[1].split("Thresholds.")[0].strip(),
            "threshold_rule": __doc__.split("Thresholds.")[1].split("The test set")[0].strip(),
            "trials": [{"weight": t["weight"], **{k: v for k, v in t["result"].items()
                                                  if k != "confusion_matrix"}} for t in trials],
            "chosen_weight": chosen["weight"],
            "malaria_target_reached": reached,
            "chosen_validation_result": result,
            "thresholds": thresholds,
            "config_hash": config_hash,
        }
        with (out / "final_selection.json").open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        pd.DataFrame([{"malaria_weight": t["weight"], "macro_f1": t["result"]["macro_f1"],
                       "ece": t["result"]["ece"],
                       **{f"recall_{c}": t["result"]["per_class_recall"][c] for c in conditions},
                       "other_floors_met": other_floors_met(t["result"])} for t in trials]
                     ).to_csv(out / "reweighting_trials.csv", index=False, float_format="%.4f")

        print(f"\nSaved results/model.joblib (v1.0), final_selection.json, reweighting_trials.csv")
        return 0
    except (OSError, ValueError, KeyError, ConvergenceWarning) as error:
        print(f"Finalisation stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
