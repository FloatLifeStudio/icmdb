"""操作审计:统一记录管理操作(随调用方事务一起提交)。"""

from sqlmodel import Session

from cmdb.models import AuditLog


def record_audit(
    session: Session, username: str | None, action: str, detail: str = ""
) -> None:
    """追加一条审计记录;事务提交由调用方负责。"""
    session.add(AuditLog(username=username, action=action, detail=detail or None))
