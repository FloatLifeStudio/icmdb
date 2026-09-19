"""Push processing: hostname matching, created/unchanged/diff branches, pending merge"""

from datetime import datetime

from sqlmodel import Session, select

from cmdb.models import (
    Cpu,
    Device,
    Disk,
    Gpu,
    MemorySlot,
    Nic,
    NicIP,
    PendingChange,
    Psu,
    normalized_size_gb,
    to_naive_utc,
)
from cmdb.schemas import DevicePush
from cmdb.services.diff import diff_push


def build_snapshot(session: Session, device: Device) -> dict:
    """Build the device's current snapshot from ORM objects, for use by diff"""
    nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
    snapshot = {
        "serial_number": device.serial_number,
        "mgmt_mac": device.mgmt_mac,
        "mgmt_ip": device.mgmt_ip,
        "mgmt_prefix_length": device.mgmt_prefix_length,
        "os_type": device.os_type,
        "os_version": device.os_version,
        "os_virt": device.os_virt,
        "kernel": device.kernel,
        "nics": {},
        "memory": {},
        "cpus": {},
        "disks": {},
        "psus": {},
        "gpus": {},
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
            "size": mem.size,
            "size_unit": mem.size_unit,
            "size_gb": mem.size_gb,
            "speed_mts": mem.speed_mts,
            "serial_number": mem.serial_number,
        }
    for cpu in session.exec(select(Cpu).where(Cpu.device_id == device.id)):
        snapshot["cpus"][cpu.slot] = {"slot": cpu.slot, "model": cpu.model}
    for disk in session.exec(select(Disk).where(Disk.device_id == device.id)):
        snapshot["disks"][disk.serial_number] = {
            "serial_number": disk.serial_number,
            "type": disk.type,
            "manufacturer": disk.manufacturer,
            "model": disk.model,
            "size": disk.size,
            "size_unit": disk.size_unit,
            "size_gb": disk.size_gb,
        }
    for psu in session.exec(select(Psu).where(Psu.device_id == device.id)):
        snapshot["psus"][psu.serial_number] = {
            "serial_number": psu.serial_number,
            "manufacturer": psu.manufacturer,
            "model": psu.model,
            "max_power_w": psu.max_power_w,
        }
    for gpu in session.exec(select(Gpu).where(Gpu.device_id == device.id)):
        snapshot["gpus"][gpu.uuid] = {
            "uuid": gpu.uuid,
            "name": gpu.name,
            "serial_number": gpu.serial_number,
            "size": gpu.size,
            "size_unit": gpu.size_unit,
            "driver_version": gpu.driver_version,
            "pcie_id": gpu.pcie_id,
        }
    return snapshot


def ingest_push(
    session: Session,
    push: DevicePush,
    received_at: datetime,
    update_last_pushed: bool = True,
) -> dict:
    """Process one push, return the three-branch result:

    - hostname not in the DB  -> created (create device + nics + IPs)
    - present with no diff    -> unchanged (only refresh last_pushed_at)
    - has a diff              -> diff_created (merge into pending, existing data untouched)

    When update_last_pushed=False the unchanged branch does not refresh last_pushed_at
    (non-real-push scenarios such as CSV re-import, avoiding regressing the last push time)
    """
    device = session.exec(
        select(Device).where(Device.hostname == push.os.hostname)
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
        if update_last_pushed:
            device.last_pushed_at = to_naive_utc(push.agent.timestamp or received_at)
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
    """Create the device + all hardware from the push body"""
    hw = push.hardware
    device = Device(
        hostname=push.os.hostname,
        serial_number=hw.chassis_serial_number,
        mgmt_mac=push.mgmt.mac,
        mgmt_ip=push.mgmt.ip,
        mgmt_prefix_length=push.mgmt.prefix_length,
        os_type=push.os.type,
        os_version=push.os.version,
        os_virt=push.os.virt,
        kernel=push.os.kernel,
        agent_version=push.agent.version,
        last_pushed_at=to_naive_utc(push.agent.timestamp or received_at),
    )
    session.add(device)
    session.flush()

    for nic in hw.nics:
        _create_nic(session, device.id, nic)
    if hw.memory:
        for mem in hw.memory.slots:
            data = mem.model_dump()
            data["size_gb"] = normalized_size_gb(mem.size, mem.size_unit)
            session.add(MemorySlot(device_id=device.id, **data))
    if hw.cpus:
        for cpu in hw.cpus:
            session.add(Cpu(device_id=device.id, **cpu.model_dump()))
    if hw.disks:
        for disk in hw.disks:
            data = disk.model_dump()
            data["size_gb"] = normalized_size_gb(disk.size, disk.size_unit)
            session.add(Disk(device_id=device.id, **data))
    if hw.psus:
        for psu in hw.psus:
            session.add(Psu(device_id=device.id, **psu.model_dump()))
    if hw.gpu:
        for gpu in hw.gpu.slots:
            data = gpu.model_dump()
            data["size_gb"] = normalized_size_gb(gpu.size, gpu.size_unit)
            session.add(Gpu(device_id=device.id, **data))
    session.commit()
    session.refresh(device)
    return device


def _create_nic(session: Session, device_id: int, nic) -> None:
    """Create a single nic and its IP list"""
    row = Nic(device_id=device_id, name=nic.name, mac=nic.mac)
    session.add(row)
    session.flush()
    for ip in nic.ips:
        session.add(NicIP(nic_id=row.id, ip=ip.ip, prefix_length=ip.prefix_length))


def _merge_into_pending(
    session: Session, device: Device, push: DevicePush, diff: dict
) -> PendingChange:
    """Attach to the device's existing pending (always one), otherwise create a new one

    When an existing pending is unresolved, the latest push wins: the diff computed from the new push
    replaces the old one wholesale (DB data is untouched before resolution, recomputing gives the latest view), never accumulated with the old diff
    """
    pending = session.exec(
        select(PendingChange).where(
            PendingChange.device_id == device.id,
            PendingChange.status == "pending",
        )
    ).first()

    if pending is None:
        pending = PendingChange(
            device_id=device.id,
            source=push.agent.source,
            payload=push.model_dump(mode="json"),
            diff=diff,
        )
    else:
        pending.diff = diff
        pending.payload = push.model_dump(mode="json")
        pending.source = push.agent.source or pending.source

    session.add(pending)
    session.commit()
    session.refresh(pending)
    return pending
