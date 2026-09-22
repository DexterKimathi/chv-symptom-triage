"""Inspect the existing synthetic corpus without changing it or training a model.

Run: python -m src.corpus_report
"""

from __future__ import annotations

import sys

import pandas as pd

from src.config_io import ROOT, binary_items, load_config, load_schema
from src.probability_table import summarise


def inspect_corpus(
    corpus: pd.DataFrame, schema: pd.DataFrame, config: dict
) -> tuple[str, list[str]]:
    """Return a plain-language report and any data-format problems found."""
    symptoms = binary_items(schema)
    features = schema["item_id"].tolist()
    conditions = config["corpus"]["conditions"]
    unanswered = int(config["unanswered"]["encoding"])
    expected_columns = {"record_id", "label", *features}
    problems = []
    lines = [
        "SYNTHETIC DATA CHECK",
        "=" * 55,
        f"Records: {len(corpus):,}",
        f"Symptom questions: {len(symptoms)}",
        "record_id is excluded from all input comparisons below.",
        "corpus_meta.csv is not loaded or used as model input.",
    ]

    missing = expected_columns - set(corpus.columns)
    unexpected = set(corpus.columns) - expected_columns
    if missing:
        problems.append(f"Missing columns: {sorted(missing)}")
    if unexpected:
        problems.append(f"Unexpected columns: {sorted(unexpected)}")
    if not corpus.columns.is_unique:
        problems.append("The corpus contains repeated column names.")
    if corpus.empty:
        problems.append("The corpus has no records.")
    if problems:
        return "\n".join(lines), problems

    empty_cells = int(corpus.isna().sum().sum())
    lines.append(f"Empty cells: {empty_cells:,}")
    if empty_cells:
        problems.append(
            f"Found {empty_cells} empty cells; unanswered symptoms should use {unanswered}."
        )
    if not corpus["record_id"].is_unique:
        problems.append("record_id is repeated; it must uniquely identify each record.")

    expected_rows = int(config["corpus"]["records_per_class"]) * len(conditions)
    if len(corpus) != expected_rows:
        problems.append(
            f"Current configuration expects {expected_rows:,} records, "
            f"but the saved corpus has {len(corpus):,}."
        )

    lines.extend(["", "Recorded disease labels:"])
    counts = corpus["label"].value_counts()
    for condition in conditions:
        count = int(counts.get(condition, 0))
        lines.append(f"  {condition:20s} {count:6,d}")
        if count == 0:
            problems.append(f"No records have the label '{condition}'.")
    if not corpus["label"].isin(conditions).all():
        problems.append("Some labels are empty or outside the five configured classes.")
    lines.append("Small differences between class counts are expected after label changes.")

    invalid_symptoms = [
        symptom
        for symptom in symptoms
        if not corpus[symptom].isin([0, 1, unanswered]).all()
    ]
    if invalid_symptoms:
        problems.append(
            f"Symptom columns with values outside 0, 1, {unanswered}: {invalid_symptoms}"
        )
    for covariate, settings in config["covariates"].items():
        if not corpus[covariate].isin(settings["values"]).all():
            problems.append(f"Invalid or empty values in '{covariate}'.")

    if problems:
        return "\n".join(lines), problems

    for rule in config.get("constraints", []):
        dependent = rule["dependent"]
        antecedents = rule["requires_any"]
        unsupported = corpus[dependent].eq(1) & ~corpus[antecedents].eq(1).any(axis=1)
        if unsupported.any():
            problems.append(
                f"{int(unsupported.sum())} records violate the configured rule for "
                f"'{dependent}'."
            )
        unmasked = (
            corpus[antecedents].eq(unanswered).any(axis=1)
            & corpus[dependent].ne(unanswered)
        )
        if unmasked.any():
            problems.append(
                f"{int(unmasked.sum())} records violate the configured unanswered-item "
                f"rule for '{dependent}'."
            )

    lines.extend(["", "Symptom answers across all records:"])
    for value, description in [(1, "Yes"), (0, "No"), (unanswered, "Unanswered")]:
        count = int(corpus[symptoms].eq(value).sum().sum())
        lines.append(f"  {description:20s} {count:8,d}")

    repeated_inputs = int(corpus.duplicated(subset=features, keep=False).sum())
    repeated_symptoms = int(corpus.duplicated(subset=symptoms, keep=False).sum())
    labels_per_input = corpus.groupby(features, dropna=False)["label"].nunique()
    conflicting_groups = int(labels_per_input.gt(1).sum())
    lines.extend(
        [
            "",
            "Repeated cases (disease labels and record IDs excluded from matching):",
            f"  Rows sharing all inputs, including age and sex: {repeated_inputs:,}",
            f"  Rows sharing symptom answers alone:            {repeated_symptoms:,}",
            f"  Identical full-input groups with different labels: {conflicting_groups:,}",
            "  Row counts include every member of each repeated group.",
            "  Matching answers can occur naturally in this simulation.",
            "  These counts are warnings, not instructions to delete records.",
            "  Repeated cases must be considered before dividing data for training.",
            "",
            "Limits of this check:",
            "  Near-duplicate cases and class separability have not been assessed.",
            "  A format check does not confirm clinical accuracy.",
            "  Probability assumptions and independent evaluation remain unfinished.",
            "  Future training must explicitly exclude record_id and all metadata.",
        ]
    )
    return "\n".join(lines), problems


def main() -> int:
    try:
        config = load_config()
        schema = load_schema()
        corpus = pd.read_csv(ROOT / config["output"]["corpus_path"])
        report, problems = inspect_corpus(corpus, schema, config)
        print(report)
        if problems:
            print("\nDATA CHECK FAILED:")
            for problem in problems:
                print(f"  - {problem}")
            return 1

        table = pd.read_csv(ROOT / config["output"]["table_path"])
        print()
        print(summarise(table))
        print("\nThese source counts describe the current table, not verified medical evidence.")
        print("TODO and VERIFY entries remain provisional; do not treat them as ground truth.")
        print("\nDATA FORMAT CHECKS PASSED. This is not approval for clinical use.")
        print("No data was changed, no split was made, and no model was trained.")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Could not complete the data check: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())