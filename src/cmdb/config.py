"""Configuration: overridable via environment variables, all with defaults"""

import os


class Settings:
    """Global configuration, reads environment variables on instantiation"""

    def __init__(self) -> None:
        # SQLite database file path
        self.db_path: str = os.getenv("CMDB_DB_PATH", "cmdb.db")
        # Suspected offline threshold: no push for more than 24 hours (N days) marks the device as suspected_offline
        self.offline_threshold_days: int = int(
            os.getenv("CMDB_OFFLINE_THRESHOLD_DAYS", "1")
        )
        # Frontend build output directory (hosted by FastAPI StaticFiles)
        self.static_dir: str = os.getenv(
            "CMDB_STATIC_DIR", "src/cmdb/static"
        )
        # Single admin account (for UI login; the push endpoint needs no auth, collectors need no changes)
        self.admin_user: str = os.getenv("CMDB_ADMIN_USER", "admin")
        self.admin_password: str = os.getenv("CMDB_ADMIN_PASSWORD", "admin")
        # Session cookie signing key (changing the key signs everyone out)
        self.secret_key: str = os.getenv("CMDB_SECRET_KEY", "cmdb-session-secret")
        # Session validity (days)
        self.session_expire_days: int = int(os.getenv("CMDB_SESSION_EXPIRE_DAYS", "7"))


settings = Settings()
