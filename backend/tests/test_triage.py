"""The referral rules in isolation, with no model and no database."""

from app.services.triage import decide

NAMES = {"malaria": "Malaria", "typhoid": "Typhoid fever", "uti": "Urinary tract infection"}
GUIDANCE = {c: ("refer_same_day", f"guidance for {c}") for c in NAMES}


def run(danger=(), ranked=(("malaria", 0.9), ("typhoid", 0.05), ("uti", 0.05))):
    return decide(list(danger), list(ranked), NAMES, GUIDANCE,
                  low_confidence=0.5, proximity_margin=0.1)


def test_confident_clear_result_is_named():
    d = run()
    assert d.outcome == "likely_condition"
    assert d.headline == "Likely: Malaria"
    assert d.guidance == "guidance for malaria"


def test_danger_sign_wins_even_over_a_confident_model():
    d = run(danger=["convulsions"])
    assert d.outcome == "urgent_referral"
    assert d.referral_level == "urgent"


def test_low_confidence_does_not_name_a_condition():
    d = run(ranked=[("malaria", 0.40), ("typhoid", 0.35), ("uti", 0.25)])
    assert d.outcome == "low_confidence"
    assert "Malaria" not in d.headline


def test_close_top_two_are_not_split():
    d = run(ranked=[("malaria", 0.52), ("typhoid", 0.46), ("uti", 0.02)])
    assert d.outcome == "too_close_to_call"
    assert "Malaria" in d.headline and "Typhoid fever" in d.headline


def test_danger_sign_checked_before_low_confidence():
    d = run(danger=["lethargy_reduced_alertness"], ranked=[("malaria", 0.3), ("uti", 0.3)])
    assert d.outcome == "urgent_referral"
