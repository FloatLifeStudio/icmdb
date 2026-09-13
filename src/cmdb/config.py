"""配置项:环境变量可覆盖,均带默认值。"""

import os


class Settings:
    """全局配置,实例化时读取环境变量。"""

    def __init__(self) -> None:
        # SQLite 数据库文件路径
        self.db_path: str = os.getenv("CMDB_DB_PATH", "cmdb.db")
        # 疑似下线阈值:超 N 天未推送标记为 suspected_offline
        self.offline_threshold_days: int = int(
            os.getenv("CMDB_OFFLINE_THRESHOLD_DAYS", "3")
        )
        # 前端构建产物目录(FastAPI StaticFiles 托管)
        self.static_dir: str = os.getenv(
            "CMDB_STATIC_DIR", "src/cmdb/static"
        )
        # 单管理员账号(UI 登录用;推送接口不鉴权,采集器无需改造)
        self.admin_user: str = os.getenv("CMDB_ADMIN_USER", "admin")
        self.admin_password: str = os.getenv("CMDB_ADMIN_PASSWORD", "admin")
        # 会话 cookie 签名密钥(改密钥即全员下线)
        self.secret_key: str = os.getenv("CMDB_SECRET_KEY", "cmdb-session-secret")
        # 会话有效期(天)
        self.session_expire_days: int = int(os.getenv("CMDB_SESSION_EXPIRE_DAYS", "7"))


settings = Settings()
