"""The admin dashboard: who may see it, and that its counts are right."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as Row

from app.services.reporting import NO_AREA, build_dashboard
from scripts.seed import CONDITIONS

NOW = datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)
NAMED = [Row(code=c["code"], name=c["name"]) for c in CONDITIONS]


def _user(id, area, role="chv", phone=None):
    return Row(id=id, name=f"Volunteer {id}", phone=phone or f"07000000{id:02d}", role=role,
               area=area, is_active=True)


def _record(id, chv_id, days_ago, condition="malaria", outcome="likely_condition", at=None):
    return Row(id=id, chv_id=chv_id, created_at=at or NOW - timedelta(days=days_ago),
               outcome=outcome, results=[{"code": condition}], patient_ref="P-AAAAAA",
               age_band="15_to_49", sex="female", headline="h", referral_level="refer_same_day",
               top_confidence=0.9)


def _build(records, users, days=7):
    return build_dashboard(records, users, NAMED, days, NOW)


# --- access ------------------------------------------------------------------ #
def test_admin_sees_the_dashboard(client, admin_headers, chv_headers, make_answers):
    before = client.get("/admin/dashboard?days=7", headers=admin_headers).json()
    client.post("/assessments", headers=chv_headers, json={
        "age_band": "15_to_49", "sex": "female", "answers": make_answers(yes=("convulsions",))})
    r = client.get("/admin/dashboard?days=7", headers=admin_headers)
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["totals"]["assessments"] == before["totals"]["assessments"] + 1
    assert after["counts"]["urgent"] == before["counts"]["urgent"] + 1
    newest = after["assessments"][0]
    assert newest["volunteer"] == "Wanjiru Kamau" and newest["area"] == "Kiambu"
    assert newest["category"] == "urgent" and newest["created_at"].endswith("Z")


def test_dashboard_never_returns_password_hashes(client, admin_headers):
    assert "password" not in client.get("/admin/dashboard", headers=admin_headers).text


def test_volunteer_cannot_see_the_dashboard(client, chv_headers):
    assert client.get("/admin/dashboard", headers=chv_headers).status_code == 403


def test_dashboard_requires_login(client):
    assert client.get("/admin/dashboard").status_code == 401


def test_only_the_offered_periods_are_accepted(client, admin_headers):
    for days in (7, 28, 84):
        assert client.get(f"/admin/dashboard?days={days}", headers=admin_headers).status_code == 200
    assert client.get("/admin/dashboard?days=30", headers=admin_headers).status_code == 422


# --- counting ---------------------------------------------------------------- #
def test_each_assessment_is_counted_once():
    out = _build([
        _record(1, 1, 0, "malaria"),
        _record(2, 1, 1, "typhoid", outcome="too_close_to_call"),
        _record(3, 1, 2, "uti", outcome="low_confidence"),
        _record(4, 1, 3, "malaria", outcome="urgent_referral"),
    ], [_user(1, "Kisumu")])
    assert out["counts"]["malaria"] == 1
    assert out["counts"]["unclear"] == 2
    assert out["counts"]["urgent"] == 1
    assert sum(out["counts"].values()) == out["totals"]["assessments"] == 4
    assert sum(sum(b["counts"].values()) for b in out["trend"]) == 4


def test_periods_split_at_kenyan_midnight():
    # 7 days ending 26 Nov starts at 00:00 on 20 Nov in Kenya, which is 21:00 UTC on 19 Nov.
    first_moment = datetime(2026, 11, 19, 21, 0, tzinfo=timezone.utc)
    out = _build([
        _record(1, 1, 0, at=first_moment),
        _record(2, 1, 0, at=first_moment - timedelta(minutes=1)),
        _record(3, 1, 0, at=NOW - timedelta(days=30)),  # older than both periods
    ], [_user(1, "Kisumu")])
    assert out["totals"]["assessments"] == 1
    assert out["totals"]["previous_assessments"] == 1
    assert out["volunteers"][0]["total_assessments"] == 3


def test_trend_is_daily_for_a_week_and_weekly_beyond():
    users = [_user(1, "Kisumu")]
    assert len(_build([], users, 7)["trend"]) == 7
    assert len(_build([], users, 28)["trend"]) == 4
    assert len(_build([], users, 84)["trend"]) == 12
    assert _build([], users, 28)["trend"][-1]["end"].isoformat() == "2026-11-26"


def test_areas_ignore_capitals_and_spaces():
    out = _build([_record(1, 1, 0), _record(2, 2, 0), _record(3, 3, 0)],
                 [_user(1, "Kisumu"), _user(2, " kisumu "), _user(3, None)])
    areas = {a["area"]: a for a in out["areas"]}
    assert areas["Kisumu"]["assessments"] == 2 and areas["Kisumu"]["volunteers"] == 2
    assert areas[NO_AREA]["assessments"] == 1
    assert out["totals"]["areas"] == 1


def test_a_doubling_with_enough_cases_is_flagged():
    records = [_record(i, 1, 1) for i in range(1, 7)]               # 6 this week
    records += [_record(i, 1, 8) for i in range(7, 10)]             # 3 the week before
    alerts = _build(records, [_user(1, "Kisumu")])["alerts"]
    assert alerts == [{"area": "Kisumu", "code": "malaria", "count": 6, "previous": 3}]


def test_small_or_modest_rises_are_not_flagged():
    users = [_user(1, "Kisumu")]
    few = [_record(i, 1, 1) for i in range(1, 5)] + [_record(9, 1, 8)]   # 4 cases: too few
    modest = [_record(i, 1, 1) for i in range(1, 7)]                     # 6 after 4
    modest += [_record(i, 1, 8) for i in range(7, 11)]
    assert _build(few, users)["alerts"] == []
    assert _build(modest, users)["alerts"] == []


def test_nothing_is_flagged_without_an_earlier_period():
    records = [_record(i, 1, 1) for i in range(1, 10)]
    assert _build(records, [_user(1, "Kisumu")])["alerts"] == []


def test_sample_data_is_reported():
    users = [_user(1, "Kisumu"), _user(2, "Kisumu", phone="0799000001")]
    out = _build([_record(1, 1, 0), _record(2, 2, 0)], users)
    assert out["sample_assessments"] == 1
