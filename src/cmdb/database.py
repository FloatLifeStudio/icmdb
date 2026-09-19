"""SQLite connection and table creation (WAL mode)"""

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from cmdb.config import settings


def make_engine(db_path: str | None = None):
    """Create a SQLite engine with WAL and foreign key constraints enabled"""
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
    """Create tables (idempotent)"""
    SQLModel.metadata.create_all(engine)


_engine = None

# Lightweight migrations: add new columns to existing tables (SQLite ALTER TABLE); fresh databases are built directly by create_all
# Note the table names are SQLModel's default lowercase class names: device / changehistory
_MIGRATIONS = {
    "changehistory": {"diff": "JSON"},
    "device": {
        "os_type": "VARCHAR",
        "os_version": "VARCHAR",
        "os_virt": "VARCHAR",
        "kernel": "VARCHAR",
        "agent_version": "VARCHAR",
        "location": "VARCHAR",
        "owner": "VARCHAR",
        "purpose": "VARCHAR",
    },
}


def migrate(engine) -> None:
    """Check the columns of existing tables, add missing columns + migrate old data (idempotent)"""
    with engine.connect() as conn:
        for table, cols in _MIGRATIONS.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing:  # table doesn't exist yet, create_all will create it with the new columns
                continue
            for col, ddl in cols.items():
                if col not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        _migrate_tags_column(conn)
        _migrate_disk_size(conn)
        _migrate_memory_size(conn)
        # Add indexes to existing tables (SQLModel create_all doesn't add indexes to existing tables)
        hcols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(changehistory)")}
        if hcols and "created_at" in hcols:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_changehistory_created_at "
                "ON changehistory (created_at)"
            )
        conn.commit()


def _migrate_tags_column(conn) -> None:
    """Migrate the old device.tags comma-separated TEXT column -> device_tag table, drop the column afterwards

    Only runs while the column still exists (device_tag is created first by create_all)
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
    """Add a normalized size_gb column to the old disk table and backfill (TB converted at 1024)"""
    cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(disk)")}
    if "size_gb" in cols or not cols:  # fresh databases get it from create_all; skip when the table doesn't exist
        return
    conn.exec_driver_sql("ALTER TABLE disk ADD COLUMN size_gb INTEGER")
    conn.exec_driver_sql(
        "UPDATE disk SET size_gb = CASE "
        "WHEN UPPER(size_unit) = 'TB' THEN size * 1024 ELSE size END"
    )


def _migrate_memory_size(conn) -> None:
    """Add size/size_unit columns to the old memoryslot table and backfill from size_gb (old data is all GB)"""
    cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(memoryslot)")}
    if "size" in cols or not cols:  # fresh databases get them from create_all; skip when the table doesn't exist
        return
    conn.exec_driver_sql("ALTER TABLE memoryslot ADD COLUMN size INTEGER")
    conn.exec_driver_sql("ALTER TABLE memoryslot ADD COLUMN size_unit VARCHAR")
    conn.exec_driver_sql(
        "UPDATE memoryslot SET size = size_gb, size_unit = 'GB' "
        "WHERE size_gb IS NOT NULL"
    )


def get_engine_cached():
    """Process-level singleton engine, creates tables + migrates on first use"""
    global _engine
    if _engine is None:
        _engine = make_engine()
        init_db(_engine)
        migrate(_engine)
        seed_admin(_engine)
    return _engine


def seed_admin(engine) -> None:
    """Seed an admin account from environment config when the users table is empty"""
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
    """FastAPI dependency: one Session per request"""
    with Session(get_engine_cached()) as session:
        yield session
