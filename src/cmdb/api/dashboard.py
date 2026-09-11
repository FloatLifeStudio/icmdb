"""仪表盘 API:资产概览统计(只读)。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from cmdb.api.devices import _device_status
from cmdb.database import get_session
from cmdb.models import ChangeHistory, Device, PendingChange
from sqlmodel import select

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(session: Session = Depends(get_session)):
    """资产概览:总数、活跃/疑似下线、待裁决数、最近变更。"""
    devices = session.exec(select(Device)).all()
    active = sum(1 for d in devices if _device_status(d) == "active")
    pending = session.exec(
        select(PendingChange).where(PendingChange.status == "pending")
    ).all()
    recent = session.exec(
        select(ChangeHistory).order_by(ChangeHistory.created_at.desc()).limit(10)
    ).all()
    return {
        "total_devices": len(devices),
        "active": active,
        "suspected_offline": len(devices) - active,
        "pending_changes": len(pending),
        "recent_changes": recent,
    }
