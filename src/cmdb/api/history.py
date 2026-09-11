"""变更历史 API:GET 列表/详情(只读)。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from cmdb.database import get_session
from cmdb.models import ChangeHistory

router = APIRouter(prefix="/change-history", tags=["change-history"])


@router.get("")
def list_change_history(
    device_id: int | None = None, session: Session = Depends(get_session)
):
    """变更历史列表,可按设备过滤;设备硬删后其历史仍可查。"""
    query = select(ChangeHistory).order_by(ChangeHistory.created_at.desc())
    if device_id is not None:
        query = query.where(ChangeHistory.device_id == device_id)
    return {"items": session.exec(query).all()}


@router.get("/{history_id}")
def get_change_history(history_id: int, session: Session = Depends(get_session)):
    """变更历史详情:含裁决时的完整 diff。"""
    record = session.get(ChangeHistory, history_id)
    if record is None:
        raise HTTPException(status_code=404, detail="history record not found")
    return record
