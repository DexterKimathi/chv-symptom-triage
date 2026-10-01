"""Synthetic corpus generator.

Implements the sampling procedure described in proposal 3.2.1:

  * independent Bernoulli sampling of every symptom at its tabulated rate
  * an atypical-presentation rate drawn from a widened distribution
  * a stated label-noise rate
  * unanswered items encoded as a distinct third state (3.2.2)
  * definitional constraints applied as post-draw repairs

Every parameter comes from config/generator.yaml. The only command-line argument
that changes the output is --seed, so the corpus is reproducible from the script
and its configuration alone.

Run:  python -m src.generator --seed 42
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.config_io import ROOT, binary_items, load_config, load_schema


def probability_matrix(table: pd.DataFrame, items: list[str], conditions: list[str]) -> np.ndarray:
    """Reshape the long table into a (condition, item) matrix of probabilities."""
    wide = table.pivot(index="condition", columns="item_id", values="probability")
    # Reindex explicitly so row and column order always match the caller's lists,
    # rather than relying on whatever order pivot happened to produce.
    wide = wide.reindex(index=conditions, columns=items)

    if wide.isna().to_numpy().any():
        missing = [
            (c, i)
            for c in conditions
            for i in items
            if pd.isna(wide.loc[c, i])
        ]
        raise ValueError(f"Probability table has no entry for: {missing[:5]}")

    return wide.to_numpy(dtype=float)


def widen(probs: np.ndarray, alpha: float) -> np.ndarray:
    """Pull probabilities toward 0.5 to model an atypical presentation.

    alpha = 0 leaves the distribution unchanged; alpha = 1 makes every symptom a
    coin flip. The effect is to blur the condition's signature without inventing
    a second, unsourced probability column.
    """
    return probs + alpha * (0.5 - probs)


def apply_constraints(draws: np.ndarray, items: list[str], constraints: list[dict]) -> np.ndarray:
    """Enforce definitional dependencies between items.

    If a dependent item was drawn as present but none of its antecedents were,
    the dependent item is reset to absent. These rules follow from the item
    definitions and the IMCI severity hierarchy, so they introduce no new
    parameter.
    """
    index = {item: n for n, item in enumerate(items)}

    for rule in constraints or []:
        dependent = rule["dependent"]
        if dependent not in index:
            continue

        antecedents = [index[a] for a in rule.get("requires_any", []) if a in index]
        if not antecedents:
            continue

        supported = draws[:, antecedents].any(axis=1)
        column = index[dependent]
        draws[:, column] = np.where(supported, draws[:, column], 0)

    return draws


def generate(config: dict, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate the corpus.

    Returns (corpus, meta). The corpus holds only features and the observed
    label. Diagnostics that must never be trained on - which condition a record
    was actually drawn from, whether it was atypical, whether its label was
    flipped - live in the separate meta frame.
    """
    rng = np.random.default_rng(seed)

    schema = load_schema()
    items = binary_items(schema)
    conditions = config["corpus"]["conditions"]
    per_class = int(config["corpus"]["records_per_class"])

    table = pd.read_csv(ROOT / config["output"]["table_path"])
    probs = probability_matrix(table, items, conditions)

    atypical_rate = float(config["atypical"]["rate"])
    alpha = float(config["atypical"]["alpha"])
    noise_rate = float(config["label_noise"]["rate"])
    unanswered_rate = float(config["unanswered"]["rate"])
    unanswered_code = int(config["unanswered"]["encoding"])
    constraints = config.get("constraints", [])

    n_total = per_class * len(conditions)
    n_items = len(items)

    # Which condition each record is drawn from: balanced by construction.
    source_condition = np.repeat(np.arange(len(conditions)), per_class)

    # Atypical records are drawn from the widened distribution instead.
    is_atypical = rng.random(n_total) < atypical_rate
    base = probs[source_condition]
    widened = widen(base, alpha)
    effective = np.where(is_atypical[:, None], widened, base)

    # The sampling step itself.
    draws = (rng.random((n_total, n_items)) < effective).astype(np.int8)

    # Repair definitional dependencies before anything is masked.
    draws = apply_constraints(draws, items, constraints)

    # Unanswered items are a third state, not a recorded negative.
    unanswered_mask = rng.random((n_total, n_items)) < unanswered_rate

    # Keep the masking coherent. A volunteer who skipped the question about a
    # parent symptom cannot have recorded its dependent, so an unanswered
    # antecedent propagates the mask to the item that depends on it. Without
    # this, the corpus contains records reading "productive cough: yes,
    # cough: not asked", which no real checklist would produce.
    index = {item: n for n, item in enumerate(items)}
    for rule in constraints or []:
        dependent = rule["dependent"]
        if dependent not in index:
            continue
        antecedents = [index[a] for a in rule.get("requires_any", []) if a in index]
        if not antecedents:
            continue
        any_unanswered = unanswered_mask[:, antecedents].any(axis=1)
        unanswered_mask[:, index[dependent]] |= any_unanswered

    features = np.where(unanswered_mask, unanswered_code, draws).astype(np.int8)

    # Label noise: keep the symptom vector, change the recorded diagnosis.
    label_index = source_condition.copy()
    noised = rng.random(n_total) < noise_rate
    if noised.any():
        # Choose uniformly among the other classes so noise does not favour one.
        offsets = rng.integers(1, len(conditions), size=int(noised.sum()))
        label_index[noised] = (label_index[noised] + offsets) % len(conditions)

    # Covariates.
    age_cfg = config["covariates"]["age_band"]
    sex_cfg = config["covariates"]["sex"]
    age = rng.choice(age_cfg["values"], size=n_total, p=age_cfg["weights"])
    sex = rng.choice(sex_cfg["values"], size=n_total, p=sex_cfg["weights"])

    record_id = np.arange(n_total)

    corpus = pd.DataFrame(features, columns=items)
    corpus.insert(0, "record_id", record_id)
    corpus["age_band"] = age
    corpus["sex"] = sex
    corpus["label"] = [conditions[i] for i in label_index]

    meta = pd.DataFrame(
        {
            "record_id": record_id,
            "generated_from": [conditions[i] for i in source_condition],
            "is_atypical": is_atypical,
            "label_flipped": noised,
            "n_unanswered": unanswered_mask.sum(axis=1),
            "n_symptoms_present": (draws == 1).sum(axis=1),
        }
    )

    # Shuffle so class order carries no information.
    order = rng.permutation(n_total)
    corpus = corpus.iloc[order].reset_index(drop=True)
    meta = meta.set_index("record_id").loc[corpus["record_id"]].reset_index()

    return corpus, meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the synthetic symptom corpus.")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed. Defaults to the value in config/generator.yaml.",
    )
    args = parser.parse_args()

    config = load_config()
    seed = args.seed if args.seed is not None else int(config["seed"])

    corpus, meta = generate(config, seed)

    out = ROOT / config["output"]["corpus_path"]
    out.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_csv(out, index=False)
    meta.to_csv(out.with_name("corpus_meta.csv"), index=False)

    print(f"seed                : {seed}")
    print(f"records             : {len(corpus)}")
    print(f"atypical records    : {int(meta['is_atypical'].sum())} "
          f"({meta['is_atypical'].mean():.1%})")
    print(f"labels flipped      : {int(meta['label_flipped'].sum())} "
          f"({meta['label_flipped'].mean():.1%})")
    print(f"mean unanswered/rec : {meta['n_unanswered'].mean():.2f}")
    print()
    print("class balance (observed labels):")
    for label, n in corpus["label"].value_counts().sort_index().items():
        print(f"  {label:18s} {n:6d}")
    print()
    print(f"Written: {out.relative_to(ROOT)}")
    print(f"Written: {out.with_name('corpus_meta.csv').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
