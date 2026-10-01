"""Fit the first Logistic Regression baseline; never open the final test data.

Run: python -m src.train
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
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.config_io import ROOT, binary_items, load_config, load_schema
from src.prepare_data import PARTITION_FRACTIONS, model_inputs


BASELINE_SETTINGS = {"solver": "lbfgs", "C": 1.0, "max_iter": 2000}


def validate_partition(
    frame: pd.DataFrame, schema: pd.DataFrame, config: dict, name: str
) -> None:
    """Reject malformed inputs, extra columns and unrecognised answers."""
    expected = schema["item_id"].tolist() + ["label"]
    if list(frame.columns) != expected:
        raise ValueError(f"{name}: columns must be the approved inputs followed by label.")
    if frame.empty or frame.isna().any().any():
        raise ValueError(f"{name}: data must be nonempty with no blank cells.")
    features, labels = model_inputs(frame, schema)
    if set(labels) != set(config["corpus"]["conditions"]):
        raise ValueError(f"{name}: expected all five configured disease labels, and no others.")
    allowed_answers = [0, 1, int(config["unanswered"]["encoding"])]
    for symptom in binary_items(schema):
        if not features[symptom].isin(allowed_answers).all():
            raise ValueError(f"{name}: invalid answers in {symptom}.")
    for covariate, settings in config["covariates"].items():
        if not features[covariate].isin(settings["values"]).all():
            raise ValueError(f"{name}: invalid answers in {covariate}.")


def load_development_data(
    directory: Path, schema: pd.DataFrame, config: dict
) -> tuple[dict[str, pd.DataFrame], dict]:
    """Read training/validation data and the audit, not test.csv or the source corpus."""
    with (directory / "preparation.json").open(encoding="utf-8") as handle:
        preparation = json.load(handle)
    if preparation["features"] != schema["item_id"].tolist() or preparation["label"] != "label":
        raise ValueError("The current schema does not match the saved preparation.")

    audit = pd.read_csv(directory / "split_audit.csv")
    if set(audit.columns) != {"record_id", "symptom_group", "split", "row_in_split"}:
        raise ValueError("The split audit has unexpected columns.")
    if audit.isna().any().any() or not audit["record_id"].is_unique:
        raise ValueError("The split audit has missing values or repeated record IDs.")
    if set(audit["split"]) != set(PARTITION_FRACTIONS):
        raise ValueError("The split audit must describe train, validation and test.")
    if audit.groupby("symptom_group")["split"].nunique().gt(1).any():
        raise ValueError("A symptom group crosses partitions in the saved audit.")

    frames = {}
    for name in PARTITION_FRACTIONS:
        expected_count = int(preparation["counts"][name]["total"])
        rows = audit.loc[audit["split"].eq(name)].sort_values("row_in_split")
        if rows["row_in_split"].tolist() != list(range(expected_count)):
            raise ValueError(f"{name}: audit row positions do not match the saved count.")
        if name == "test":
            continue
        frame = pd.read_csv(directory / f"{name}.csv")
        validate_partition(frame, schema, config, name)
        if len(frame) != expected_count:
            raise ValueError(f"{name}: row count differs from the saved preparation.")
        for condition in config["corpus"]["conditions"]:
            expected = int(preparation["counts"][name][condition])
            if int(frame["label"].eq(condition).sum()) != expected:
                raise ValueError(f"{name}: {condition} count differs from the saved preparation.")
        frames[name] = frame
    return frames, preparation


def build_pipeline(schema: pd.DataFrame, config: dict, seed: int) -> Pipeline:
    """Encode yes, no and unanswered as separate categories, then classify."""
    features = schema["item_id"].tolist()
    symptoms = set(binary_items(schema))
    symptom_values = sorted([0, 1, int(config["unanswered"]["encoding"])])
    categories = [
        symptom_values if feature in symptoms else config["covariates"][feature]["values"]
        for feature in features
    ]
    encoder = ColumnTransformer(
        [("answers", OneHotEncoder(categories=categories, handle_unknown="error"), features)],
        remainder="drop",
    )
    return Pipeline(
        [
            ("encode", encoder),
            ("classifier", LogisticRegression(**BASELINE_SETTINGS, random_state=seed)),
        ]
    )


def fit_baseline(
    training: pd.DataFrame, validation: pd.DataFrame,
    schema: pd.DataFrame, config: dict, seed: int,
) -> tuple[Pipeline, dict]:
    """Fit only on training rows and calculate preliminary validation metrics."""
    validate_partition(training, schema, config, "train")
    validate_partition(validation, schema, config, "validation")
    training_inputs, training_labels = model_inputs(training, schema)
    validation_inputs, validation_labels = model_inputs(validation, schema)
    pipeline = build_pipeline(schema, config, seed)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        pipeline.fit(training_inputs, training_labels)
    predictions = pipeline.predict(validation_inputs)
    conditions = config["corpus"]["conditions"]
    macro_f1 = float(f1_score(validation_labels, predictions, labels=conditions, average="macro"))
    limitations = [
        "Synthetic-data baseline only; not evidence of clinical diagnostic accuracy.",
        "Validation results are preliminary, not final held-out test results.",
        "No hyperparameter search, candidate comparison or cross-validation has run yet.",
        "No probability calibration has been performed; do not present scores as clinical confidence.",
        "Probability-source verification and independent evaluation cases remain unfinished.",
        "Age and sex are included as specified, but their generated distributions are provisional.",
    ]
    if macro_f1 > 0.95:
        limitations.append(
            "WARNING: macro F1 > 0.95 triggers the proposal's generator-separability flag, not a success claim."
        )
    report = {
        "model": "Logistic Regression",
        "stage": "first_fixed_settings_baseline",
        "evaluation_partition": "validation",
        "training_rows": len(training),
        "validation_rows": len(validation),
        "seed": seed,
        "settings": {**BASELINE_SETTINGS, "class_weight": None},
        "input_features": training_inputs.columns.tolist(),
        "encoding": "One-hot categories from the declared schema/config; -1 is not treated as no.",
        "encoded_features": pipeline.named_steps["encode"].get_feature_names_out().tolist(),
        "iterations": pipeline.named_steps["classifier"].n_iter_.tolist(),
        "accuracy": float(accuracy_score(validation_labels, predictions)),
        "macro_f1": macro_f1,
        "weighted_f1": float(f1_score(validation_labels, predictions, average="weighted")),
        "per_class": classification_report(
            validation_labels, predictions, labels=conditions, output_dict=True, zero_division=0
        ),
        "confusion_matrix_labels": conditions,
        "confusion_matrix": confusion_matrix(validation_labels, predictions, labels=conditions).tolist(),
        "final_test_evaluated": False,
        "calibrated": False,
        "warnings": limitations,
        "versions": {"numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__, "joblib": joblib.__version__},
    }
    return pipeline, report


def save_baseline(output: Path, pipeline: Pipeline, report: dict) -> None:
    """Save the encoder and classifier together without replacing an existing run."""
    output.mkdir(parents=True, exist_ok=False)
    joblib.dump(pipeline, output / "pipeline.joblib")
    with (output / "validation_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    conditions = report["confusion_matrix_labels"]
    matrix = pd.DataFrame(report["confusion_matrix"], index=conditions, columns=conditions)
    matrix.index.name = "actual_disease"
    matrix.columns.name = "predicted_disease"
    matrix.to_csv(output / "validation_confusion_matrix.csv")


def main() -> int:
    try:
        output = ROOT / "outputs" / "baseline_logistic_regression"
        if output.exists():
            raise ValueError("A baseline output directory already exists; nothing will be overwritten.")
        schema = load_schema()
        config = load_config()
        directory = ROOT / "data" / "splits"
        print("Checking saved training/validation data and split audit...", flush=True)
        frames, preparation = load_development_data(directory, schema, config)
        print(f"Learning from {len(frames['train']):,} training examples...", flush=True)
        print("The final test data will not be opened.", flush=True)
        pipeline, report = fit_baseline(
            frames["train"], frames["validation"], schema, config, int(preparation["seed"])
        )
        report["preparation"] = preparation
        report["input_file_sha256"] = {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ["train.csv", "validation.csv", "split_audit.csv", "preparation.json"]
        }
        report["feature_schema"] = schema.to_dict(orient="records")
        report["allowed_covariates"] = config["covariates"]
        print("\nLOGISTIC REGRESSION: VALIDATION RESULTS")
        print(f"Examples checked: {report['validation_rows']:,}")
        print(f"Accuracy (overall correct): {report['accuracy']:.3f}")
        print(f"Macro F1 (equal weight to each disease): {report['macro_f1']:.3f}")
        print("\nRecall: share of each disease's examples correctly identified")
        for condition in config["corpus"]["conditions"]:
            print(f"  {condition:20s} {report['per_class'][condition]['recall']:.3f}")
        print("\nMistakes table: rows = actual labels; columns = predicted labels")
        print(pd.DataFrame(
            report["confusion_matrix"], index=report["confusion_matrix_labels"],
            columns=report["confusion_matrix_labels"],
        ).to_string())
        print("\nInterpretation limits:")
        for warning in report["warnings"] + preparation.get("warnings", []):
            print(f"  - {warning}")
        save_baseline(output, pipeline, report)
        print("\nSaved the encoder + model, validation report and confusion matrix to:")
        print(output)
        print("Original data and splits unchanged. Final test data not opened.")
        return 0
    except (OSError, ValueError, KeyError, ConvergenceWarning) as error:
        print(f"Baseline stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())