"""Audit: records admin operations in one place (committed with the caller's transaction)"""

from sqlmodel import Session

from cmdb.models import AuditLog


def record_audit(
    session: Session, username: str | None, action: str, detail: str = ""
) -> None:
    """Append one audit record; transaction commit is the caller's responsibility"""
    session.add(AuditLog(username=username, action=action, detail=detail or None))
