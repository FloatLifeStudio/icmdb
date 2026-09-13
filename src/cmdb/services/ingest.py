"""推送处理:hostname 匹配、创建/unchanged/diff 分支、pending 合并。"""

from datetime import datetime

from sqlmodel import Session, select

from cmdb.models import Cpu, Device, MemorySlot, Nic, NicIP, PendingChange, to_naive_utc
from cmdb.schemas import DevicePush
from cmdb.services.diff import diff_push, merge_diff


def build_snapshot(session: Session, device: Device) -> dict:
    """从 ORM 对象构建设备当前快照,供 diff 使用。"""
    nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
    snapshot = {
        "serial_number": device.serial_number,
        "mgmt_mac": device.mgmt_mac,
        "mgmt_ip": device.mgmt_ip,
        "mgmt_prefix_length": device.mgmt_prefix_length,
        "nics": {},
        "memory": {},
        "cpus": {},
    }
    for nic in nics:
        ips = session.exec(select(NicIP).where(NicIP.nic_id == nic.id)).all()
        snapshot["nics"][nic.name] = {
            "name": nic.name,
            "mac": nic.mac,
            "ips": {nip.ip: nip.prefix_length for nip in ips},
        }
    for mem in session.exec(select(MemorySlot).where(MemorySlot.device_id == device.id)):
        snapshot["memory"][mem.slot] = {
            "slot": mem.slot,
            "manufacturer": mem.manufacturer,
            "part_number": mem.part_number,
            "type": mem.type,
            "size_gb": mem.size_gb,
            "speed_mts": mem.speed_mts,
            "serial_number": mem.serial_number,
        }
    for cpu in session.exec(select(Cpu).where(Cpu.device_id == device.id)):
        snapshot["cpus"][cpu.slot] = {"slot": cpu.slot, "model": cpu.model}
    return snapshot


def ingest_push(session: Session, push: DevicePush, received_at: datetime) -> dict:
    """处理一次推送,返回三分支结果。

    - 库中无该 hostname -> created(创建设备+网卡+IP)
    - 有且无差异        -> unchanged(仅刷新 last_pushed_at)
    - 有差异            -> diff_created(合并进 pending,不改现有数据)
    """
    device = session.exec(
        select(Device).where(Device.hostname == push.hostname)
    ).first()

    if device is None:
        device = _create_device(session, push, received_at)
        return {
            "result": "created",
            "device_id": device.id,
            "pending_change_id": None,
        }

    snapshot = build_snapshot(session, device)
    diff = diff_push(snapshot, push)
    if not diff["has_changes"]:
        device.last_pushed_at = to_naive_utc(push.timestamp or received_at)
        session.add(device)
        session.commit()
        return {
            "result": "unchanged",
            "device_id": device.id,
            "pending_change_id": None,
        }

    pending = _merge_into_pending(session, device, push, diff)
    return {
        "result": "diff_created",
        "device_id": device.id,
        "pending_change_id": pending.id,
    }


def _create_device(session: Session, push: DevicePush, received_at: datetime) -> Device:
    """按推送体创建设备 + 网卡 + IP。"""
    device = Device(
        hostname=push.hostname,
        serial_number=push.serial_number,
        mgmt_mac=push.mgmt.mac,
        mgmt_ip=push.mgmt.ip,
        mgmt_prefix_length=push.mgmt.prefix_length,
        last_pushed_at=to_naive_utc(push.timestamp or received_at),
    )
    session.add(device)
    session.flush()

    for nic in push.nics:
        _create_nic(session, device.id, nic)
    if push.memory:
        for mem in push.memory.slots:
            session.add(MemorySlot(device_id=device.id, **mem.model_dump()))
    if push.cpus:
        for cpu in push.cpus:
            session.add(Cpu(device_id=device.id, **cpu.model_dump()))
    session.commit()
    session.refresh(device)
    return device


def _create_nic(session: Session, device_id: int, nic) -> None:
    """创建单块网卡及其 IP 列表。"""
    row = Nic(device_id=device_id, name=nic.name, mac=nic.mac)
    session.add(row)
    session.flush()
    for ip in nic.ips:
        session.add(NicIP(nic_id=row.id, ip=ip.ip, prefix_length=ip.prefix_length))


def _merge_into_pending(
    session: Session, device: Device, push: DevicePush, diff: dict
) -> PendingChange:
    """合并进该设备已有的 pending(始终一条),否则新建。"""
    pending = session.exec(
        select(PendingChange).where(
            PendingChange.device_id == device.id,
            PendingChange.status == "pending",
        )
    ).first()

    if pending is None:
        pending = PendingChange(
            device_id=device.id,
            source=push.source,
            payload=push.model_dump(mode="json"),
            diff=diff,
        )
    else:
        pending.diff = merge_diff(pending.diff, diff)
        pending.payload = push.model_dump(mode="json")
        pending.source = push.source or pending.source

    session.add(pending)
    session.commit()
    session.refresh(pending)
    return pending
