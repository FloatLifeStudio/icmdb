"""用户登录:单管理员账号(env 配置),HMAC 签名 cookie 会话。

推送接口(POST /devices)不鉴权,采集器无需改造;其余 /api/v1 接口
由 main.py 的中间件统一校验会话 cookie。
"""

import hashlib
import hmac
import time

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

from cmdb.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "cmdb_session"


def _sign(payload: str) -> str:
    return hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def _make_token() -> str:
    """token = 过期时间戳:用户名:HMAC 签名。"""
    expires = int(time.time()) + settings.session_expire_days * 86400
    payload = f"{expires}:{settings.admin_user}"
    return f"{payload}:{_sign(payload)}"


def verify_token(token: str | None) -> bool:
    """校验会话 token:签名正确、未过期、用户名匹配。"""
    if not token:
        return False
    payload, _, sig = token.rpartition(":")
    if not payload or not sig:
        return False
    if not hmac.compare_digest(sig, _sign(payload)):
        return False
    expires_str, _, username = payload.partition(":")
    if username != settings.admin_user:
        return False
    try:
        return int(expires_str) > time.time()
    except ValueError:
        return False


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, response: Response):
    """校验账号密码,签发会话 cookie。"""
    ok_user = hmac.compare_digest(
        body.username.encode(), settings.admin_user.encode()
    )
    ok_pass = hmac.compare_digest(
        body.password.encode(), settings.admin_password.encode()
    )
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    response.set_cookie(
        SESSION_COOKIE,
        _make_token(),
        httponly=True,
        samesite="lax",
        max_age=settings.session_expire_days * 86400,
    )
    return {"username": settings.admin_user}


@router.post("/logout")
def logout(response: Response):
    """清除会话 cookie。"""
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(cmdb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    """返回当前登录用户;未登录返回 401,前端用它判断会话状态。"""
    if not verify_token(cmdb_session):
        raise HTTPException(status_code=401, detail="未登录")
    return {"username": settings.admin_user}
