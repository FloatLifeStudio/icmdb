"""Change history API: GET list/detail (read-only)"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from cmdb.database import get_session
from cmdb.models import ChangeHistory

router = APIRouter(prefix="/change-history", tags=["change-history"])


@router.get("")
def list_change_history(
    device_id: int | None = None, session: Session = Depends(get_session)
):
    """Change history list, filterable by device; history remains queryable after the device is hard deleted"""
    query = select(ChangeHistory).order_by(ChangeHistory.created_at.desc())
    if device_id is not None:
        query = query.where(ChangeHistory.device_id == device_id)
    return {"items": session.exec(query).all()}


@router.get("/{history_id}")
def get_change_history(history_id: int, session: Session = Depends(get_session)):
    """Change history detail: includes the full diff at resolution time"""
    record = session.get(ChangeHistory, history_id)
    if record is None:
        raise HTTPException(status_code=404, detail="history record not found")
    return record
