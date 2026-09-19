"""Device API: POST push, GET list/detail/export/batch-delete, tag update, CSV import, DELETE"""

import csv
import io
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, Body, File, HTTPException, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import func, or_
from sqlmodel import Session, select

from cmdb.api.auth import current_username
from cmdb.database import get_session
from cmdb.models import (
    Cpu,
    Device,
    DeviceTag,
    Disk,
    Gpu,
    MemorySlot,
    Nic,
    NicIP,
    PendingChange,
    Psu,
    utcnow,
)
from cmdb.schemas import (
    MetadataIn,
    AgentInfo,
    BatchDeleteIn,
    CpuSlotOut,
    DeviceCreatedOut,
    DeviceOut,
    DevicePush,
    DiskOut,
    GpuOut,
    GpuSlotIn,
    GpuInfo,
    HardwareInfo,
    MgmtInfo,
    MemorySlotOut,
    NicIn,
    NicIPOut,
    NicOut,
    NicIPIn,
    OsInfo,
    PsuOut,
    TagUpdate,
    normalise_legacy,
)
from cmdb.api.settings import get_offline_threshold_hours
from cmdb.services.audit import record_audit
from cmdb.services.ingest import ingest_push

router = APIRouter(prefix="/devices", tags=["devices"])

# Fields the list endpoint allows sorting by (whitelist, prevents injection)
_SORTABLE = {"hostname", "serial_number", "mgmt_ip", "last_pushed_at"}

_Children = dict


def _offline_threshold(session: Session) -> timedelta:
    """Suspected offline threshold: DB system setting takes priority, falls back to environment variables"""
    return timedelta(hours=get_offline_threshold_hours(session))


def _device_status(device: Device, threshold: timedelta) -> str:
    """Compute the status dynamically: no push beyond the threshold marks suspected offline"""
    if device.last_pushed_at is None:
        return "suspected_offline"
    if utcnow() - device.last_pushed_at > threshold:
        return "suspected_offline"
    return "active"


def _load_children(session: Session, device_ids: list[int]) -> _Children:
    """Batch-load child table data for multiple devices (one IN query per kind, avoids N+1)

    Returns {"nics": {device_id: [Nic]}, "ips": {nic_id: [NicIP]},
          "memory": {device_id: [...]}, "cpus": ..., "disks": ...,
          "psus": ..., "tags": {device_id: [str]}}
    """
    if not device_ids:
        return {"nics": {}, "ips": {}, "memory": {}, "cpus": {}, "disks": {},
                "psus": {}, "gpus": {}, "tags": {}}

    nics = session.exec(
        select(Nic).where(Nic.device_id.in_(device_ids))
    ).all()
    nic_ids = [n.id for n in nics]
    ips = session.exec(
        select(NicIP).where(NicIP.nic_id.in_(nic_ids))
    ).all() if nic_ids else []

    children: _Children = {
        "nics": {},
        "ips": {},
        "memory": {},
        "cpus": {},
        "disks": {},
        "psus": {},
        "gpus": {},
        "tags": {},
    }
    for nic in nics:
        children["nics"].setdefault(nic.device_id, []).append(nic)
    for ip in ips:
        children["ips"].setdefault(ip.nic_id, []).append(ip)
    for row in session.exec(
        select(MemorySlot).where(MemorySlot.device_id.in_(device_ids))
    ).all():
        children["memory"].setdefault(row.device_id, []).append(row)
    for row in session.exec(select(Cpu).where(Cpu.device_id.in_(device_ids))).all():
        children["cpus"].setdefault(row.device_id, []).append(row)
    for row in session.exec(select(Disk).where(Disk.device_id.in_(device_ids))).all():
        children["disks"].setdefault(row.device_id, []).append(row)
    for row in session.exec(select(Psu).where(Psu.device_id.in_(device_ids))).all():
        children["psus"].setdefault(row.device_id, []).append(row)
    for row in session.exec(select(Gpu).where(Gpu.device_id.in_(device_ids))).all():
        children["gpus"].setdefault(row.device_id, []).append(row)
    for row in session.exec(
        select(DeviceTag)
        .where(DeviceTag.device_id.in_(device_ids))
        .order_by(DeviceTag.id)
    ).all():
        children["tags"].setdefault(row.device_id, []).append(row.name)
    return children


def _replace_tags(session: Session, device_id: int, tags: list[str]) -> None:
    """Fully replace device tags (delete old rows first, then insert new, flush avoids unique constraint conflicts)"""
    for row in session.exec(
        select(DeviceTag).where(DeviceTag.device_id == device_id)
    ).all():
        session.delete(row)
    session.flush()
    for name in tags:
        session.add(DeviceTag(device_id=device_id, name=name))


def _delete_device_children(session: Session, device_id: int) -> None:
    """Delete a device's child table data: nics + IPs + tags + pending records + hardware

    Without relationships the UoW delete order isn't guaranteed: after deleting child rows, flush explicitly before deleting the parent row
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
    for tag in session.exec(
        select(DeviceTag).where(DeviceTag.device_id == device_id)
    ).all():
        session.delete(tag)
    for mem in session.exec(
        select(MemorySlot).where(MemorySlot.device_id == device_id)
    ).all():
        session.delete(mem)
    for cpu in session.exec(select(Cpu).where(Cpu.device_id == device_id)).all():
        session.delete(cpu)
    for disk in session.exec(select(Disk).where(Disk.device_id == device_id)).all():
        session.delete(disk)
    for psu in session.exec(select(Psu).where(Psu.device_id == device_id)).all():
        session.delete(psu)
    for gpu in session.exec(select(Gpu).where(Gpu.device_id == device_id)).all():
        session.delete(gpu)
    session.flush()


def _to_out(
    session: Session,
    device: Device,
    children: _Children | None = None,
    threshold: timedelta | None = None,
) -> DeviceOut:
    """Device + child table data -> DeviceOut (with dynamic status)

    children are batch-loaded by _load_children; can be omitted for a single device (filled in once internally)
    """
    if children is None:
        children = _load_children(session, [device.id])
    nic_outs = []
    for nic in children["nics"].get(device.id, []):
        nic_outs.append(
            NicOut(
                id=nic.id,
                name=nic.name,
                mac=nic.mac,
                ips=[
                    NicIPOut(id=i.id, ip=i.ip, prefix_length=i.prefix_length)
                    for i in children["ips"].get(nic.id, [])
                ],
            )
        )
    return DeviceOut(
        id=device.id,
        hostname=device.hostname,
        serial_number=device.serial_number,
        os_type=device.os_type,
        os_version=device.os_version,
        os_virt=device.os_virt,
        kernel=device.kernel,
        agent_version=device.agent_version,
        location=device.location,
        owner=device.owner,
        purpose=device.purpose,
        mgmt_mac=device.mgmt_mac,
        mgmt_ip=device.mgmt_ip,
        mgmt_prefix_length=device.mgmt_prefix_length,
        last_pushed_at=device.last_pushed_at,
        created_at=device.created_at,
        updated_at=device.updated_at,
        status=_device_status(device, threshold or _offline_threshold(session)),
        tags=children["tags"].get(device.id, []),
        nics=nic_outs,
        memory=[
            MemorySlotOut(
                id=m.id, slot=m.slot, manufacturer=m.manufacturer,
                part_number=m.part_number, type=m.type,
                size=m.size, size_unit=m.size_unit, size_gb=m.size_gb,
                speed_mts=m.speed_mts, serial_number=m.serial_number,
            )
            for m in children["memory"].get(device.id, [])
        ],
        cpus=[
            CpuSlotOut(id=c.id, slot=c.slot, model=c.model)
            for c in children["cpus"].get(device.id, [])
        ],
        disks=[
            DiskOut(
                id=d.id, serial_number=d.serial_number, type=d.type,
                manufacturer=d.manufacturer, model=d.model,
                size=d.size, size_unit=d.size_unit, size_gb=d.size_gb,
            )
            for d in children["disks"].get(device.id, [])
        ],
        psus=[
            PsuOut(
                id=p.id, serial_number=p.serial_number,
                manufacturer=p.manufacturer, model=p.model,
                max_power_w=p.max_power_w,
            )
            for p in children["psus"].get(device.id, [])
        ],
        gpus=[
            GpuOut(
                id=g.id, uuid=g.uuid, name=g.name,
                serial_number=g.serial_number,
                size=g.size, size_unit=g.size_unit, size_gb=g.size_gb,
                driver_version=g.driver_version, pcie_id=g.pcie_id,
            )
            for g in children["gpus"].get(device.id, [])
        ],
    )


@router.post("")
def push_device(payload: dict = Body(...), session: Session = Depends(get_session)):
    """Collection push (the only data write entry point)

    New format: agent + os + mgmt + hardware; legacy format (top-level hostname etc.) is converted automatically
    """
    try:
        push = DevicePush(**normalise_legacy(payload))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
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
    """Device list: pagination, fuzzy search, status/tag filtering, sorting

    - search covers hostname / serial_number / mgmt_ip / nic business IPs (reverse lookup)
    - status is computed dynamically from last_pushed_at, filtering is also done at the SQL layer by threshold
    - tag matches the tag exactly
    - sort_by sorts by a whitelist field, sort_order is asc / desc
    """
    query = select(Device)
    if search:
        like = f"%{search}%"
        cond = or_(
            Device.hostname.like(like),
            Device.serial_number.like(like),
            Device.mgmt_ip.like(like),
        )
        # Reverse-lookup devices by nic business IP
        ip_device_ids = session.exec(
            select(Nic.device_id)
            .join(NicIP, NicIP.nic_id == Nic.id)
            .where(NicIP.ip.like(like))
        ).all()
        if ip_device_ids:
            cond = or_(cond, Device.id.in_(ip_device_ids))
        query = query.where(cond)
    if tag:
        # Exact tag match (device_tag table, one device-tag pair per row)
        tagged_ids = select(DeviceTag.device_id).where(DeviceTag.name == tag)
        query = query.where(Device.id.in_(tagged_ids))
    if status in ("active", "suspected_offline"):
        cutoff = utcnow() - _offline_threshold(session)
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
    # count uses an aggregate query, avoids loading all rows
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    devices = session.exec(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()
    # Batch-load child tables (one IN query per kind), avoids repeated queries per device
    children = _load_children(session, [d.id for d in devices])
    threshold = _offline_threshold(session)
    items = [_to_out(session, d, children, threshold) for d in devices]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{device_id}")
def get_device(device_id: int, session: Session = Depends(get_session)):
    """Device detail"""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")
    return _to_out(session, device)


@router.delete("/{device_id}", status_code=204)
def delete_device(
    device_id: int, request: Request, session: Session = Depends(get_session)
):
    """Manually delete a device: hard-deletes the device and nic data, change_history is kept"""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")

    _delete_device_children(session, device_id)
    session.delete(device)
    record_audit(session, current_username(request), "删除设备", device.hostname)
    session.commit()


@router.post("/batch-delete")
def batch_delete(
    body: BatchDeleteIn, request: Request, session: Session = Depends(get_session)
):
    """Batch delete devices: hard delete, same behavior as single delete"""
    deleted = []
    for device_id in body.ids:
        device = session.get(Device, device_id)
        if device is None:
            continue
        _delete_device_children(session, device_id)
        session.delete(device)
        deleted.append(device_id)
    record_audit(session, current_username(request), "批量删除设备", f"{len(deleted)} 台")
    session.commit()
    return {"deleted": deleted}


@router.put("/{device_id}/tags")
def update_tags(
    device_id: int, body: TagUpdate, request: Request, session: Session = Depends(get_session)
):
    """Update device tags (full replacement)"""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")
    tags = list(dict.fromkeys(t.strip() for t in body.tags if t.strip()))
    _replace_tags(session, device_id, tags)
    device.updated_at = utcnow()
    record_audit(session, current_username(request), "更新标签", device.hostname)
    session.commit()
    return {"device_id": device_id, "tags": tags}


@router.put("/{device_id}/metadata")
def update_metadata(
    device_id: int,
    body: MetadataIn,
    request: Request,
    session: Session = Depends(get_session),
):
    """Update device metadata (data center/rack location, owner, purpose; untouched by pushes, edited in the UI only)"""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")
    if body.location is not None:
        device.location = body.location.strip() or None
    if body.owner is not None:
        device.owner = body.owner.strip() or None
    if body.purpose is not None:
        device.purpose = body.purpose.strip() or None
    device.updated_at = utcnow()
    record_audit(session, current_username(request), "更新设备信息", device.hostname)
    session.add(device)
    session.commit()
    return {"device_id": device_id, "location": device.location, "owner": device.owner, "purpose": device.purpose}


@router.get("/export/csv")
def export_csv(session: Session = Depends(get_session)):
    """Export all devices as CSV (UTF-8 BOM, Excel Chinese-compatible)"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["hostname", "serial_number", "os_type", "os_version", "os_virt",
         "kernel", "agent_version", "mgmt_mac", "mgmt_ip",
         "mgmt_prefix_length", "purpose",
         "status", "last_pushed_at", "nics", "gpu"]
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
        gpus = session.exec(select(Gpu).where(Gpu.device_id == d.id)).all()
        gpu_parts = []
        for g in gpus:
            size_str = f"{g.size}{g.size_unit}" if g.size else "-"
            gpu_parts.append(
                f"{g.name or '-'}({g.uuid}): {size_str}, "
                f"driver {g.driver_version or '-'}, pcie {g.pcie_id or '-'}"
            )
        writer.writerow(
            [
                d.hostname,
                d.serial_number or "",
                d.os_type or "",
                d.os_version or "",
                d.os_virt or "",
                d.kernel or "",
                d.agent_version or "",
                d.mgmt_mac or "",
                d.mgmt_ip or "",
                d.mgmt_prefix_length if d.mgmt_prefix_length is not None else "",
                d.purpose or "",
                _device_status(d, _offline_threshold(session)),
                d.last_pushed_at.isoformat() if d.last_pushed_at else "",
                " | ".join(nic_parts),
                " | ".join(gpu_parts),
            ]
        )
    content = "\ufeff" + buf.getvalue()  # UTF-8 BOM, Excel Chinese-compatible
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=devices.csv"},
    )


def _nics_from_csv(nics_str: str | None) -> list[NicIn]:
    """Parse the export-format nics column: "eth0(MAC): ip/24, ip/24 | eth1(MAC): ...\""""
    nics: list[NicIn] = []
    if not nics_str:
        return nics
    for part in nics_str.split(" | "):
        m = re.match(r"^(.+?)\((.*?)\):\s*(.*)$", part.strip())
        if not m:
            continue
        name, mac, ip_str = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        ips: list[NicIPIn] = []
        for ip in filter(None, (p.strip() for p in ip_str.split(","))):
            if ip == "-":
                continue
            if "/" in ip:
                addr, prefix = ip.split("/", 1)
                ips.append(NicIPIn(ip=addr, prefix_length=int(prefix)))
            else:
                ips.append(NicIPIn(ip=ip))
        nics.append(NicIn(name=name, mac=mac or None, ips=ips))
    return nics


def _gpus_from_csv(gpus_str: str | None) -> list[GpuSlotIn]:
    """Parse the export-format gpu column: "name(uuid): 80GB, driver 535.183.01, pcie 0000:1B:00.0\""""
    gpus: list[GpuSlotIn] = []
    if not gpus_str:
        return gpus
    for part in gpus_str.split(" | "):
        m = re.match(r"^(.+?)\((.+?)\):\s*(.*)$", part.strip())
        if not m:
            continue
        name, uuid_, rest = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        size = size_unit = driver = pcie = None
        for token in rest.split(","):
            token = token.strip()
            if token.startswith("driver "):
                driver = token[7:] or None
            elif token.startswith("pcie "):
                pcie = token[5:] or None
            elif token and size is None:
                m2 = re.match(r"^(\d+)(GB|TB)$", token, re.IGNORECASE)
                if m2:
                    size = int(m2.group(1))
                    size_unit = m2.group(2).upper()
        gpus.append(
            GpuSlotIn(
                uuid=uuid_,
                name=name or None,
                size=size,
                size_unit=size_unit,
                driver_version=driver,
                pcie_id=pcie,
            )
        )
    return gpus


@router.post("/import/csv")
async def import_csv(
    request: Request, file: UploadFile = File(...), session: Session = Depends(get_session)
):
    """CSV batch import: each row goes through the same cleaning logic as push (hostname matching, diff goes to pending)

    The row format matches the export and can be re-imported directly; source is marked as csv_import
    """
    text = (await file.read()).decode("utf-8-sig")  # BOM compatible
    reader = csv.DictReader(io.StringIO(text))
    summary = {"created": 0, "unchanged": 0, "diff_created": 0, "errors": []}

    for row in reader:
        row_no = reader.line_num
        hostname = (row.get("hostname") or "").strip()
        if not hostname:
            summary["errors"].append(f"第 {row_no} 行:缺 hostname,已跳过")
            continue
        push = DevicePush(
            # CSV represents the device's full state (agent.full_sync defaults to True)
            agent=AgentInfo(source="csv_import"),
            os=OsInfo(hostname=hostname),
            mgmt=MgmtInfo(
                mac=row.get("mgmt_mac") or None,
                ip=row.get("mgmt_ip") or None,
                prefix_length=(
                    int(row["mgmt_prefix_length"])
                    if row.get("mgmt_prefix_length")
                    else None
                ),
            ),
            hardware=HardwareInfo(
                chassis_serial_number=row.get("serial_number") or None,
                nics=_nics_from_csv(row.get("nics")),
                gpu=GpuInfo(slots=_gpus_from_csv(row.get("gpus"))),
            ),
        )
        result = ingest_push(session, push, utcnow(), update_last_pushed=False)
        summary[result["result"]] += 1

        # Purpose is set with the import (CMDB metadata, not pushed through push cleaning)
        purpose = (row.get("purpose") or "").strip()
        if purpose:
            device = session.exec(
                select(Device).where(Device.hostname == hostname)
            ).first()
            if device is not None:
                device.purpose = purpose

    record_audit(
        session,
        current_username(request),
        "CSV 导入",
        f"新增 {summary['created']},未变化 {summary['unchanged']},进待裁决 {summary['diff_created']}",
    )
    session.commit()
    return summary
