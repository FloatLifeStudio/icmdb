"""Shared test fixtures: temporary SQLite database, isolated per test case"""

import pytest
from sqlmodel import Session

from cmdb.database import init_db, make_engine, seed_admin


@pytest.fixture()
def engine(tmp_path):
    eng = make_engine(str(tmp_path / "test.db"))
    init_db(eng)
    seed_admin(eng)
    yield eng


@pytest.fixture()
def client(engine, monkeypatch):
    """TestClient with API dependencies pointed at the temporary database"""
    from fastapi.testclient import TestClient

    from cmdb.database import get_session
    from cmdb.main import app

    def _get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    # login/me/role queries go through get_engine_cached, point it at the temp db
    monkeypatch.setattr("cmdb.database.get_engine_cached", lambda: engine)
    with TestClient(app) as c:
        # logged in as admin by default, use the guest fixture for auth tests
        c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def guest(engine, monkeypatch):
    """TestClient without login, used for auth-specific tests"""
    from fastapi.testclient import TestClient

    from cmdb.database import get_session
    from cmdb.main import app

    def _get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    monkeypatch.setattr("cmdb.database.get_engine_cached", lambda: engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
