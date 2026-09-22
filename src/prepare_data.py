"""Prepare grouped synthetic-data partitions without fitting a model.

Run python -m src.prepare_data to preview; add --write to save new partitions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from src.config_io import ROOT, binary_items, load_config, load_schema
from src.corpus_report import inspect_corpus


PARTITION_FRACTIONS = {"train": 0.70, "validation": 0.15, "test": 0.15}
AUDIT_COLUMNS = {
    "record_id", "generated_from", "is_atypical", "label_flipped",
    "n_unanswered", "n_symptoms_present", "symptom_group", "split", "row_in_split",
}


def model_inputs(
    corpus: pd.DataFrame, schema: pd.DataFrame
) -> tuple[pd.DataFrame, pd.Series]:
    """Select only schema-approved inputs; keep the answer separate."""
    features = schema["item_id"].tolist()
    if not features or len(features) != len(set(features)):
        raise ValueError("The feature list must be nonempty and unique.")
    forbidden = set(features) & (AUDIT_COLUMNS | {"label"})
    if forbidden:
        raise ValueError(f"Identifiers or answers cannot be features: {sorted(forbidden)}")
    return corpus.loc[:, features].copy(), corpus["label"].copy()


def symptom_groups(corpus: pd.DataFrame, symptoms: list[str]) -> pd.Series:
    """Keep exact matches and chains of one-answer differences together.

    After collapsing exact matches, omit each symptom in turn to find patterns
    matching everywhere else. Connect each match to a representative, then use
    connected components to keep every linked chain in one indivisible group.
    Unanswered is a distinct answer, not a wildcard. Labels are never compared.
    """
    if not symptoms or corpus.empty:
        raise ValueError("Grouping requires records and symptom columns.")
    answers = corpus.loc[:, symptoms]
    if answers.isna().any().any():
        raise ValueError("Use the unanswered code rather than empty symptom cells.")
    pattern_codes, _ = pd.factorize(pd.MultiIndex.from_frame(answers), sort=False)
    patterns = answers.drop_duplicates().reset_index(drop=True)
    positions = np.arange(len(patterns))
    sources = []
    targets = []
    for omitted in symptoms:
        remaining = [symptom for symptom in symptoms if symptom != omitted]
        codes = (
            patterns.groupby(remaining, sort=False).ngroup()
            if remaining else pd.Series(0, index=patterns.index)
        )
        representatives = pd.Series(positions).groupby(codes).transform("min").to_numpy()
        linked = representatives != positions
        sources.append(positions[linked])
        targets.append(representatives[linked])
    source_positions = np.concatenate(sources)
    target_positions = np.concatenate(targets)
    graph = coo_matrix(
        (np.ones(len(source_positions), dtype=np.int8), (source_positions, target_positions)),
        shape=(len(patterns), len(patterns)),
    ).tocsr()
    _, components = connected_components(graph, directed=False)
    return pd.Series(components[pattern_codes], index=corpus.index, name="symptom_group")


def grouped_split(corpus: pd.DataFrame, schema: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Allocate intact groups directly toward per-disease 70/15/15 targets.

    Largest groups go first; the seed orders equal-size groups. Each placement
    minimises the increase in sum((count - target)**2 / target) over partition
    and disease counts. This greedy allocation uses no model predictions and
    cannot guarantee exact proportions when groups are indivisible.
    """
    symptoms = binary_items(schema)
    if not symptoms:
        raise ValueError("No symptom columns were defined.")
    if corpus["record_id"].isna().any() or not corpus["record_id"].is_unique:
        raise ValueError("Each record needs a unique, nonempty record_id for the audit.")
    _, labels = model_inputs(corpus, schema)
    groups = symptom_groups(corpus, symptoms)
    partition_count = len(PARTITION_FRACTIONS)
    groups_per_label = pd.DataFrame({"label": labels, "group": groups}).groupby(
        "label"
    )["group"].nunique()
    if groups_per_label.empty or groups_per_label.lt(partition_count).any():
        raise ValueError(
            f"Each disease needs at least {partition_count} distinct symptom groups. "
            f"After linking one-answer matches: {groups.nunique()} groups; largest has "
            f"{int(groups.value_counts().max())} records. Review grouping before splitting."
        )

    group_table = pd.crosstab(groups, labels)
    group_counts = group_table.to_numpy(dtype=float)
    fractions = np.array(list(PARTITION_FRACTIONS.values()))
    targets = fractions[:, None] * group_counts.sum(axis=0)
    allocated = np.zeros_like(targets)
    group_sizes = group_counts.sum(axis=1)
    shuffled = np.random.default_rng(seed).permutation(len(group_table))
    order = shuffled[np.argsort(-group_sizes[shuffled], kind="stable")]
    assignments = np.empty(len(group_table), dtype=object)
    partition_names = list(PARTITION_FRACTIONS)
    for group_position in order:
        counts = group_counts[group_position]
        costs = (
            ((allocated + counts - targets) ** 2 - (allocated - targets) ** 2) / targets
        ).sum(axis=1)
        destination = int(np.argmin(costs))
        allocated[destination] += counts
        assignments[group_position] = partition_names[destination]
    partitions = groups.map(pd.Series(assignments, index=group_table.index)).to_numpy()

    manifest = pd.DataFrame(
        {
            "record_id": corpus["record_id"].to_numpy(),
            "symptom_group": groups.to_numpy(),
            "split": partitions,
        }
    )
    manifest["row_in_split"] = manifest.groupby("split", sort=False).cumcount()
    if not manifest["split"].isin(PARTITION_FRACTIONS).all():
        raise ValueError("Some rows were not assigned a partition.")
    if manifest.groupby("symptom_group")["split"].nunique().gt(1).any():
        raise ValueError("Linked symptom groups crossed partition boundaries.")
    for name in PARTITION_FRACTIONS:
        observed = set(labels.iloc[np.flatnonzero(partitions == name)])
        if observed != set(labels):
            raise ValueError(f"Partition '{name}' does not contain every disease.")
    return manifest


def one_answer_apart(
    corpus: pd.DataFrame, symptoms: list[str], manifest: pd.DataFrame
) -> dict[str, int]:
    """Count unique pattern pairs differing in exactly one recorded answer.

    Dropping each column in turn exposes such pairs without building an
    all-pairs distance matrix. Exact matches are collapsed first. Unanswered
    is a distinct answer, not a wildcard. Age, sex and labels are not compared.
    """
    patterns = corpus.loc[:, symptoms].reset_index(drop=True).copy()
    patterns["_partition"] = manifest["split"].to_numpy()
    patterns = patterns.drop_duplicates(subset=symptoms).reset_index(drop=True)
    pair_count = 0
    crossing_count = 0
    involved = np.zeros(len(patterns), dtype=bool)
    for omitted in symptoms:
        remaining = [symptom for symptom in symptoms if symptom != omitted]
        if remaining:
            group_codes = patterns.groupby(remaining, sort=False).ngroup()
        else:
            group_codes = pd.Series(0, index=patterns.index)
        counts = group_codes.value_counts()
        pairs = int((counts * (counts - 1) // 2).sum())
        within_counts = pd.DataFrame(
            {"group": group_codes, "partition": patterns["_partition"]}
        ).groupby(["group", "partition"]).size()
        within_pairs = int((within_counts * (within_counts - 1) // 2).sum())
        pair_count += pairs
        crossing_count += pairs - within_pairs
        involved |= group_codes.map(counts).gt(1).to_numpy()
    return {
        "unique_pattern_pairs": pair_count,
        "patterns_with_a_neighbour": int(involved.sum()),
        "pairs_across_partitions": crossing_count,
    }


def conflict_audit(
    corpus: pd.DataFrame, schema: pd.DataFrame, meta_path: Path
) -> dict[str, int | str]:
    """Use metadata only to explain conflicts, never to change labels or splits."""
    features, labels = model_inputs(corpus, schema)
    labelled = features.assign(label=labels)
    conflicts = labelled.groupby(list(features), dropna=False)["label"].transform(
        "nunique"
    ).gt(1)
    result: dict[str, int | str] = {
        "identical_input_groups_with_different_labels": int(
            features.loc[conflicts].drop_duplicates().shape[0]
        ),
        "rows_in_conflicting_groups": int(conflicts.sum()),
    }
    if not meta_path.exists():
        result["metadata_status"] = "Not found; causes of conflicting labels not checked."
        return result

    meta = pd.read_csv(meta_path)
    if not meta["record_id"].is_unique or set(meta["record_id"]) != set(corpus["record_id"]):
        raise ValueError("Metadata IDs do not match the corpus; do not use a stale audit file.")
    aligned = meta.set_index("record_id").loc[corpus["record_id"]].reset_index(drop=True)
    flipped = aligned["label_flipped"]
    if not flipped.isin([True, False]).all():
        raise ValueError("Metadata label_flipped must contain Boolean values.")
    if aligned["generated_from"].isna().any():
        raise ValueError("Metadata contains empty original disease labels.")
    changed = aligned["generated_from"].ne(labels.reset_index(drop=True))
    if not changed.eq(flipped).all():
        raise ValueError("Recorded labels disagree with the metadata's label-change flags.")
    result["flagged_label_changes_in_conflicting_rows"] = int(
        flipped.loc[conflicts.to_numpy()].sum()
    )
    result["metadata_status"] = "Checked for label changes; no labels corrected or removed."
    return result


def write_partitions(
    output: Path, corpus: pd.DataFrame, schema: pd.DataFrame,
    manifest: pd.DataFrame, summary: dict,
) -> None:
    """Write a new split directory; never replace an existing experiment."""
    features, labels = model_inputs(corpus, schema)
    output.mkdir(parents=True, exist_ok=False)
    for name in PARTITION_FRACTIONS:
        positions = np.flatnonzero(manifest["split"].eq(name).to_numpy())
        partition = features.iloc[positions].copy()
        partition["label"] = labels.iloc[positions].to_numpy()
        partition.to_csv(output / f"{name}.csv", index=False)
    manifest.to_csv(output / "split_audit.csv", index=False)
    with (output / "preparation.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--write", action="store_true", help="Save new partitions after checks.")
    args = parser.parse_args()
    try:
        config = load_config()
        schema = load_schema()
        seed = int(config["seed"]) if args.seed is None else args.seed
        source = ROOT / config["output"]["corpus_path"]
        output = ROOT / "data" / "splits"
        if args.write and output.exists():
            raise ValueError("data/splits already exists. Existing partitions will not be overwritten.")
        corpus = pd.read_csv(source).sort_values("record_id").reset_index(drop=True)
        _, problems = inspect_corpus(corpus, schema, config)
        if problems:
            raise ValueError("Data checks failed: " + "; ".join(problems))
        print("Preparing grouped partitions; no model will be trained.", flush=True)
        manifest = grouped_split(corpus, schema, seed)
        print("Checking cases differing in one symptom answer...", flush=True)
        neighbours = one_answer_apart(corpus, binary_items(schema), manifest)
        if neighbours["pairs_across_partitions"]:
            raise ValueError("One-answer-apart cases crossed partitions; no files will be saved.")
        group_sizes = manifest["symptom_group"].value_counts()
        group_summary = {
            "number_of_groups": int(len(group_sizes)),
            "largest_group_records": int(group_sizes.max()),
            "largest_group_partition": str(manifest.loc[
                manifest["symptom_group"].eq(group_sizes.idxmax()), "split"
            ].iloc[0]),
            "largest_group_by_disease": corpus.loc[
                manifest["symptom_group"].eq(group_sizes.idxmax()), "label"
            ].value_counts().to_dict(),
        }
        conflicts = conflict_audit(corpus, schema, source.with_name("corpus_meta.csv"))
        counts = pd.crosstab(manifest["split"], corpus["label"]).reindex(
            index=list(PARTITION_FRACTIONS), columns=config["corpus"]["conditions"], fill_value=0
        )
        counts["total"] = counts.sum(axis=1)
        warnings = [
            "All records are synthetic; these are exploratory partitions, not clinical validation.",
            "Symptom probabilities and random age/sex distributions remain assumptions under review.",
            "No independent evaluation cases have been added by this command.",
            "Near-match policy: at most one different recorded symptom answer, ignoring age/sex/label.",
            "Linked chains stay together, even when their endpoints differ by more than one answer.",
            "This stricter split tests unseen symptom groups; similar cases are not necessarily errors.",
            "Review group sizes and disease counts before saving; 70/15/15 remains approximate.",
            "A large group appears in only one partition; balanced class counts do not remove this limitation.",
            "This numerical near-match rule does not establish clinical similarity or safety.",
            "Do not tune settings or the generator using final test performance.",
            "Future cross-validation must also keep symptom groups together using split_audit.csv.",
            "Do not load split_audit.csv or preparation.json as model inputs.",
        ]
        summary = {
            "seed": seed,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "features": schema["item_id"].tolist(),
            "label": "label",
            "grouping": "Connected components of exact or one-answer symptom matches; age, sex and labels ignored.",
            "max_different_symptom_answers": 1,
            "group_summary": group_summary,
            "method": "Largest-group-first greedy allocation towards per-disease targets; seeded size ties; minimise increase in sum((count-target)^2/target).",
            "target_fractions": PARTITION_FRACTIONS,
            "counts": json.loads(counts.to_json(orient="index")),
            "near_matches": neighbours,
            "conflicting_labels": conflicts,
            "versions": {"numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__},
            "warnings": warnings,
        }
        print(f"\nSeed: {seed}")
        print(counts.to_string())
        print("\nPercentages (approximate because matching cases stay together):")
        for name in PARTITION_FRACTIONS:
            print(f"  {name:12s} {100 * int(counts.loc[name, 'total']) / len(corpus):.2f}%")
        print(f"\nLinked symptom groups: {group_summary['number_of_groups']:,}")
        print(f"Largest linked group: {group_summary['largest_group_records']:,} records")
        print(f"Largest group's partition: {group_summary['largest_group_partition']}")
        print(f"Largest group's disease counts: {group_summary['largest_group_by_disease']}")
        print("Identical or one-answer-apart symptom patterns crossing partitions: 0 (checked)")
        print("Training inputs: schema-approved fields only; no IDs or metadata.")
        print("\nOne-answer-apart comparison (unique symptom patterns, not patient pairs):")
        for name, value in neighbours.items():
            print(f"  {name}: {value:,}")
        print("\nConflicting-label audit:")
        for name, value in conflicts.items():
            print(f"  {name}: {value}")
        print("\nStill important:")
        for warning in warnings:
            print(f"  - {warning}")
        if args.write:
            write_partitions(output, corpus, schema, manifest, summary)
            print("\nSaved train.csv, validation.csv and test.csv in data/splits.")
            print("Saved a separate split_audit.csv and preparation.json for reproducibility.")
        else:
            print("\nPREVIEW ONLY: no files written. Add --write to save after reviewing this output.")
        print("Original data and labels unchanged. No model trained.")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Preparation stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())