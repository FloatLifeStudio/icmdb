"""SQLite 连接与建表(WAL 模式)。"""

from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from cmdb.config import settings


def make_engine(db_path: str | None = None):
    """创建 SQLite engine,启用 WAL 与外键约束。"""
    path = db_path or settings.db_path
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def init_db(engine) -> None:
    """建表(幂等)。"""
    SQLModel.metadata.create_all(engine)
