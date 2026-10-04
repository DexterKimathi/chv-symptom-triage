"""Evaluate the finalised model once on the held-out test set.

Opens test.csv for the first and only time. Refuses to run if a test report already
exists, so the test set cannot be reused to tune anything.

Reports:
  * accuracy, macro precision/recall/F1, per-class recall, confusion matrix, calibration
  * the full referral system on test: how often a condition is named, how often named
    results are right, and referral-level recall (did each patient get at least as urgent
    an instruction as their condition needs)
  * a mistake-tolerance test: answers flipped or left unanswered, then re-scored

Run:  python -m src.evaluate
"""

from __future__ import annotations

import json
import sys

import joblib
import numpy as np
import pandas as pd

from src.compare import evaluate
from src.config_io import ROOT, binary_items, load_config, load_schema
from src.finalise import named_mask
from src.prepare_data import model_inputs
from src.train import validate_partition

# Mirrors the referral levels seeded in the backend (scripts/seed.py).
REFERRAL_RANK = {"home_care_and_monitor": 0, "refer_routine": 1,
                 "refer_same_day": 2, "urgent": 3}
CONDITION_LEVEL = {"malaria": "refer_same_day", "typhoid": "refer_same_day",
                   "urti_pneumonia": "refer_same_day", "diarrhoeal": "home_care_and_monitor",
                   "uti": "refer_routine"}
WITHHELD_LEVEL = "refer_same_day"  # "refer for assessment"
MISTAKE_COUNTS = [1, 2, 3]


def load_test(schema, config) -> pd.DataFrame:
    directory = ROOT / "data" / "splits"
    with (directory / "preparation.json").open(encoding="utf-8") as fh:
        preparation = json.load(fh)
    frame = pd.read_csv(directory / "test.csv")
    validate_partition(frame, schema, config, "test")
    if len(frame) != int(preparation["counts"]["test"]["total"]):
        raise ValueError("test.csv row count differs from the saved preparation.")
    return frame


def aligned_probs(model, inputs, conditions):
    probs = model.predict_proba(inputs)
    return probs[:, [list(model.classes_).index(c) for c in conditions]]


def system_actions(inputs, probs, conditions, danger_signs, thresholds) -> np.ndarray:
    """The referral rank the deployed system gives each patient."""
    named = named_mask(probs, thresholds["low_confidence"], thresholds["proximity_margin"])
    predicted = np.asarray(conditions)[probs.argmax(axis=1)]
    ranks = np.array([REFERRAL_RANK[CONDITION_LEVEL[c]] for c in predicted])
    ranks[~named] = REFERRAL_RANK[WITHHELD_LEVEL]
    danger = (inputs[danger_signs] == 1).any(axis=1).to_numpy()
    ranks[danger] = REFERRAL_RANK["urgent"]
    return ranks


def perturb(inputs, symptoms, count, mode, unanswered, rng) -> pd.DataFrame:
    """Flip (yes<->no) or blank `count` answered symptoms per patient."""
    out = inputs.copy()
    values = out[symptoms].to_numpy().copy()
    for row in range(len(values)):
        answered = np.flatnonzero(values[row] != unanswered)
        if len(answered) == 0:
            continue
        chosen = rng.choice(answered, size=min(count, len(answered)), replace=False)
        values[row, chosen] = (1 - values[row, chosen]) if mode == "flip" else unanswered
    out[symptoms] = values
    return out


def main() -> int:
    out = ROOT / "results"
    if (out / "test_report.json").exists():
        print("A test report already exists. The test set is used once; nothing was run.",
              file=sys.stderr)
        return 1
    try:
        schema, config = load_schema(), load_config()
        bundle = joblib.load(out / "model.joblib")
        model, conditions = bundle["model"], bundle["conditions"]
        thresholds, danger_signs = bundle["thresholds"], bundle["danger_signs"]
        unanswered = int(bundle["unanswered_code"])
        symptoms = binary_items(schema)

        print(f"Opening the test set (first and only time). Model {bundle['model_version']}, "
              f"malaria weight {bundle['malaria_weight']}.\n")
        x_test, y_test = model_inputs(load_test(schema, config), schema)
        truth = y_test.to_numpy()

        result = evaluate("Logistic Regression v1.0", model, x_test, y_test, conditions)

        probs = aligned_probs(model, x_test, conditions)
        named = named_mask(probs, thresholds["low_confidence"], thresholds["proximity_margin"])
        predicted = np.asarray(conditions)[probs.argmax(axis=1)]
        actions = system_actions(x_test, probs, conditions, danger_signs, thresholds)
        required = np.array([REFERRAL_RANK[CONDITION_LEVEL[c]] for c in truth])
        referral_recall = {c: float((actions[truth == c] >= required[truth == c]).mean())
                           for c in conditions}

        rng = np.random.default_rng(int(bundle["seed"]))
        mistakes = []
        for mode in ("flip", "blank"):
            for count in MISTAKE_COUNTS:
                damaged = perturb(x_test, symptoms, count, mode, unanswered, rng)
                r = evaluate(f"{mode} {count}", model, damaged, y_test, conditions)
                mistakes.append({"mode": mode, "answers_changed": count,
                                 "macro_f1": r["macro_f1"],
                                 "malaria_recall": r["per_class_recall"]["malaria"],
                                 "urti_pneumonia_recall": r["per_class_recall"]["urti_pneumonia"]})

        report = {
            "evaluation_partition": "test",
            "opened_once": True,
            "model_version": bundle["model_version"],
            "malaria_weight": bundle["malaria_weight"],
            "thresholds": thresholds,
            "model_result": result,
            "system": {
                "named_share": float(named.mean()),
                "named_precision": float((predicted[named] == truth[named]).mean()),
                "danger_sign_share": float((x_test[danger_signs] == 1).any(axis=1).mean()),
                "referral_level_recall": referral_recall,
            },
            "mistake_tolerance": mistakes,
        }
        with (out / "test_report.json").open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        cm = pd.DataFrame(result["confusion_matrix"], index=conditions, columns=conditions)
        cm.index.name, cm.columns.name = "actual", "predicted"
        cm.to_csv(out / "test_confusion_matrix.csv")
        pd.DataFrame(mistakes).to_csv(out / "mistake_tolerance.csv", index=False,
                                      float_format="%.4f")

        r = result["per_class_recall"]
        print("TEST SET RESULTS")
        print(f"  accuracy {result['accuracy']:.3f}   macro F1 {result['macro_f1']:.3f}   "
              f"ECE {result['ece']:.3f}")
        print("  recall: " + "  ".join(f"{c} {r[c]:.3f}" for c in conditions))
        print("\n  floors: " + "  ".join(
            f"{c} {'pass' if ok else 'FAIL'}" for c, ok in result["recall_floors_met"].items())
            + f"  macro F1 {'pass' if result['macro_f1_floor_met'] else 'FAIL'}"
            + f"  ECE {'pass' if result['ece_ceiling_met'] else 'FAIL'}")
        print(f"\n  system names a condition for {named.mean():.1%} of patients; "
              f"named results correct {report['system']['named_precision']:.1%}")
        print("  referral-level recall: " + "  ".join(
            f"{c} {v:.3f}" for c, v in referral_recall.items()))
        print("\n  mistake tolerance (macro F1):")
        for m in mistakes:
            print(f"    {m['mode']:5s} {m['answers_changed']} answer(s): {m['macro_f1']:.3f}  "
                  f"(malaria recall {m['malaria_recall']:.3f})")
        print("\nSaved results/test_report.json, test_confusion_matrix.csv, mistake_tolerance.csv")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Evaluation stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
