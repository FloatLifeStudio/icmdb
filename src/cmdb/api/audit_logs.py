"""操作审计日志 API:仅 admin(中间件按路径拦截,此处再做角色校验)。"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from cmdb.api.auth import current_username
from cmdb.database import get_session
from cmdb.models import AuditLog, User

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("")
def list_audit_logs(
    request: Request,
    username: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """审计日志列表(新在前,可选按操作人过滤)。"""
    me = current_username(request)
    user = session.exec(select(User).where(User.username == me)).first() if me else None
    if user is None or user.role != "admin":
        raise HTTPException(status_code=403, detail="仅 admin 可查看审计日志")
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if username:
        stmt = stmt.where(AuditLog.username == username)
    rows = session.exec(stmt.limit(min(limit, 1000))).all()
    return {
        "items": [
            {
                "id": r.id,
                "username": r.username,
                "action": r.action,
                "detail": r.detail,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
