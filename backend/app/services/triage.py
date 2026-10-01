"""Turn a prediction into what the CHV is told.

The rules run in a fixed order and the first that applies decides the headline:

  1. Any danger sign answered yes  -> refer urgently now, whatever the model says.
  2. Top probability below the low-confidence threshold -> do not name a condition.
  3. Top two too close together    -> do not pick between them (proposal 1.5.2).
  4. Otherwise                     -> name the likely condition.

The model still runs in every case and its ranking is always recorded, so a danger-sign
referral keeps a full audit trail. No result is ever presented as a diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass

DISCLAIMER = (
    "This is decision support, not a diagnosis. It suggests a likely illness from the "
    "symptoms entered and can be wrong. Always seek care from a qualified health worker, "
    "and refer immediately if the patient gets worse."
)

URGENT_GUIDANCE = (
    "Danger sign present. Refer to the nearest health facility immediately. Do not wait "
    "to treat at home. If the patient cannot drink, keep offering fluids on the way."
)

UNCLEAR_GUIDANCE = (
    "The symptoms do not clearly point to one condition. Refer to a health facility for "
    "assessment and testing."
)


@dataclass
class Decision:
    outcome: str
    headline: str
    referral_level: str
    guidance: str


def decide(
    danger_signs_present: list[str],
    ranked: list[tuple[str, float]],
    names: dict[str, str],
    guidance_by_condition: dict[str, tuple[str, str]],
    low_confidence: float,
    proximity_margin: float,
) -> Decision:
    """`guidance_by_condition` maps a condition code to (referral_level, guidance)."""
    if danger_signs_present:
        return Decision("urgent_referral", "Refer urgently now", "urgent", URGENT_GUIDANCE)

    top_code, top_p = ranked[0]
    if top_p < low_confidence:
        return Decision(
            "low_confidence",
            "Symptoms do not clearly match one condition. Refer for assessment.",
            "refer_for_assessment", UNCLEAR_GUIDANCE,
        )

    if len(ranked) > 1 and top_p - ranked[1][1] < proximity_margin:
        second = names.get(ranked[1][0], ranked[1][0])
        return Decision(
            "too_close_to_call",
            f"Too close to call between {names.get(top_code, top_code)} and {second}. "
            "Refer for assessment.",
            "refer_for_assessment", UNCLEAR_GUIDANCE,
        )

    level, guidance = guidance_by_condition[top_code]
    return Decision("likely_condition", f"Likely: {names.get(top_code, top_code)}", level, guidance)
