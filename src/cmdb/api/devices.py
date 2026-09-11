"""设备 API:POST 推送、GET 列表/详情/导出/批量删除、标签更新、DELETE。"""

import csv
import io
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_
from sqlmodel import Session, select

from cmdb.config import settings
from cmdb.database import get_session
from cmdb.models import Device, Nic, NicIP, PendingChange, utcnow
from cmdb.schemas import (
    BatchDeleteIn,
    DeviceCreatedOut,
    DeviceOut,
    DevicePush,
    NicIPOut,
    NicOut,
    TagUpdate,
)
from cmdb.services.ingest import ingest_push

router = APIRouter(prefix="/devices", tags=["devices"])

# 列表接口允许排序的字段(白名单,防注入)
_SORTABLE = {"hostname", "serial_number", "mgmt_ip", "last_pushed_at"}


def _device_status(device: Device) -> str:
    """动态计算状态:超阈值未推送标记疑似下线。"""
    if device.last_pushed_at is None:
        return "suspected_offline"
    threshold = timedelta(days=settings.offline_threshold_days)
    if utcnow() - device.last_pushed_at > threshold:
        return "suspected_offline"
    return "active"


def _split_tags(tags: str | None) -> list[str]:
    return [t for t in (tags or "").split(",") if t]


def _delete_device_children(session: Session, device_id: int) -> None:
    """删除设备的子表数据:网卡 + IP + 待裁决记录。

    无 relationship 时 UoW 删除顺序不保证:删子表后显式 flush 再删父行。
    """
    nics = session.exec(select(Nic).where(Nic.device_id == device_id)).all()
    for nic in nics:
        for nip in session.exec(select(NicIP).where(NicIP.nic_id == nic.id)).all():
            session.delete(nip)
    session.flush()
    for nic in nics:
        session.delete(nic)
    session.flush()
    for pending in session.exec(
        select(PendingChange).where(PendingChange.device_id == device_id)
    ).all():
        session.delete(pending)
    session.flush()


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
        tags=_split_tags(device.tags),
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
    tag: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
    session: Session = Depends(get_session),
):
    """设备列表:分页、模糊搜索、状态/标签筛选、排序。

    - search 覆盖 hostname / serial_number / mgmt_ip / 网卡业务 IP(反查)
    - status 由 last_pushed_at 动态计算,筛选同样按阈值在 SQL 层完成
    - tag 按标签筛选
    - sort_by 白名单字段排序,sort_order 为 asc / desc
    """
    query = select(Device)
    if search:
        like = f"%{search}%"
        cond = or_(
            Device.hostname.like(like),
            Device.serial_number.like(like),
            Device.mgmt_ip.like(like),
        )
        # 按网卡业务 IP 反查设备
        ip_device_ids = session.exec(
            select(Nic.device_id)
            .join(NicIP, NicIP.nic_id == Nic.id)
            .where(NicIP.ip.like(like))
        ).all()
        if ip_device_ids:
            cond = or_(cond, Device.id.in_(ip_device_ids))
        query = query.where(cond)
    if tag:
        query = query.where(Device.tags.like(f"%{tag}%"))
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
    if sort_by in _SORTABLE:
        col = getattr(Device, sort_by)
        query = query.order_by(col.desc() if sort_order == "desc" else col.asc())
    else:
        query = query.order_by(Device.hostname)
    total = len(session.exec(query).all())
    devices = session.exec(
        query.offset((page - 1) * page_size).limit(page_size)
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

    _delete_device_children(session, device_id)
    session.delete(device)
    session.commit()


@router.post("/batch-delete")
def batch_delete(body: BatchDeleteIn, session: Session = Depends(get_session)):
    """批量删除设备:硬删,行为同单个删除。"""
    deleted = []
    for device_id in body.ids:
        device = session.get(Device, device_id)
        if device is None:
            continue
        _delete_device_children(session, device_id)
        session.delete(device)
        deleted.append(device_id)
    session.commit()
    return {"deleted": deleted}


@router.put("/{device_id}/tags")
def update_tags(
    device_id: int, body: TagUpdate, session: Session = Depends(get_session)
):
    """更新设备标签(全量替换)。"""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")
    device.tags = ",".join(t.strip() for t in body.tags if t.strip())
    device.updated_at = utcnow()
    session.add(device)
    session.commit()
    return {"device_id": device_id, "tags": _split_tags(device.tags)}


@router.get("/export/csv")
def export_csv(session: Session = Depends(get_session)):
    """导出全部设备为 CSV(UTF-8 BOM,Excel 中文兼容)。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["hostname", "serial_number", "mgmt_mac", "mgmt_ip", "mgmt_prefix_length",
         "tags", "status", "last_pushed_at", "nics"]
    )
    for d in session.exec(select(Device).order_by(Device.hostname)).all():
        nics = session.exec(select(Nic).where(Nic.device_id == d.id)).all()
        nic_parts = []
        for nic in nics:
            ips = session.exec(select(NicIP).where(NicIP.nic_id == nic.id)).all()
            ip_str = ",".join(
                i.ip + (f"/{i.prefix_length}" if i.prefix_length else "") for i in ips
            )
            nic_parts.append(f"{nic.name}({nic.mac or '-'}): {ip_str or '-'}")
        writer.writerow(
            [
                d.hostname,
                d.serial_number or "",
                d.mgmt_mac or "",
                d.mgmt_ip or "",
                d.mgmt_prefix_length if d.mgmt_prefix_length is not None else "",
                d.tags,
                _device_status(d),
                d.last_pushed_at.isoformat() if d.last_pushed_at else "",
                " | ".join(nic_parts),
            ]
        )
    content = "\ufeff" + buf.getvalue()  # UTF-8 BOM,Excel 中文兼容
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=devices.csv"},
    )
