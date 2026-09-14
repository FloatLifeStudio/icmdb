"""用户管理 API:仅 admin(中间件按角色拦截,此处再做兜底校验)。"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from cmdb.api.auth import SESSION_COOKIE, hash_password, token_username
from cmdb.database import get_session
from cmdb.models import User

router = APIRouter(prefix="/users", tags=["users"])

_ROLES = ("admin", "viewer")


def _to_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
    }


def _admin_count(session: Session) -> int:
    return len(
        session.exec(select(User).where(User.role == "admin")).all()
    )


def _current_username(request: Request) -> str | None:
    return token_username(request.cookies.get(SESSION_COOKIE))


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserUpdateIn(BaseModel):
    password: str | None = None
    role: str | None = None


@router.get("")
def list_users(session: Session = Depends(get_session)):
    """用户列表。"""
    return {"items": [_to_out(u) for u in session.exec(select(User)).all()]}


@router.post("")
def create_user(body: UserIn, session: Session = Depends(get_session)):
    """新增用户。"""
    if body.role not in _ROLES:
        raise HTTPException(status_code=422, detail=f"role 只能是 {' / '.join(_ROLES)}")
    if not body.username.strip() or not body.password:
        raise HTTPException(status_code=422, detail="用户名和密码不能为空")
    exists = session.exec(
        select(User).where(User.username == body.username.strip())
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(
        username=body.username.strip(),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _to_out(user)


@router.put("/{user_id}")
def update_user(
    user_id: int, body: UserUpdateIn, session: Session = Depends(get_session)
):
    """重置密码 / 修改角色。"""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.role is not None:
        if body.role not in _ROLES:
            raise HTTPException(
                status_code=422, detail=f"role 只能是 {' / '.join(_ROLES)}"
            )
        if user.role == "admin" and body.role != "admin" and _admin_count(session) == 1:
            raise HTTPException(status_code=409, detail="不能降级最后一个管理员账号")
        user.role = body.role
    if body.password:
        user.password_hash = hash_password(body.password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return _to_out(user)


@router.delete("/{user_id}")
def delete_user(user_id: int, request: Request, session: Session = Depends(get_session)):
    """删除用户;不能删除自己与最后一个管理员。"""
    if user := session.get(User, user_id):
        if user.username == _current_username(request):
            raise HTTPException(status_code=409, detail="不能删除自己的账号")
        if user.role == "admin" and _admin_count(session) == 1:
            raise HTTPException(status_code=409, detail="不能删除最后一个管理员账号")
        session.delete(user)
        session.commit()
        return {"ok": True}
    raise HTTPException(status_code=404, detail="用户不存在")
