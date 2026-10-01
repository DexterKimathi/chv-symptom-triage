"""Test fixtures: every test session gets its own throwaway SQLite database.

The development database (chv.db) is never touched. The real model bundle is used, so
these tests exercise the same model the API serves.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db import Base, get_db, make_engine
from app.main import app
from app.models import Condition, Question, User
from scripts.seed import CONDITIONS, DEMO_USERS, PROVISIONAL, load_questions

ADMIN = DEMO_USERS[0]
CHV_A = DEMO_USERS[1]
CHV_B = DEMO_USERS[2]


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    engine = make_engine(f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with TestSession() as db:
        db.add_all(Question(**q) for q in load_questions())
        db.add_all(Condition(**c, source=PROVISIONAL) for c in CONDITIONS)
        db.add_all(
            User(name=u["name"], phone=u["phone"], role=u["role"], area=u["area"],
                 password_hash=hash_password(u["password"]))
            for u in DEMO_USERS
        )
        db.commit()

    def override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _token(client, user) -> dict:
    response = client.post("/auth/login", json={"phone": user["phone"], "password": user["password"]})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return _token(client, ADMIN)


@pytest.fixture(scope="session")
def chv_headers(client):
    return _token(client, CHV_A)


@pytest.fixture(scope="session")
def other_chv_headers(client):
    return _token(client, CHV_B)


@pytest.fixture(scope="session")
def question_codes(client, chv_headers):
    return [q["code"] for q in client.get("/questions", headers=chv_headers).json()]


@pytest.fixture
def make_answers(question_codes):
    """All questions answered no, except the codes given, which are answered yes."""
    def build(yes=(), unknown=()):
        return {code: "yes" if code in yes else "unknown" if code in unknown else "no"
                for code in question_codes}
    return build
