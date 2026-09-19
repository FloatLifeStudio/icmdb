"""FastAPI app 工厂:/api 路由挂载 + 前端静态托管。"""

import tomllib
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlmodel import Session, select

from cmdb.api.auth import SESSION_COOKIE, token_username
from cmdb.api.auth import router as auth_router
from cmdb.api.dashboard import router as dashboard_router
from cmdb.api.devices import router as devices_router
from cmdb.api.history import router as history_router
from cmdb.api.pending_changes import router as pending_changes_router
from cmdb.api.settings import router as settings_router
from cmdb.api.users import router as users_router
from cmdb.config import settings


def _version() -> str:
    """从 pyproject.toml 读版本号,读不到回退 unknown。"""
    for parent in Path(__file__).parents:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, "rb") as f:
                    return tomllib.load(f)["project"]["version"]
            except Exception:
                break
    return "unknown"


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


def _is_admin_path(path: str, method: str) -> bool:
    """仅 admin 可操作的接口(其他用户只读)。"""
    if path.startswith("/api/v1/users"):
        return True
    if method == "PUT" and path.startswith("/api/v1/settings"):
        return True
    if method == "DELETE" and path.startswith("/api/v1/devices"):
        return True
    if method == "PUT" and path.startswith("/api/v1/devices"):
        return True
    if method == "POST" and path.startswith("/api/v1/devices/batch-delete"):
        return True
    if method == "POST" and path.startswith("/api/v1/devices/import"):
        return True
    if method == "POST" and path.startswith("/api/v1/pending-changes") and path.endswith(
        "/resolve"
    ):
        return True
    return False


def create_app() -> FastAPI:
    app = FastAPI(title="CMDB", version=_version())
    app.include_router(devices_router, prefix="/api/v1")
    app.include_router(pending_changes_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")

    # 会话与角色拦截:/api/v1 除推送(采集器无需登录)与登录/会话检查外均要求登录;
    # 写操作(裁决/删除/标签/用户管理)仅 admin;角色从库中实时查询,变更即时生效。
    # 静态资源(登录页本身)不拦截,由前端路由守卫跳转
    exempt = {
        ("/api/v1/devices", "POST"),
        ("/api/v1/auth/login", "POST"),
        ("/api/v1/auth/me", "GET"),
    }

    @app.middleware("http")
    async def _auth_middleware(request, call_next):
        path = request.url.path
        if path.startswith("/api/v1") and (path, request.method) not in exempt:
            username = token_username(request.cookies.get(SESSION_COOKIE))
            if username is None:
                return JSONResponse({"detail": "未登录"}, status_code=401)
            if _is_admin_path(path, request.method) and _user_role(username) != "admin":
                return JSONResponse({"detail": "需要管理员权限"}, status_code=403)
        return await call_next(request)

    # 前端构建产物由 FastAPI 托管,单服务单端口;目录不存在(纯后端 dev)时跳过
    static_dir = Path(settings.static_dir)
    if static_dir.exists():
        app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="static")
    return app


def _user_role(username: str) -> str:
    """从库中实时查用户角色(角色变更即时生效)。"""
    from cmdb.database import get_engine_cached
    from cmdb.models import User

    with Session(get_engine_cached()) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        return user.role if user else ""


app = create_app()
