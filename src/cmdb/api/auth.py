"""User login: multiple accounts in the users table, PBKDF2 hashing, HMAC-signed cookie sessions

The push endpoint (POST /devices) needs no auth, collectors need no changes; the other /api/v1 endpoints
are validated centrally by the main.py middleware for session cookie and role (admin can operate, viewer is read-only)
"""

import hashlib
import hmac
import secrets
import time

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from cmdb.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "cmdb_session"


def hash_password(password: str, salt: str | None = None) -> str:
    """PBKDF2-SHA256 hash, stored as salt:digest"""
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split(":", 1)
    except ValueError:
        return False
    expected = hash_password(password, salt)
    return hmac.compare_digest(expected, stored)


def _sign(payload: str) -> str:
    return hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def _make_token(username: str) -> str:
    """token = expiry timestamp:username:HMAC signature"""
    expires = int(time.time()) + settings.session_expire_days * 86400
    payload = f"{expires}:{username}"
    return f"{payload}:{_sign(payload)}"


def current_username(request: Request) -> str | None:
    """Get the current logged-in username from the request cookie"""
    return token_username(request.cookies.get(SESSION_COOKIE))


def token_username(token: str | None) -> str | None:
    """Validate the session token: correct signature and not expired returns the username, invalid returns None"""
    if not token:
        return None
    payload, _, sig = token.rpartition(":")
    if not payload or not sig:
        return None
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    expires_str, _, username = payload.partition(":")
    if not username:
        return None
    try:
        return username if int(expires_str) > time.time() else None
    except ValueError:
        return None


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


@router.post("/login")
def login(body: LoginIn, response: Response):
    """Validate the users table account password and issue a session cookie"""
    from cmdb.database import get_engine_cached
    from cmdb.models import User

    with Session(get_engine_cached()) as session:
        user = session.exec(
            select(User).where(User.username == body.username)
        ).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    response.set_cookie(
        SESSION_COOKIE,
        _make_token(user.username),
        httponly=True,
        samesite="lax",
        max_age=settings.session_expire_days * 86400,
    )
    return {"username": user.username, "role": user.role}


@router.post("/change-password")
def change_password(body: ChangePasswordIn, cmdb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    """The current logged-in user changes their own password (original password must be verified), available to all roles"""
    from cmdb.database import get_engine_cached
    from cmdb.models import User

    username = token_username(cmdb_session)
    if not username:
        raise HTTPException(status_code=401, detail="未登录")
    with Session(get_engine_cached()) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        if not verify_password(body.old_password, user.password_hash):
            raise HTTPException(status_code=401, detail="原密码错误")
        if not body.new_password:
            raise HTTPException(status_code=422, detail="新密码不能为空")
        user.password_hash = hash_password(body.new_password)
        session.add(user)
        session.commit()
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    """Clear the session cookie"""
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(cmdb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    """Return the current logged-in user and role; 401 when not logged in, the frontend uses it to check session state"""
    from cmdb.database import get_engine_cached
    from cmdb.models import User

    username = token_username(cmdb_session)
    if not username:
        raise HTTPException(status_code=401, detail="未登录")
    with Session(get_engine_cached()) as session:
        user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return {"username": user.username, "role": user.role}
