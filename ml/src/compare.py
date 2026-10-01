"""Compare four models on the validation partition; never open the test data.

Models:
  * Naive Bayes reference, computed directly from the probability table. Under the
    generator's independent-sampling assumption this is close to the best any model
    can do, so it is the yardstick the others are read against.
  * Logistic Regression (the existing baseline settings)
  * Random Forest
  * XGBoost

All trainable models see identical one-hot inputs. Settings are fixed in advance; no
tuning is done. The winner is chosen on validation macro F1 among the three trainable
candidates, and exported for the backend. The final test evaluation is a separate
step (src.evaluate) so the test set is opened exactly once.

Run:  python -m src.compare
"""

from __future__ import annotations

import hashlib
import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

from src.config_io import ROOT, binary_items, load_config, load_schema
from src.prepare_data import model_inputs
from src.train import BASELINE_SETTINGS, build_pipeline, load_development_data

RF_SETTINGS = {"n_estimators": 300, "min_samples_leaf": 1, "n_jobs": -1}
XGB_SETTINGS = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.1,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "objective": "multi:softprob",
    "eval_metric": "mlogloss",
    "n_jobs": -1,
}

# Acceptance thresholds committed to in the proposal. Never loosened.
HIGH_SEVERITY = {"malaria", "urti_pneumonia"}
RECALL_FLOOR_HIGH = 0.90
RECALL_FLOOR_OTHER = 0.75
MACRO_F1_FLOOR = 0.80
ECE_CEILING = 0.10
SEPARABILITY_FLAG = 0.95


# --------------------------------------------------------------------------- #
# Naive Bayes reference
# --------------------------------------------------------------------------- #
class TableNaiveBayes:
    """Classify with the probability table itself, fitting nothing.

    For each condition c the score is log P(c) + sum_j log P(x_j | c), where
    P(x_j = 1 | c) is the table value. An unanswered item contributes nothing:
    under missing-at-random masking the unknown answer is marginalised out.
    Age band and sex are generated independently of the condition, so they carry
    no information and are left out.
    """

    def __init__(self, table: pd.DataFrame, items: list[str], conditions: list[str],
                 unanswered: int):
        wide = table.pivot(index="condition", columns="item_id", values="probability")
        wide = wide.reindex(index=conditions, columns=items)
        p = np.clip(wide.to_numpy(dtype=float), 1e-6, 1 - 1e-6)
        self.log_yes = np.log(p)
        self.log_no = np.log1p(-p)
        self.items = items
        self.classes_ = np.array(conditions)
        self.unanswered = unanswered

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        x = frame[self.items].to_numpy()
        yes = (x == 1).astype(float)
        no = (x == 0).astype(float)
        # Uniform prior: the corpus is balanced by construction.
        scores = yes @ self.log_yes.T + no @ self.log_no.T
        scores -= scores.max(axis=1, keepdims=True)
        probs = np.exp(scores)
        return probs / probs.sum(axis=1, keepdims=True)

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return self.classes_[self.predict_proba(frame).argmax(axis=1)]


# --------------------------------------------------------------------------- #
# XGBoost needs integer labels; wrap it so it behaves like the sklearn models.
# --------------------------------------------------------------------------- #
class LabelledXGB:
    """XGBoost pipeline that accepts and returns condition names."""

    def __init__(self, pipeline: Pipeline, conditions: list[str]):
        self.pipeline = pipeline
        self.encoder = LabelEncoder().fit(conditions)
        self.classes_ = self.encoder.classes_

    def fit(self, x, y):
        self.pipeline.fit(x, self.encoder.transform(y))
        return self

    def predict_proba(self, x):
        return self.pipeline.predict_proba(x)

    def predict(self, x):
        return self.encoder.inverse_transform(self.pipeline.predict(x))


def with_classifier(schema, config, seed, classifier) -> Pipeline:
    """Same one-hot encoder as the baseline, different classifier."""
    pipeline = build_pipeline(schema, config, seed)
    pipeline.steps[-1] = ("classifier", classifier)
    return pipeline


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def expected_calibration_error(y_true, probs, classes, bins=10) -> float:
    """Top-label ECE: how far stated confidence is from observed accuracy."""
    confidence = probs.max(axis=1)
    predicted = np.asarray(classes)[probs.argmax(axis=1)]
    correct = (predicted == np.asarray(y_true)).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        in_bin = (confidence > lo) & (confidence <= hi)
        if in_bin.any():
            ece += in_bin.mean() * abs(correct[in_bin].mean() - confidence[in_bin].mean())
    return float(ece)


def brier(y_true, probs, classes) -> float:
    """Multiclass Brier score: mean squared error of the probability vector."""
    onehot = (np.asarray(y_true)[:, None] == np.asarray(classes)[None, :]).astype(float)
    return float(((probs - onehot) ** 2).sum(axis=1).mean())


def evaluate(name, model, inputs, labels, conditions) -> dict:
    probs = model.predict_proba(inputs)
    # Align probability columns with the configured condition order.
    order = [list(model.classes_).index(c) for c in conditions]
    probs = probs[:, order]
    predicted = np.asarray(conditions)[probs.argmax(axis=1)]

    recall = recall_score(labels, predicted, labels=conditions, average=None, zero_division=0)
    per_class_recall = {c: float(r) for c, r in zip(conditions, recall)}
    floors_met = {
        c: per_class_recall[c] >= (RECALL_FLOOR_HIGH if c in HIGH_SEVERITY else RECALL_FLOOR_OTHER)
        for c in conditions
    }
    macro_f1 = float(f1_score(labels, predicted, labels=conditions, average="macro"))
    ece = expected_calibration_error(labels, probs, conditions)

    return {
        "model": name,
        "accuracy": float(accuracy_score(labels, predicted)),
        "macro_precision": float(precision_score(labels, predicted, labels=conditions,
                                                 average="macro", zero_division=0)),
        "macro_recall": float(recall_score(labels, predicted, labels=conditions,
                                           average="macro", zero_division=0)),
        "macro_f1": macro_f1,
        # log_loss reads probability columns in sorted label order, not config order.
        "log_loss": float(log_loss(
            labels, probs[:, [conditions.index(c) for c in sorted(conditions)]],
            labels=sorted(conditions))),
        "brier": brier(labels, probs, conditions),
        "ece": ece,
        "per_class_recall": per_class_recall,
        "recall_floors_met": floors_met,
        "all_floors_met": all(floors_met.values()),
        "macro_f1_floor_met": macro_f1 >= MACRO_F1_FLOOR,
        "ece_ceiling_met": ece <= ECE_CEILING,
        "separability_flag": macro_f1 > SEPARABILITY_FLAG,
        "confusion_matrix": confusion_matrix(labels, predicted, labels=conditions).tolist(),
    }


# --------------------------------------------------------------------------- #
def main() -> int:
    try:
        schema = load_schema()
        config = load_config()
        conditions = config["corpus"]["conditions"]
        items = binary_items(schema)
        directory = ROOT / "data" / "splits"

        print("Loading training and validation data (the test set is not opened)...")
        frames, preparation = load_development_data(directory, schema, config)
        seed = int(preparation["seed"])
        x_train, y_train = model_inputs(frames["train"], schema)
        x_val, y_val = model_inputs(frames["validation"], schema)

        table = pd.read_csv(ROOT / config["output"]["table_path"])
        candidates = {
            "Logistic Regression": with_classifier(
                schema, config, seed, LogisticRegression(**BASELINE_SETTINGS, random_state=seed)),
            "Random Forest": with_classifier(
                schema, config, seed, RandomForestClassifier(**RF_SETTINGS, random_state=seed)),
            "XGBoost": LabelledXGB(
                with_classifier(schema, config, seed,
                                xgboost.XGBClassifier(**XGB_SETTINGS, random_state=seed)),
                conditions),
        }

        results = []
        reference = TableNaiveBayes(table, items, conditions, int(config["unanswered"]["encoding"]))
        print("Scoring the Naive Bayes reference (computed from the table, nothing fitted)...")
        results.append(evaluate("Naive Bayes (table reference)", reference, x_val, y_val, conditions))

        fitted = {}
        for name, model in candidates.items():
            print(f"Fitting {name} on {len(x_train):,} training rows...")
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                model.fit(x_train, y_train)
            fitted[name] = model
            results.append(evaluate(name, model, x_val, y_val, conditions))

        # Selection rule, declared before any test data is seen: highest validation
        # macro F1 among the trainable candidates.
        trainable = [r for r in results if r["model"] in candidates]
        winner = max(trainable, key=lambda r: r["macro_f1"])
        chosen = winner["model"]

        out = ROOT / "results"
        out.mkdir(exist_ok=True)

        rows = []
        for r in results:
            row = {k: r[k] for k in ["model", "accuracy", "macro_precision", "macro_recall",
                                     "macro_f1", "log_loss", "brier", "ece"]}
            row.update({f"recall_{c}": r["per_class_recall"][c] for c in conditions})
            row["all_recall_floors_met"] = r["all_floors_met"]
            row["separability_flag"] = r["separability_flag"]
            rows.append(row)
        table_out = pd.DataFrame(rows)
        table_out.to_csv(out / "validation_comparison.csv", index=False, float_format="%.4f")

        for r in results:
            slug = r["model"].split(" (")[0].lower().replace(" ", "_")
            cm = pd.DataFrame(r["confusion_matrix"], index=conditions, columns=conditions)
            cm.index.name, cm.columns.name = "actual", "predicted"
            cm.to_csv(out / f"validation_confusion_{slug}.csv")

        # Export the chosen model for the backend, with the exact feature order and
        # the hash of the data configuration it was trained on.
        config_hash = hashlib.sha256(
            b"".join((ROOT / p).read_bytes() for p in [
                "config/feature_schema.csv", "config/symptom_probability_table.csv",
                "config/generator.yaml"])
        ).hexdigest()
        bundle = {
            "model": fitted[chosen],
            "model_name": chosen,
            "feature_order": schema["item_id"].tolist(),
            "danger_signs": schema.loc[schema["is_danger_sign"].astype(bool), "item_id"].tolist(),
            "conditions": conditions,
            "unanswered_code": int(config["unanswered"]["encoding"]),
            "config_hash": config_hash,
            "seed": seed,
            "versions": {"sklearn": sklearn.__version__, "xgboost": xgboost.__version__,
                         "numpy": np.__version__, "pandas": pd.__version__},
        }
        joblib.dump(bundle, out / "model.joblib")

        report = {
            "evaluation_partition": "validation",
            "test_set_opened": False,
            "selection_rule": "highest validation macro F1 among the trainable candidates",
            "chosen_model": chosen,
            "config_hash": config_hash,
            "settings": {"logistic_regression": BASELINE_SETTINGS, "random_forest": RF_SETTINGS,
                         "xgboost": XGB_SETTINGS},
            "results": results,
        }
        with (out / "validation_report.json").open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

        # ---- console summary --------------------------------------------- #
        pd.set_option("display.width", 200)
        print("\nVALIDATION COMPARISON (test set not opened)")
        print(table_out[["model", "accuracy", "macro_f1", "brier", "ece"]]
              .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        print("\nRecall by condition (floor: 0.90 malaria and urti_pneumonia, 0.75 others)")
        print(table_out[["model"] + [f"recall_{c}" for c in conditions]]
              .rename(columns=lambda c: c.replace("recall_", ""))
              .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        ref = results[0]["macro_f1"]
        print(f"\nNaive Bayes reference macro F1: {ref:.3f}")
        for r in trainable:
            print(f"  {r['model']:22s} {r['macro_f1']:.3f}  ({r['macro_f1'] - ref:+.3f} vs reference)")
        print(f"\nChosen on validation: {chosen}")
        if any(r["separability_flag"] for r in results):
            print("FLAG: a macro F1 above 0.95 indicates generator separability, not success.")
        print(f"\nSaved to {out.relative_to(ROOT)}/: comparison table, confusion matrices, "
              "report, and model.joblib")
        return 0

    except (OSError, ValueError, KeyError, ConvergenceWarning) as error:
        print(f"Comparison stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
