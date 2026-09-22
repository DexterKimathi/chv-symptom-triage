"""Loading and validation of the configuration artefacts.

Three files define everything the generator does:

    config/feature_schema.csv        the 34 binary items a CHV can observe
    config/symptom_profiles.yaml     which items matter for each condition
    config/generator.yaml            all numeric parameters

Nothing in this package hardcodes a clinical value. If a number is not in one of
those files, it does not exist.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

# Repository root, resolved relative to this file so the scripts work from anywhere.
ROOT = Path(__file__).resolve().parent.parent

SCHEMA_PATH = ROOT / "config" / "feature_schema.csv"
PROFILES_PATH = ROOT / "config" / "symptom_profiles.yaml"
CONFIG_PATH = ROOT / "config" / "generator.yaml"


def load_config(path: Path | None = None) -> dict:
    """Read generator.yaml."""
    with open(path or CONFIG_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_profiles(path: Path | None = None) -> dict:
    """Read symptom_profiles.yaml."""
    with open(path or PROFILES_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_schema(path: Path | None = None) -> pd.DataFrame:
    """Read feature_schema.csv and check it is internally consistent."""
    schema = pd.read_csv(path or SCHEMA_PATH)

    required = {"item_id", "category", "data_type", "chv_question", "ddxplus_equivalent"}
    missing = required - set(schema.columns)
    if missing:
        raise ValueError(f"feature_schema.csv is missing columns: {sorted(missing)}")

    if not schema["item_id"].is_unique:
        duplicated = schema.loc[schema["item_id"].duplicated(), "item_id"].tolist()
        raise ValueError(f"Duplicate item_id in feature_schema.csv: {duplicated}")

    return schema


def binary_items(schema: pd.DataFrame) -> list[str]:
    """The symptom items. Covariates (age band, sex) are handled separately."""
    return schema.loc[schema["data_type"] == "binary", "item_id"].tolist()


def validate_profiles(profiles: dict, items: list[str]) -> list[str]:
    """Check every item named in the profiles actually exists in the schema.

    Returns a list of human-readable problems; empty means the profiles are clean.
    A typo in a YAML item name would otherwise pass silently and quietly drop a
    symptom from a condition's profile, so this check matters.
    """
    problems: list[str] = []
    known = set(items)

    for condition, profile in profiles.items():
        for item in profile.get("sourced", {}):
            if item not in known:
                problems.append(f"{condition}: sourced item '{item}' is not in the schema")

        for band, listed in (profile.get("bands") or {}).items():
            for item in listed or []:
                if item not in known:
                    problems.append(
                        f"{condition}: band '{band}' names '{item}', which is not in the schema"
                    )

        # An item should not be both sourced and assigned a band; the sourced
        # value would silently win and the band would be misleading.
        banded = {i for listed in (profile.get("bands") or {}).values() for i in (listed or [])}
        overlap = banded & set(profile.get("sourced", {}))
        for item in sorted(overlap):
            problems.append(f"{condition}: '{item}' appears in both sourced and bands")

    return problems
