"""One success case and one failure case per endpoint, plus the safety rules."""

MALARIA = {"fever_current", "chills_rigors", "drenching_sweats", "headache",
           "body_aches", "fatigue_weakness"}


def _assess(client, headers, answers, ref="T-1", age="15_to_49", sex="female"):
    return client.post("/assessments", headers=headers, json={
        "patient_ref": ref, "age_band": age, "sex": sex, "answers": answers})


# --- health ------------------------------------------------------------------ #
def test_health_reports_model(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["model_version"] and body["config_hash"]


# --- auth -------------------------------------------------------------------- #
def test_login_succeeds_with_correct_credentials(client):
    r = client.post("/auth/login", json={"phone": "0711111111", "password": "chv-demo-2026"})
    assert r.status_code == 200
    assert r.json()["role"] == "chv" and r.json()["access_token"]


def test_login_rejects_wrong_password(client):
    r = client.post("/auth/login", json={"phone": "0711111111", "password": "wrong-password"})
    assert r.status_code == 401


def test_login_does_not_reveal_unknown_phone(client):
    r = client.post("/auth/login", json={"phone": "0799999999", "password": "anything"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect phone or password"


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
    assert body["top"][0]["code"] == "malaria"
    assert len(body["top"]) == 3
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
        "patient_ref": "X", "age_band": "15_to_49", "sex": "male", "answers": make_answers()})
    assert r.status_code == 401


# --- assessment history ------------------------------------------------------ #
def test_chv_sees_own_assessments(client, chv_headers, make_answers):
    created = _assess(client, chv_headers, make_answers(yes=MALARIA), ref="HIST-1").json()
    listed = client.get("/assessments", headers=chv_headers).json()
    assert created["id"] in {a["id"] for a in listed}


def test_chv_cannot_see_another_chvs_assessments(client, chv_headers, other_chv_headers, make_answers):
    created = _assess(client, chv_headers, make_answers(yes=MALARIA), ref="PRIVATE").json()
    listed = client.get("/assessments", headers=other_chv_headers).json()
    assert created["id"] not in {a["id"] for a in listed}


def test_get_one_assessment_returns_what_was_shown(client, chv_headers, make_answers):
    created = _assess(client, chv_headers, make_answers(yes=MALARIA)).json()
    fetched = client.get(f"/assessments/{created['id']}", headers=chv_headers).json()
    assert fetched["headline"] == created["headline"]
    assert fetched["top"] == created["top"]


def test_other_chvs_assessment_is_not_found(client, chv_headers, other_chv_headers, make_answers):
    created = _assess(client, chv_headers, make_answers(yes=MALARIA)).json()
    r = client.get(f"/assessments/{created['id']}", headers=other_chv_headers)
    assert r.status_code == 404, "someone else's record must look the same as a missing one"


def test_missing_assessment_is_not_found(client, chv_headers):
    assert client.get("/assessments/999999", headers=chv_headers).status_code == 404


# --- conditions -------------------------------------------------------------- #
def test_condition_returns_guidance(client, chv_headers):
    body = client.get("/conditions/1", headers=chv_headers).json()
    assert body["guidance"] and body["source"]


def test_missing_condition_is_not_found(client, chv_headers):
    assert client.get("/conditions/999", headers=chv_headers).status_code == 404


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


def test_short_password_is_rejected(client, admin_headers):
    r = client.post("/admin/users", headers=admin_headers, json={
        "name": "Short", "phone": "0755555555", "password": "short"})
    assert r.status_code == 422
