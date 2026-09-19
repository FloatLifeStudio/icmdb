"""FastAPI app factory: /api routers + frontend static hosting"""

import tomllib
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlmodel import Session, select

from cmdb.api.auth import SESSION_COOKIE, token_username
from cmdb.api.auth import router as auth_router
from cmdb.api.audit_logs import router as audit_logs_router
from cmdb.api.dashboard import router as dashboard_router
from cmdb.api.devices import router as devices_router
from cmdb.api.history import router as history_router
from cmdb.api.pending_changes import router as pending_changes_router
from cmdb.api.settings import router as settings_router
from cmdb.api.users import router as users_router
from cmdb.config import settings


def _version() -> str:
    """Read the version from pyproject.toml, fall back to unknown"""
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
    """Static hosting for the frontend SPA: falls back to index.html for missing files, supports frontend route refresh"""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # Unknown API paths don't fall back, keep the 404
            if exc.status_code == 404 and not path.startswith("api/"):
                return await super().get_response("index.html", scope)
            raise


def _is_admin_path(path: str, method: str) -> bool:
    """Admin-only endpoints (other users are read-only)"""
    if path.startswith("/api/v1/users"):
        return True
    if path.startswith("/api/v1/audit-logs"):
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
    app.include_router(audit_logs_router, prefix="/api/v1")

    # Session and role gating: /api/v1 requires login except for push (collectors need no login) and login/session check;
    # write operations (resolve/delete/tags/user management) are admin only; roles are queried from the DB in real time, changes take effect immediately
    # Static assets (the login page itself) are not intercepted, the frontend route guard handles redirects
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

    # Frontend build output is hosted by FastAPI, single service single port; skipped when the directory doesn't exist (backend-only dev)
    static_dir = Path(settings.static_dir)
    if static_dir.exists():
        app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="static")
    return app


def _user_role(username: str) -> str:
    """Query the user role from the DB in real time (role changes take effect immediately)"""
    from cmdb.database import get_engine_cached
    from cmdb.models import User

    with Session(get_engine_cached()) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        return user.role if user else ""


app = create_app()
