"""Compare the generated respiratory records with DDXPlus; nothing is trained or changed.

DDXPlus (Tchango et al., 2022) is the only public corpus that holds any of the five target
conditions, and only the respiratory one. It is used here as an external reference, never
as training data (methodology 3.2.1).

Method, fixed before the comparison was run:

  * Reference. The released DDXPlus training partition (English release, figshare v15),
    filtered to PATHOLOGY "URTI" and "Pneumonia". The two are pooled as released, because
    the project carries them as one class, and also reported separately.
  * Mapping. Every schema item whose `ddxplus_equivalent` names a DDXPlus evidence code is
    counted as Yes when that code appears in the record's EVIDENCES list. All mapped codes
    are binary. Items marked NONE (no DDXPlus equivalent, such as the hydration and urinary
    items) are left out, and so are pain items, which DDXPlus records only as categorical
    location and intensity answers a checklist cannot collect (methodology 3.2.2).
  * Generated side. The urti_pneumonia records of the training partition: the share of
    answered records (Not asked excluded) that answered Yes. The test partition is not read.
  * Agreement rule. Each DDXPlus frequency is placed in the nearest ordinal band of
    generator.yaml (background 0.03, occasional 0.20, frequent 0.40, common 0.60,
    cardinal 0.85; the cut points are the midpoints). A cell AGREES when that band is the
    cell's own band, is ADJACENT when it is one band away and DIVERGES when it is two or
    more bands away. Divergent cells are flagged for revision against source. Model v1.0 is
    not retrained here: its settings were fixed and its test set has been used.

DDXPlus is itself synthetic, built from a proprietary knowledge base for an acute-care
setting, so agreement supports plausibility but is not real-patient validation.

Files needed in data/raw/ddxplus/ (not tracked; https://doi.org/10.6084/m9.figshare.20043374):
release_train_patients.zip and release_evidences.json.

Run:  python -m src.calibration
Writes results/ddxplus_comparison.csv and results/ddxplus_comparison.json.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile

import pandas as pd

from src.config_io import ROOT, load_config, load_schema

DDX = ROOT / "data" / "raw" / "ddxplus"
PATHOLOGIES = ["URTI", "Pneumonia"]
CLASS = "urti_pneumonia"
BAND_ORDER = ["background", "occasional", "frequent", "common", "cardinal"]
CODE = re.compile(r"'(E_\d+)(?:_@_[^']*)?'")


def evidence_codes(evidences: str) -> set[str]:
    """The evidence codes in one EVIDENCES cell, with any _@_value suffix removed."""
    return set(CODE.findall(evidences))


def nearest_band(p: float, bands: dict) -> str:
    """The ordinal band whose probability is closest to p."""
    return min(BAND_ORDER, key=lambda b: abs(bands[b] - p))


def verdict(cell_band: str, ref_band: str) -> str:
    gap = abs(BAND_ORDER.index(cell_band) - BAND_ORDER.index(ref_band))
    return "agrees" if gap == 0 else "adjacent" if gap == 1 else "diverges"


def load_reference(mapped: dict[str, str]) -> pd.DataFrame:
    """One row per DDXPlus URTI or Pneumonia record: pathology, age, sex and mapped items."""
    path = DDX / "release_train_patients.zip"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; see the module docstring for the source.")
    rows = []
    with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as fh:
        for chunk in pd.read_csv(fh, usecols=["AGE", "SEX", "PATHOLOGY", "EVIDENCES"], chunksize=200_000):
            chunk = chunk[chunk["PATHOLOGY"].isin(PATHOLOGIES)]
            for age, sex, pathology, ev in chunk.itertuples(index=False):
                codes = evidence_codes(ev)
                rows.append({"pathology": pathology, "age": age, "sex": sex,
                             **{item: int(code in codes) for item, code in mapped.items()}})
    return pd.DataFrame(rows)


def main() -> int:
    schema = load_schema()
    config = load_config()
    bands = config["bands"]
    evidences = json.loads((DDX / "release_evidences.json").read_text(encoding="utf-8"))

    mapped = {r.item_id: r.ddxplus_equivalent for r in schema.itertuples()
              if str(r.ddxplus_equivalent).startswith("E_")}
    for item, code in mapped.items():
        if evidences[code]["data_type"] != "B":
            raise ValueError(f"{item} maps to {code}, which is not a binary evidence")

    ref = load_reference(mapped)
    train = pd.read_csv(ROOT / "data" / "splits" / "train.csv")
    gen = train[train["label"] == CLASS]
    table = pd.read_csv(ROOT / config["output"]["table_path"])
    table = table[table["condition"] == CLASS].set_index("item_id")
    unanswered = int(config["unanswered"]["encoding"])

    out = []
    for item, code in mapped.items():
        answered = gen.loc[gen[item] != unanswered, item]
        cell = table.loc[item]
        pooled = ref[item].mean()
        ref_band = nearest_band(pooled, bands)
        out.append({
            "item_id": item,
            "ddxplus_code": code,
            "table_probability": float(cell["probability"]),
            "table_band": cell["band"],
            "table_status": cell["status"],
            "generated_yes_share": round(float(answered.mean()), 4),
            "ddxplus_urti": round(float(ref.loc[ref.pathology == "URTI", item].mean()), 4),
            "ddxplus_pneumonia": round(float(ref.loc[ref.pathology == "Pneumonia", item].mean()), 4),
            "ddxplus_pooled": round(float(pooled), 4),
            "ddxplus_band": ref_band,
            "verdict": verdict(cell["band"], ref_band),
            "difference_generated_minus_ddxplus": round(float(answered.mean() - pooled), 4),
        })
    result = pd.DataFrame(out)

    results = ROOT / "results"
    result.to_csv(results / "ddxplus_comparison.csv", index=False)
    zpath = DDX / "release_train_patients.zip"
    summary = {
        "reference": "DDXPlus English release, training partition (figshare v15)",
        "reference_file_sha256": hashlib.sha256(zpath.read_bytes()).hexdigest(),
        "pathologies": PATHOLOGIES,
        "reference_records": {p: int((ref.pathology == p).sum()) for p in PATHOLOGIES},
        "generated_partition": "train",
        "generated_records": int(len(gen)),
        "items_compared": len(result),
        "items_without_equivalent": int(len(schema[schema["data_type"] == "binary"]) - len(result)),
        "verdicts": result["verdict"].value_counts().to_dict(),
        "diverging_items": result.loc[result.verdict == "diverges", "item_id"].tolist(),
        "mean_absolute_difference": round(float(result["difference_generated_minus_ddxplus"].abs().mean()), 4),
        "reference_age": {"median": float(ref["age"].median()),
                          "under_15_share": round(float((ref["age"] < 15).mean()), 4)},
        "reference_sex_female_share": round(float((ref["sex"] == "F").mean()), 4),
        "config_hash_note": "Model v1.0 and the probability table are unchanged by this comparison.",
    }
    (results / "ddxplus_comparison.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    pd.set_option("display.width", 200)
    print(result.drop(columns=["ddxplus_code", "table_status"]).to_string(index=False))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
