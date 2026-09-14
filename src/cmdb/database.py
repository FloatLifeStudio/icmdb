"""SQLite 连接与建表(WAL 模式)。"""

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

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


_engine = None

# 轻量迁移:已有表补新列(SQLite ALTER TABLE);新库由 create_all 直接建出
# 注意表名是 SQLModel 默认的类名小写:device / changehistory
_MIGRATIONS = {
    "changehistory": {"diff": "JSON"},
    "device": {
        "os_type": "VARCHAR",
        "os_version": "VARCHAR",
        "kernel": "VARCHAR",
        "agent_version": "VARCHAR",
    },
}


def migrate(engine) -> None:
    """检查既有表的列,补缺失的列 + 旧数据迁移(幂等)。"""
    with engine.connect() as conn:
        for table, cols in _MIGRATIONS.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing:  # 表还不存在,create_all 会带新列建出
                continue
            for col, ddl in cols.items():
                if col not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        _migrate_tags_column(conn)
        _migrate_disk_size(conn)
        _migrate_memory_size(conn)
        # 存量表补索引(SQLModel create_all 不会给已存在的表加索引)
        hcols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(changehistory)")}
        if hcols and "created_at" in hcols:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_changehistory_created_at "
                "ON changehistory (created_at)"
            )
        conn.commit()


def _migrate_tags_column(conn) -> None:
    """旧 device.tags 逗号分隔 TEXT 列 -> device_tag 表;迁完删列。

    仅在列还存在时执行(device_tag 由 create_all 先建好)。
    """
    cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(device)")}
    if "tags" not in cols:
        return
    rows = conn.exec_driver_sql(
        "SELECT id, tags FROM device WHERE tags != ''"
    ).fetchall()
    for device_id, tags in rows:
        for name in (t.strip() for t in tags.split(",")):
            if name:
                conn.exec_driver_sql(
                    "INSERT OR IGNORE INTO devicetag (device_id, name) VALUES (?, ?)",
                    (device_id, name),
                )
    conn.exec_driver_sql("ALTER TABLE device DROP COLUMN tags")


def _migrate_disk_size(conn) -> None:
    """旧 disk 表补 size_gb 归一化列并回填(TB 按 1024 换算)。"""
    cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(disk)")}
    if "size_gb" in cols or not cols:  # 新库由 create_all 带出;表不存在则跳过
        return
    conn.exec_driver_sql("ALTER TABLE disk ADD COLUMN size_gb INTEGER")
    conn.exec_driver_sql(
        "UPDATE disk SET size_gb = CASE "
        "WHEN UPPER(size_unit) = 'TB' THEN size * 1024 ELSE size END"
    )


def _migrate_memory_size(conn) -> None:
    """旧 memoryslot 表补 size/size_unit 列并从 size_gb 回填(旧数据全为 GB)。"""
    cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(memoryslot)")}
    if "size" in cols or not cols:  # 新库由 create_all 带出;表不存在则跳过
        return
    conn.exec_driver_sql("ALTER TABLE memoryslot ADD COLUMN size INTEGER")
    conn.exec_driver_sql("ALTER TABLE memoryslot ADD COLUMN size_unit VARCHAR")
    conn.exec_driver_sql(
        "UPDATE memoryslot SET size = size_gb, size_unit = 'GB' "
        "WHERE size_gb IS NOT NULL"
    )


def get_engine_cached():
    """进程级单例 engine,首次使用时建表 + 迁移。"""
    global _engine
    if _engine is None:
        _engine = make_engine()
        init_db(_engine)
        migrate(_engine)
        seed_admin(_engine)
    return _engine


def seed_admin(engine) -> None:
    """users 表为空时,按环境变量配置种子 admin 账号。"""
    from cmdb.api.auth import hash_password
    from cmdb.config import settings
    from cmdb.models import User

    with Session(engine) as session:
        if session.exec(select(User)).first() is not None:
            return
        session.add(
            User(
                username=settings.admin_user,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
        )
        session.commit()


def get_session():
    """FastAPI 依赖:每个请求一个 Session。"""
    with Session(get_engine_cached()) as session:
        yield session
