"""FastAPI app 工厂:/api 路由挂载 + 前端静态托管。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from cmdb.api.dashboard import router as dashboard_router
from cmdb.api.devices import router as devices_router
from cmdb.api.history import router as history_router
from cmdb.api.pending_changes import router as pending_changes_router
from cmdb.config import settings


class SPAStaticFiles(StaticFiles):
    """前端 SPA 静态托管:文件不存在时回退到 index.html,支持前端路由刷新。"""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # 未知 API 路径不回退,保持 404
            if exc.status_code == 404 and not path.startswith("api/"):
                return await super().get_response("index.html", scope)
            raise


def create_app() -> FastAPI:
    app = FastAPI(title="CMDB", version="2.0.0")
    app.include_router(devices_router, prefix="/api/v1")
    app.include_router(pending_changes_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")

    # 前端构建产物由 FastAPI 托管,单服务单端口;目录不存在(纯后端 dev)时跳过
    static_dir = Path(settings.static_dir)
    if static_dir.exists():
        app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()
