"""FastAPI app 工厂:/api 路由挂载 + 前端静态托管。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from cmdb.api.devices import router as devices_router
from cmdb.api.history import router as history_router
from cmdb.api.pending_changes import router as pending_changes_router
from cmdb.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="CMDB", version="2.0.0")
    app.include_router(devices_router, prefix="/api/v1")
    app.include_router(pending_changes_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")

    # 前端构建产物由 FastAPI 托管,单服务单端口;目录不存在(纯后端 dev)时跳过
    static_dir = Path(settings.static_dir)
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()
