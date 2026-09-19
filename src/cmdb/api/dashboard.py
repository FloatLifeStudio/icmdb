"""Dashboard API: asset overview statistics (read-only)"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from cmdb.api.devices import _device_status, _offline_threshold
from cmdb.database import get_session
from cmdb.models import ChangeHistory, Device, PendingChange
from sqlmodel import select

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(session: Session = Depends(get_session)):
    """Asset overview: totals, active/suspected offline, pending count, recent changes"""
    devices = session.exec(select(Device)).all()
    threshold = _offline_threshold(session)
    active = sum(1 for d in devices if _device_status(d, threshold) == "active")
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
