"""One success case and one failure case per endpoint, plus the safety rules."""

import re

MALARIA = {"fever_current", "chills_rigors", "drenching_sweats", "headache",
           "body_aches", "fatigue_weakness"}


def _assess(client, headers, answers, ref=None, age="15_to_49", sex="female"):
    """A new patient unless `ref` names a returning one."""
    body = {"age_band": age, "sex": sex, "answers": answers}
    if ref is not None:
        body["patient_ref"] = ref
    return client.post("/assessments", headers=headers, json=body)


# --- health ------------------------------------------------------------------ #
def test_health_reports_model(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["model_version"] == "v1.0"
    assert body["config_hash"]


def test_frontend_origin_is_allowed(client):
    r = client.options("/questions", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_origin_is_not_allowed(client):
    r = client.options("/questions", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


def test_thresholds_come_from_the_model_file():
    from app.services.predictor import get_predictor
    assert get_predictor().thresholds == {"low_confidence": 0.3, "proximity_margin": 0.3}


# --- auth -------------------------------------------------------------------- #
def test_login_succeeds_with_correct_credentials(client):
    r = client.post("/auth/login", json={"phone": "0711111111", "password": "chv-demo-2026"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "chv" and body["access_token"]
    assert body["name"] == "Wanjiru Kamau"


def test_login_rejects_wrong_password(client):
    r = client.post("/auth/login", json={"phone": "0711111111", "password": "wrong-password"})
    assert r.status_code == 401


def test_login_does_not_reveal_unknown_phone(client):
    r = client.post("/auth/login", json={"phone": "0799999999", "password": "anything"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect phone or password"


def test_unknown_phone_costs_a_password_check_too(client, monkeypatch):
    # Rejecting an unknown phone without hashing is measurably faster than rejecting a
    # wrong password, which reveals which numbers are registered.
    from app.routers import auth
    calls = []
    real = auth.verify_password
    monkeypatch.setattr(auth, "verify_password", lambda *a: calls.append(a) or real(*a))
    for phone in ("0799999999", "0711111111"):
        calls.clear()
        r = client.post("/auth/login", json={"phone": phone, "password": "wrong-password"})
        assert r.status_code == 401
        assert len(calls) == 1, phone


# --- questions --------------------------------------------------------------- #
def test_questions_returns_all_in_order(client, chv_headers):
    questions = client.get("/questions", headers=chv_headers).json()
    assert len(questions) == 35
    assert [q["display_order"] for q in questions] == list(range(1, 36))
    assert {q["code"] for q in questions if q["is_danger_sign"]} == {
        "lethargy_reduced_alertness", "unable_to_drink_or_feed", "convulsions"}


def test_questions_requires_login(client):
    assert client.get("/questions").status_code == 401


def test_invalid_token_is_rejected(client):
    r = client.get("/questions", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


# --- assessments: the core flow ---------------------------------------------- #
def test_malaria_like_answers_return_ranked_result(client, chv_headers, make_answers):
    r = _assess(client, chv_headers, make_answers(yes=MALARIA))
    assert r.status_code == 201
    body = r.json()
    assert body["outcome"] == "likely_condition"
    assert (body["age_band"], body["sex"]) == ("15_to_49", "female")
    assert re.fullmatch(r"P-[A-HJ-NP-Z2-9]{6}", body["patient_ref"])  # issued, not typed
    assert body["top"][0]["code"] == "malaria"
    assert len(body["top"]) == 5  # every condition, best first
    probs = [t["probability"] for t in body["top"]]
    assert probs == sorted(probs, reverse=True)
    assert body["explanation"], "a named result must say what it was based on"
    assert body["guidance"] and "not a diagnosis" in body["disclaimer"]


def test_danger_sign_overrides_the_model(client, chv_headers, make_answers):
    # A convulsion with mild cold symptoms. The model alone would say respiratory
    # infection; the danger rule must still send this patient urgently.
    answers = make_answers(yes={"convulsions", "cough", "runny_or_blocked_nose", "fever_current"})
    body = _assess(client, chv_headers, answers, age="under_5").json()
    assert body["outcome"] == "urgent_referral"
    assert body["headline"] == "Refer urgently now"
    assert body["referral_level"] == "urgent"
    assert body["danger_signs_present"] == ["convulsions"]
    assert body["top"], "the model still runs so the record is complete"


def test_every_danger_sign_triggers_urgent_referral(client, chv_headers, make_answers):
    for sign in ("lethargy_reduced_alertness", "unable_to_drink_or_feed", "convulsions"):
        body = _assess(client, chv_headers, make_answers(yes={sign})).json()
        assert body["outcome"] == "urgent_referral", sign


def test_unknown_answers_are_accepted(client, chv_headers, make_answers):
    answers = make_answers(yes=MALARIA, unknown={"cough", "sore_throat"})
    assert _assess(client, chv_headers, answers).status_code == 201


def test_danger_sign_answered_unknown_is_rejected(client, chv_headers, make_answers):
    # Without this, a skipped danger-sign check with malaria-like symptoms came back as a
    # routine "Likely: Malaria" result instead of prompting the check.
    for sign in ("lethargy_reduced_alertness", "unable_to_drink_or_feed", "convulsions"):
        r = _assess(client, chv_headers, make_answers(yes=MALARIA, unknown={sign}))
        assert r.status_code == 422, sign
        assert sign in r.json()["detail"]


def test_danger_sign_rejection_saves_nothing(client, chv_headers, make_answers):
    before = len(client.get("/assessments", headers=chv_headers).json())
    _assess(client, chv_headers, make_answers(unknown={"convulsions"}))
    assert len(client.get("/assessments", headers=chv_headers).json()) == before


def test_missing_answer_is_rejected(client, chv_headers, make_answers):
    answers = make_answers(yes=MALARIA)
    answers.pop("headache")
    r = _assess(client, chv_headers, answers)
    assert r.status_code == 422
    assert "headache" in r.json()["detail"]


def test_unknown_question_code_is_rejected(client, chv_headers, make_answers):
    answers = make_answers()
    answers["not_a_symptom"] = "yes"
    assert _assess(client, chv_headers, answers).status_code == 422


def test_invalid_answer_value_is_rejected(client, chv_headers, make_answers):
    answers = make_answers()
    answers["cough"] = "maybe"
    assert _assess(client, chv_headers, answers).status_code == 422


def test_invalid_age_band_is_rejected(client, chv_headers, make_answers):
    assert _assess(client, chv_headers, make_answers(), age="adult").status_code == 422


def test_assessment_requires_login(client, make_answers):
    r = client.post("/assessments", json={
        "age_band": "15_to_49", "sex": "male", "answers": make_answers()})
    assert r.status_code == 401


# --- assessment history ------------------------------------------------------ #
def test_chv_sees_own_assessments(client, chv_headers, make_answers):
    created = _assess(client, chv_headers, make_answers(yes=MALARIA)).json()
    listed = client.get("/assessments", headers=chv_headers).json()
    assert created["id"] in {a["id"] for a in listed}


def test_chv_cannot_see_another_chvs_assessments(client, chv_headers, other_chv_headers, make_answers):
    created = _assess(client, chv_headers, make_answers(yes=MALARIA)).json()
    listed = client.get("/assessments", headers=other_chv_headers).json()
    assert created["id"] not in {a["id"] for a in listed}


def test_get_one_assessment_returns_what_was_shown(client, chv_headers, make_answers):
    created = _assess(client, chv_headers, make_answers(yes=MALARIA)).json()
    fetched = client.get(f"/assessments/{created['id']}", headers=chv_headers).json()
    assert fetched["headline"] == created["headline"]
    assert fetched["top"] == created["top"]


def test_timestamps_are_utc_with_a_timezone(client, chv_headers, make_answers):
    from datetime import datetime, timedelta, timezone
    created = _assess(client, chv_headers, make_answers(yes=MALARIA)).json()
    fetched = client.get(f"/assessments/{created['id']}", headers=chv_headers).json()
    listed = client.get("/assessments", headers=chv_headers).json()
    for stamp in (created["created_at"], fetched["created_at"], listed[0]["created_at"]):
        assert stamp.endswith("Z"), stamp
        age = datetime.now(timezone.utc) - datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        assert timedelta(0) <= age < timedelta(minutes=1)


def test_other_chvs_assessment_is_not_found(client, chv_headers, other_chv_headers, make_answers):
    created = _assess(client, chv_headers, make_answers(yes=MALARIA)).json()
    r = client.get(f"/assessments/{created['id']}", headers=other_chv_headers)
    assert r.status_code == 404, "someone else's record must look the same as a missing one"


def test_missing_assessment_is_not_found(client, chv_headers):
    assert client.get("/assessments/999999", headers=chv_headers).status_code == 404


def test_out_of_range_assessment_id_is_rejected(client, chv_headers):
    # Larger than any database INTEGER; this used to overflow in the driver and return 500.
    for bad in ("99999999999999999999999", str(2**31), "0", "-1"):
        assert client.get(f"/assessments/{bad}", headers=chv_headers).status_code == 422, bad


# --- conditions -------------------------------------------------------------- #
def test_condition_returns_guidance(client, chv_headers):
    body = client.get("/conditions/1", headers=chv_headers).json()
    assert body["guidance"] and body["source"]


def test_missing_condition_is_not_found(client, chv_headers):
    assert client.get("/conditions/999", headers=chv_headers).status_code == 404


def test_out_of_range_condition_id_is_rejected(client, chv_headers):
    for bad in ("99999999999999999999999", str(2**31), "0"):
        assert client.get(f"/conditions/{bad}", headers=chv_headers).status_code == 422, bad


# --- admin ------------------------------------------------------------------- #
def test_admin_can_create_chv(client, admin_headers):
    r = client.post("/admin/users", headers=admin_headers, json={
        "name": "New CHV", "phone": "0733333333", "password": "a-strong-password", "area": "Nakuru"})
    assert r.status_code == 201
    assert r.json()["role"] == "chv"
    assert "password" not in r.text and "password_hash" not in r.text


def test_chv_cannot_create_users(client, chv_headers):
    r = client.post("/admin/users", headers=chv_headers, json={
        "name": "X", "phone": "0744444444", "password": "a-strong-password"})
    assert r.status_code == 403


def test_duplicate_phone_is_rejected(client, admin_headers):
    r = client.post("/admin/users", headers=admin_headers, json={
        "name": "Dup", "phone": "0711111111", "password": "a-strong-password"})
    assert r.status_code == 409


def test_duplicate_phone_caught_by_the_database_is_also_a_409(client, admin_headers, monkeypatch):
    # Simulates two simultaneous requests: the "does this phone exist" check finds nothing,
    # and the unique index is what stops the second insert.
    from sqlalchemy.orm import Session
    monkeypatch.setattr(Session, "scalar", lambda self, *a, **k: None)
    r = client.post("/admin/users", headers=admin_headers, json={
        "name": "Race", "phone": "0711111111", "password": "a-strong-password"})
    assert r.status_code == 409


def test_short_password_is_rejected(client, admin_headers):
    r = client.post("/admin/users", headers=admin_headers, json={
        "name": "Short", "phone": "0755555555", "password": "short"})
    assert r.status_code == 422


def test_password_too_long_for_bcrypt_is_rejected(client, admin_headers):
    # bcrypt accepts at most 72 bytes; this used to reach it and return a 500.
    r = client.post("/admin/users", headers=admin_headers, json={
        "name": "Long", "phone": "0755555555", "password": "p" * 73})
    assert r.status_code == 422
    assert "72 bytes" in r.text


def test_72_byte_password_is_accepted_and_works(client, admin_headers):
    r = client.post("/admin/users", headers=admin_headers, json={
        "name": "Edge", "phone": "0756565656", "password": "p" * 72})
    assert r.status_code == 201
    r = client.post("/auth/login", json={"phone": "0756565656", "password": "p" * 72})
    assert r.status_code == 200


def test_non_numeric_phone_is_rejected(client, admin_headers):
    for bad in ("abcdefg", "12345678", "07123", "0812345678", "071234567890"):
        r = client.post("/admin/users", headers=admin_headers, json={
            "name": "Bad", "phone": bad, "password": "a-strong-password"})
        assert r.status_code == 422, bad


def test_phone_is_stored_in_local_form(client, admin_headers):
    r = client.post("/admin/users", headers=admin_headers, json={
        "name": "Intl", "phone": "+254 757 575-757", "password": "a-strong-password"})
    assert r.status_code == 201
    assert r.json()["phone"] == "0757575757"


def test_same_number_in_another_spelling_is_a_duplicate(client, admin_headers):
    r = client.post("/admin/users", headers=admin_headers, json={
        "name": "Dup", "phone": "+254711111111", "password": "a-strong-password"})
    assert r.status_code == 409


def test_login_accepts_international_spelling(client):
    r = client.post("/auth/login", json={"phone": "+254711111111", "password": "chv-demo-2026"})
    assert r.status_code == 200


def test_login_rejects_malformed_phone(client):
    r = client.post("/auth/login", json={"phone": "abcdefg", "password": "anything"})
    assert r.status_code == 422


# --- adaptive questioning --------------------------------------------------- #
DANGER = ("lethargy_reduced_alertness", "unable_to_drink_or_feed", "convulsions")


def _next(client, headers, answers, age="15_to_49", sex="female"):
    return client.post("/assessments/next", headers=headers, json={"age_band": age, "sex": sex, "answers": answers})


def test_next_question_asks_something_new_after_the_danger_signs(client, chv_headers):
    r = _next(client, chv_headers, {d: "no" for d in DANGER})
    assert r.status_code == 200
    body = r.json()
    assert body["done"] is False and body["asked"] == 3 and body["total"] == 35
    assert body["next_question"] and body["next_question"] not in DANGER


def test_next_question_stops_at_a_danger_sign(client, chv_headers):
    body = _next(client, chv_headers, {**{d: "no" for d in DANGER}, "convulsions": "yes"}).json()
    assert body["done"] is True and body["reason"] == "danger_sign"


def test_next_question_stops_when_the_model_is_confident(client, chv_headers):
    answers = {d: "no" for d in DANGER} | {s: "yes" for s in MALARIA}
    body = _next(client, chv_headers, answers).json()
    assert body["done"] is True and body["reason"] == "confident"


def test_following_the_questions_reaches_a_result_before_all_35(client, chv_headers, make_answers):
    target = make_answers(yes=MALARIA)
    answers = {d: "no" for d in DANGER}
    for _ in range(35):
        body = _next(client, chv_headers, answers).json()
        if body["done"]:
            break
        answers[body["next_question"]] = target[body["next_question"]]
    assert body["done"] and len(answers) < 35
    full = {code: answers.get(code, "unknown") for code in target}
    r = _assess(client, chv_headers, full)
    assert r.status_code == 201 and r.json()["top"][0]["code"] == "malaria"


def test_next_question_needs_the_danger_signs_first(client, chv_headers):
    assert _next(client, chv_headers, {}).status_code == 422
    assert _next(client, chv_headers, {d: "unknown" for d in DANGER}).status_code == 422


def test_next_question_rejects_unknown_codes_and_anonymous_callers(client, chv_headers):
    assert _next(client, chv_headers, {**{d: "no" for d in DANGER}, "not_a_question": "yes"}).status_code == 422
    assert client.post("/assessments/next", json={"age_band": "15_to_49", "sex": "female", "answers": {}}).status_code == 401


# --- deployment configuration ----------------------------------------------- #
def test_hosting_platform_database_urls_use_psycopg():
    from app.db import normalise_url
    assert normalise_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert normalise_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalise_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalise_url("sqlite:///x.db") == "sqlite:///x.db"


def test_seed_passwords_come_from_the_environment_when_set(monkeypatch):
    from scripts.seed import DEMO_USERS, password_for
    admin, chv = DEMO_USERS[0], DEMO_USERS[1]
    assert password_for(admin) == admin["password"]
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "a-strong-deployment-secret")
    monkeypatch.setenv("SEED_CHV_PASSWORD", "another-strong-secret")
    assert password_for(admin) == "a-strong-deployment-secret"
    assert password_for(chv) == "another-strong-secret"


def test_seed_never_prints_a_database_password():
    from scripts.seed import masked
    assert masked("postgresql://chv:secretpw@host:5432/db") == "postgresql://chv:***@host:5432/db"
    assert masked("sqlite:///chv.db") == "sqlite:///chv.db"


# --- patient codes ----------------------------------------------------------- #
def test_each_new_patient_gets_a_different_code(client, chv_headers, make_answers):
    codes = {_assess(client, chv_headers, make_answers()).json()["patient_ref"] for _ in range(5)}
    assert len(codes) == 5


def test_returning_patient_keeps_their_code(client, chv_headers, make_answers):
    code = _assess(client, chv_headers, make_answers()).json()["patient_ref"]
    again = _assess(client, chv_headers, make_answers(), ref=f"  {code.lower()} ")  # as copied by hand
    assert again.status_code == 201
    assert again.json()["patient_ref"] == code


def test_unknown_or_made_up_codes_are_refused(client, chv_headers, make_answers):
    before = len(client.get("/assessments", headers=chv_headers).json())
    unknown = _assess(client, chv_headers, make_answers(), ref="P-ABCDEF")
    assert unknown.status_code == 422 and "P-ABCDEF" in unknown.json()["detail"]
    for typed in ("Mary Wanjiku", "12345678", "P-017"):  # a name, an ID number, an old-style code
        assert _assess(client, chv_headers, make_answers(), ref=typed).status_code == 422
    assert len(client.get("/assessments", headers=chv_headers).json()) == before


def test_patient_code_check(client, chv_headers, make_answers):
    code = _assess(client, chv_headers, make_answers()).json()["patient_ref"]
    assert client.get(f"/assessments/patients/{code.lower()}", headers=chv_headers).status_code == 204
    assert client.get("/assessments/patients/P-ABCDEF", headers=chv_headers).status_code == 404
    assert client.get("/assessments/patients/Mary", headers=chv_headers).status_code == 404
    assert client.get(f"/assessments/patients/{code}").status_code == 401
