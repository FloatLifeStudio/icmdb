"""Conflict pending resolution API: GET list/detail, POST resolve"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from cmdb.database import get_session
from cmdb.models import PendingChange
from cmdb.schemas import ResolutionIn
from cmdb.services.resolve import apply_resolution

router = APIRouter(prefix="/pending-changes", tags=["pending-changes"])


@router.get("")
def list_pending_changes(
    status: str = "pending", session: Session = Depends(get_session)
):
    """Pending list, shows pending only by default; status=all shows everything including processed records"""
    query = select(PendingChange).order_by(PendingChange.created_at)
    if status != "all":
        query = query.where(PendingChange.status == status)
    return {"items": session.exec(query).all()}


@router.get("/{change_id}")
def get_pending_change(change_id: int, session: Session = Depends(get_session)):
    """Diff detail: payload + field-level diff list"""
    pending = session.get(PendingChange, change_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="pending change not found")
    return pending


@router.post("/{change_id}/resolve")
def resolve_pending_change(
    change_id: int, body: ResolutionIn, session: Session = Depends(get_session)
):
    """Resolve: pick new (adopt new data) / old (keep current state) per entry"""
    pending = session.get(PendingChange, change_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="pending change not found")
    if pending.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"already resolved: {pending.status}"
        )
    result = apply_resolution(
        session,
        pending,
        body.field_choices,
        body.nic_choices,
        body.memory_choices,
        body.cpu_choices,
        body.disk_choices,
        body.psu_choices,
        body.gpu_choices,
    )
    return {"applied": result["applied"], "pending_id": pending.id, "status": "applied"}
