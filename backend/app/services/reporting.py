"""Figures for the admin dashboard.

Everything here counts what the app told volunteers. A "likely condition" is the model's
suggestion for referral, not a confirmed diagnosis, so these figures show where to look,
not how many people have a disease.

Location is the area saved on the volunteer's account. No device location is collected.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone

from app.models import Assessment, Condition, User

# Days are counted as Kenyan days, so "today" matches what the volunteer sees.
KENYA = timezone(timedelta(hours=3))

# The order is fixed so each condition keeps the same colour on every chart.
CONDITION_ORDER = ["malaria", "typhoid", "urti_pneumonia", "diarrhoeal", "uti"]
UNCLEAR = "unclear"
URGENT = "urgent"

# An area is flagged when a result reaches this many cases and at least this multiple of the
# period before. A deliberately simple rule that can be checked by hand.
RISING_MIN_CASES = 5
RISING_FACTOR = 2

NO_AREA = "Area not set"

# Volunteers created by scripts/sample_data.py, so the dashboard can say sample data is shown.
SAMPLE_PHONE_PREFIX = "0799000"


def category(assessment: Assessment) -> str:
    """Which single bucket an assessment is counted in."""
    if assessment.outcome == "urgent_referral":
        return URGENT
    if assessment.outcome == "likely_condition" and assessment.results:
        return assessment.results[0]["code"]
    return UNCLEAR


def local_date(moment: datetime) -> date:
    # Timestamps are written in UTC; SQLite hands them back without a timezone.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(KENYA).date()


def _area_name(user: User | None) -> str:
    name = " ".join((user.area or "").split()) if user else ""
    return name or NO_AREA


def _zero_counts(codes: Sequence[str]) -> dict[str, int]:
    return {code: 0 for code in codes}


def build_dashboard(
    assessments: Sequence[Assessment],
    users: Sequence[User],
    conditions: Sequence[Condition],
    days: int,
    now: datetime,
) -> dict:
    """The last `days` Kenyan days up to and including today, compared with the `days` before."""
    names = {c.code: c.name for c in conditions}
    codes = [c for c in CONDITION_ORDER if c in names]
    categories = codes + [UNCLEAR, URGENT]

    today = local_date(now)
    start = today - timedelta(days=days - 1)
    previous_start = start - timedelta(days=days)

    users_by_id = {u.id: u for u in users}
    volunteers = [u for u in users if u.role == "chv"]

    current: list[Assessment] = []
    previous: list[Assessment] = []
    all_time: dict[int, list[datetime]] = {}
    for a in assessments:
        all_time.setdefault(a.chv_id, []).append(a.created_at)
        day = local_date(a.created_at)
        if start <= day <= today:
            current.append(a)
        elif previous_start <= day < start:
            previous.append(a)

    # --- totals by category ------------------------------------------------ #
    now_counts = _zero_counts(categories)
    before_counts = _zero_counts(categories)
    for a in current:
        now_counts[category(a)] += 1
    for a in previous:
        before_counts[category(a)] += 1

    # --- trend: one bucket a day for a week, otherwise one a week ----------- #
    size = 1 if days <= 7 else 7
    trend = [
        {"start": start + timedelta(days=i), "end": start + timedelta(days=min(i + size, days) - 1),
         "counts": _zero_counts(categories)}
        for i in range(0, days, size)
    ]
    for a in current:
        trend[(local_date(a.created_at) - start).days // size]["counts"][category(a)] += 1

    # --- areas, matched without regard to capitals or double spaces --------- #
    areas: dict[str, dict] = {}

    def area_row(user: User | None) -> dict:
        name = _area_name(user)
        return areas.setdefault(name.casefold(), {
            "area": name, "volunteers": 0, "assessments": 0, "previous_assessments": 0,
            "counts": _zero_counts(categories), "previous_counts": _zero_counts(categories),
        })

    for u in volunteers:
        area_row(u)["volunteers"] += 1
    for a in current:
        row = area_row(users_by_id.get(a.chv_id))
        row["assessments"] += 1
        row["counts"][category(a)] += 1
    for a in previous:
        row = area_row(users_by_id.get(a.chv_id))
        row["previous_assessments"] += 1
        row["previous_counts"][category(a)] += 1
    area_rows = sorted(areas.values(), key=lambda r: (-r["assessments"], r["area"].casefold()))

    # --- rises worth a look ------------------------------------------------- #
    alerts = []
    for row in area_rows:
        # With nothing in the earlier period there is no baseline to rise from.
        if row["area"] == NO_AREA or row["previous_assessments"] == 0:
            continue
        for code in codes + [URGENT]:
            count, before = row["counts"][code], row["previous_counts"][code]
            if count >= RISING_MIN_CASES and count >= RISING_FACTOR * before:
                alerts.append({"area": row["area"], "code": code, "count": count, "previous": before})
    alerts.sort(key=lambda x: (-(x["count"] - x["previous"]), x["area"].casefold()))

    # --- volunteers --------------------------------------------------------- #
    volunteer_rows = []
    for u in volunteers:
        mine = [a for a in current if a.chv_id == u.id]
        history = all_time.get(u.id, [])
        volunteer_rows.append({
            "id": u.id, "name": u.name, "phone": u.phone, "area": _area_name(u),
            "is_active": u.is_active,
            "assessments": len(mine),
            "urgent": sum(category(a) == URGENT for a in mine),
            "total_assessments": len(history),
            "last_assessment_at": max(history) if history else None,
        })
    volunteer_rows.sort(key=lambda r: (-r["assessments"], r["name"].casefold()))

    # --- the assessments themselves, newest first --------------------------- #
    records = []
    for a in sorted(current, key=lambda a: (a.created_at, a.id), reverse=True):
        user = users_by_id.get(a.chv_id)
        records.append({
            "id": a.id, "created_at": a.created_at, "patient_ref": a.patient_ref,
            "age_band": a.age_band, "sex": a.sex, "category": category(a),
            "headline": a.headline, "referral_level": a.referral_level,
            "top_confidence": a.top_confidence,
            "volunteer_id": a.chv_id,
            "volunteer": user.name if user else "Unknown account",
            "area": _area_name(user),
        })

    sample_ids = {u.id for u in users if u.phone.startswith(SAMPLE_PHONE_PREFIX)}

    return {
        "generated_at": now,
        "days": days,
        "start": start,
        "end": today,
        "conditions": [{"code": c, "name": names[c]} for c in codes],
        "totals": {
            "assessments": len(current),
            "previous_assessments": len(previous),
            "volunteers": len(volunteers),
            "active_volunteers": len({a.chv_id for a in current} & {u.id for u in volunteers}),
            "areas": len({r["area"] for r in area_rows if r["assessments"] and r["area"] != NO_AREA}),
        },
        "counts": now_counts,
        "previous_counts": before_counts,
        "trend": trend,
        "areas": area_rows,
        "alerts": alerts,
        "alert_rule": {"min_cases": RISING_MIN_CASES, "factor": RISING_FACTOR},
        "volunteers": volunteer_rows,
        "assessments": records,
        "sample_assessments": sum(a.chv_id in sample_ids for a in current),
    }
