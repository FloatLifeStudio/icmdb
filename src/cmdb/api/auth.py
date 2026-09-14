"""用户登录:users 表多账号,PBKDF2 哈希,HMAC 签名 cookie 会话。

推送接口(POST /devices)不鉴权,采集器无需改造;其余 /api/v1 接口
由 main.py 的中间件统一校验会话 cookie 与角色(admin 可操作,viewer 只读)。
"""

import hashlib
import hmac
import secrets
import time

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from cmdb.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "cmdb_session"


def hash_password(password: str, salt: str | None = None) -> str:
    """PBKDF2-SHA256 哈希,存 salt:digest。"""
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
    """token = 过期时间戳:用户名:HMAC 签名。"""
    expires = int(time.time()) + settings.session_expire_days * 86400
    payload = f"{expires}:{username}"
    return f"{payload}:{_sign(payload)}"


def token_username(token: str | None) -> str | None:
    """校验会话 token:签名正确、未过期,返回用户名;无效返回 None。"""
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


@router.post("/login")
def login(body: LoginIn, response: Response):
    """校验 users 表账号密码,签发会话 cookie。"""
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


@router.post("/logout")
def logout(response: Response):
    """清除会话 cookie。"""
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(cmdb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    """返回当前登录用户与角色;未登录返回 401,前端用它判断会话状态。"""
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
