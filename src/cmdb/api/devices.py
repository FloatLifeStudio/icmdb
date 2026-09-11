"""设备 API:POST 推送、GET 列表/详情、DELETE。"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlmodel import Session, select

from cmdb.config import settings
from cmdb.database import get_session
from cmdb.models import Device, Nic, NicIP, PendingChange, utcnow
from cmdb.schemas import DeviceCreatedOut, DeviceOut, DevicePush, NicIPOut, NicOut
from cmdb.services.ingest import ingest_push

router = APIRouter(prefix="/devices", tags=["devices"])


def _device_status(device: Device) -> str:
    """动态计算状态:超阈值未推送标记疑似下线。"""
    if device.last_pushed_at is None:
        return "suspected_offline"
    threshold = timedelta(days=settings.offline_threshold_days)
    if utcnow() - device.last_pushed_at > threshold:
        return "suspected_offline"
    return "active"


def _to_out(session: Session, device: Device) -> DeviceOut:
    """Device + 网卡 + IP -> DeviceOut(含动态状态)。"""
    nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
    nic_outs = []
    for nic in nics:
        ips = session.exec(select(NicIP).where(NicIP.nic_id == nic.id)).all()
        nic_outs.append(
            NicOut(
                id=nic.id,
                name=nic.name,
                mac=nic.mac,
                ips=[
                    NicIPOut(id=i.id, ip=i.ip, prefix_length=i.prefix_length)
                    for i in ips
                ],
            )
        )
    return DeviceOut(
        id=device.id,
        hostname=device.hostname,
        serial_number=device.serial_number,
        mgmt_mac=device.mgmt_mac,
        mgmt_ip=device.mgmt_ip,
        mgmt_prefix_length=device.mgmt_prefix_length,
        last_pushed_at=device.last_pushed_at,
        created_at=device.created_at,
        updated_at=device.updated_at,
        status=_device_status(device),
        nics=nic_outs,
    )


@router.post("")
def push_device(push: DevicePush, session: Session = Depends(get_session)):
    """采集推送(唯一数据写入入口)。"""
    result = ingest_push(session, push, utcnow())
    return DeviceCreatedOut(**result)


@router.get("")
def list_devices(
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
):
    """设备列表:分页、hostname 模糊搜索、状态筛选。

    status 由 last_pushed_at 动态计算,筛选同样按阈值在 SQL 层完成。
    """
    query = select(Device)
    if search:
        query = query.where(Device.hostname.contains(search))
    if status in ("active", "suspected_offline"):
        cutoff = utcnow() - timedelta(days=settings.offline_threshold_days)
        if status == "suspected_offline":
            query = query.where(
                or_(Device.last_pushed_at.is_(None), Device.last_pushed_at < cutoff)
            )
        else:
            query = query.where(
                Device.last_pushed_at.is_not(None), Device.last_pushed_at >= cutoff
            )
    total = len(session.exec(query).all())
    devices = session.exec(
        query.order_by(Device.hostname).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [_to_out(session, d) for d in devices]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{device_id}")
def get_device(device_id: int, session: Session = Depends(get_session)):
    """设备详情。"""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")
    return _to_out(session, device)


@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: int, session: Session = Depends(get_session)):
    """手工删除设备:硬删设备与网卡数据,change_history 保留。"""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")

    nics = session.exec(select(Nic).where(Nic.device_id == device_id)).all()
    for nic in nics:
        for nip in session.exec(select(NicIP).where(NicIP.nic_id == nic.id)).all():
            session.delete(nip)
    session.flush()  # 先删子表;无 relationship 时 UoW 删除顺序不保证
    for nic in nics:
        session.delete(nic)
    session.flush()
    for pending in session.exec(
        select(PendingChange).where(PendingChange.device_id == device_id)
    ).all():
        session.delete(pending)
    session.flush()
    session.delete(device)
    session.commit()
