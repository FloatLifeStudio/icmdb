"""API key management: create / list / revoke (admin only, enforced by the middleware)"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from cmdb.api.auth import current_username
from cmdb.database import get_session
from cmdb.models import ApiKey, utcnow
from cmdb.services.audit import record_audit

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyIn(BaseModel):
    name: str


class ApiKeyOut(BaseModel):
    id: int
    name: str
    key: str
    prefix: str
    created_at: str
    last_used_at: str | None


def _to_out(row: ApiKey) -> ApiKeyOut:
    """Serialize a key row; the full key is included (viewable anytime)"""
    return ApiKeyOut(
        id=row.id,
        name=row.name,
        key=row.key,
        prefix=row.prefix,
        created_at=row.created_at.isoformat(),
        last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
    )


@router.get("")
def list_api_keys(session: Session = Depends(get_session)) -> dict:
    """List all keys with the full key value"""
    rows = session.exec(select(ApiKey).order_by(ApiKey.id)).all()
    return {"items": [_to_out(row) for row in rows]}


@router.post("")
def create_api_key(
    body: ApiKeyIn, request: Request, session: Session = Depends(get_session)
) -> ApiKeyOut:
    """Create a new key: cmdb_ + 32 hex chars, stored in full plus a display prefix"""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="密钥名称不能为空")
    key = "cmdb_" + secrets.token_hex(16)
    row = ApiKey(name=name, key=key, prefix=key[:12], created_at=utcnow())
    session.add(row)
    record_audit(
        session, current_username(request), "创建 API 密钥", f"{name} ({row.prefix}...)"
    )
    session.commit()
    session.refresh(row)
    return _to_out(row)


@router.delete("/{key_id}")
def revoke_api_key(
    key_id: int, request: Request, session: Session = Depends(get_session)
) -> dict:
    """Revoke (delete) a key; collectors using it get 401 immediately"""
    row = session.get(ApiKey, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="API 密钥不存在")
    session.delete(row)
    record_audit(
        session, current_username(request), "吊销 API 密钥", f"{row.name} ({row.prefix}...)"
    )
    session.commit()
    return {"ok": True}
