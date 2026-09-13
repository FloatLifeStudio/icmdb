"""测试公共 fixture:临时 SQLite 库,每个用例独立。"""

import pytest
from sqlmodel import Session

from cmdb.database import init_db, make_engine


@pytest.fixture()
def engine(tmp_path):
    eng = make_engine(str(tmp_path / "test.db"))
    init_db(eng)
    yield eng


@pytest.fixture()
def client(engine):
    """TestClient,API 依赖指向临时库。"""
    from fastapi.testclient import TestClient

    from cmdb.database import get_session
    from cmdb.main import app

    def _get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    with TestClient(app) as c:
        # 默认已登录(单管理员),登录/鉴权专项测试用 guest fixture
        c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def guest(engine):
    """未登录的 TestClient,鉴权专项测试用。"""
    from fastapi.testclient import TestClient

    from cmdb.database import get_session
    from cmdb.main import app

    def _get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
