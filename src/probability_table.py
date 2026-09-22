"""Build the symptom probability table.

Expands the compact clinical profiles into one row per (symptom, condition) pair,
so that every one of the 34 x 5 = 170 cells carries its own probability, status
and source. This is the artefact the proposal promises in 3.7.2.

Run:  python -m src.probability_table
"""

from __future__ import annotations

import sys

import pandas as pd

from src.config_io import (
    ROOT,
    binary_items,
    load_config,
    load_profiles,
    load_schema,
    validate_profiles,
)

BACKGROUND_BASIS = (
    "Not characteristic of this condition; assigned the declared uniform "
    "background rate (see generator.yaml)."
)


def build_table(schema: pd.DataFrame, profiles: dict, config: dict) -> pd.DataFrame:
    """Produce the long-format probability table, one row per cell."""
    bands = config["bands"]
    items = binary_items(schema)
    rows = []

    for condition in config["corpus"]["conditions"]:
        if condition not in profiles:
            raise ValueError(f"No clinical profile defined for condition '{condition}'")

        profile = profiles[condition]
        guideline = profile.get("guideline", "")
        default_status = profile.get("default_status", "TODO")
        sourced = profile.get("sourced") or {}
        notes = profile.get("notes") or {}

        # Invert the band lists so an item maps to its band.
        band_of = {}
        for band, listed in (profile.get("bands") or {}).items():
            for item in listed or []:
                band_of[item] = band

        for item in items:
            if item in sourced:
                entry = sourced[item]
                rows.append(
                    {
                        "item_id": item,
                        "condition": condition,
                        "probability": float(entry["value"]),
                        "tier": "published_frequency",
                        "band": "",
                        "status": entry.get("status", "SOURCED"),
                        "source": entry.get("source", ""),
                        "basis": entry.get("note", "Published frequency used as reported."),
                    }
                )
            elif item in band_of:
                band = band_of[item]
                rows.append(
                    {
                        "item_id": item,
                        "condition": condition,
                        "probability": float(bands[band]),
                        "tier": "guideline_ordinal",
                        "band": band,
                        "status": default_status,
                        "source": guideline,
                        "basis": notes.get(
                            item, f"Guideline places this symptom in the '{band}' band."
                        ),
                    }
                )
            else:
                rows.append(
                    {
                        "item_id": item,
                        "condition": condition,
                        "probability": float(bands["background"]),
                        "tier": "background_rule",
                        "band": "background",
                        "status": "BACKGROUND-RULE",
                        "source": "declared rule",
                        "basis": BACKGROUND_BASIS,
                    }
                )

    table = pd.DataFrame(rows)

    if (table["probability"] < 0).any() or (table["probability"] > 1).any():
        raise ValueError("Probability outside [0, 1] in the generated table")

    return table


def summarise(table: pd.DataFrame) -> str:
    """A short provenance summary. This is the honesty check on the table."""
    lines = ["Probability table provenance", "=" * 40, ""]
    lines.append(f"Total cells: {len(table)}")
    lines.append("")
    lines.append("By tier:")
    for tier, n in table["tier"].value_counts().items():
        lines.append(f"  {tier:22s} {n:4d}  ({n / len(table):5.1%})")
    lines.append("")
    lines.append("By status:")
    for status, n in table["status"].value_counts().items():
        lines.append(f"  {status:22s} {n:4d}  ({n / len(table):5.1%})")
    lines.append("")
    lines.append("Cells resting on a published frequency, by condition:")
    pub = table[table["tier"] == "published_frequency"]
    if pub.empty:
        lines.append("  none")
    else:
        for condition, n in pub["condition"].value_counts().items():
            lines.append(f"  {condition:22s} {n:4d}")
    return "\n".join(lines)


def main() -> int:
    config = load_config()
    schema = load_schema()
    profiles = load_profiles()

    problems = validate_profiles(profiles, binary_items(schema))
    if problems:
        print("Profile validation failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    table = build_table(schema, profiles, config)

    out = ROOT / config["output"]["table_path"]
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)

    print(summarise(table))
    print()
    print(f"Written: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
