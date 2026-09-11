"""测试公共 fixture:临时 SQLite 库,每个用例独立。"""

import pytest

from cmdb.database import init_db, make_engine


@pytest.fixture()
def engine(tmp_path):
    eng = make_engine(str(tmp_path / "test.db"))
    init_db(eng)
    yield eng
