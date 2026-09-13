"""裁决应用:按条目选择新旧、更新设备数据、写 change_history。

裁决请求体约定:

{
  "field_choices": {"mgmt.ip": "new"},          // 主机字段:选新值还是保留旧值
  "nic_choices": {"eth3": "new", "eth1": "old"} // 网卡条目:新增/候删选 new,保留现状选 old
}

统一语义:每条 diff 条目选 "new"(采用新数据)或 "old"(保留现状)。
对 removed 网卡,"new" 即删除该网卡。
"""

from sqlmodel import Session, select

from cmdb.models import (
    ChangeHistory,
    Cpu,
    Device,
    Disk,
    MemorySlot,
    Nic,
    NicIP,
    PendingChange,
    Psu,
    utcnow,
)

# 主机字段路径 -> Device 属性
_FIELD_ATTRS = {
    "serial_number": "serial_number",
    "mgmt.mac": "mgmt_mac",
    "mgmt.ip": "mgmt_ip",
    "mgmt.prefix_length": "mgmt_prefix_length",
}


_MEMORY_FIELDS = (
    "manufacturer",
    "part_number",
    "type",
    "size_gb",
    "speed_mts",
    "serial_number",
)


def _apply_memory(session: Session, device: Device, entry: dict) -> None:
    """按裁决结果处理单个内存槽位条目(kind=added/removed/changed,选择已过滤为 new)。"""
    slot = entry["slot"]
    existing = session.exec(
        select(MemorySlot).where(
            MemorySlot.device_id == device.id, MemorySlot.slot == slot
        )
    ).first()

    if entry["kind"] == "added":
        if existing is not None:  # 已存在(如旧 diff 残留)则幂等跳过
            return
        new = entry["new"]
        session.add(
            MemorySlot(
                device_id=device.id,
                slot=slot,
                manufacturer=new.get("manufacturer"),
                part_number=new.get("part_number"),
                type=new.get("type"),
                size_gb=new.get("size_gb"),
                speed_mts=new.get("speed_mts"),
                serial_number=new.get("serial_number"),
            )
        )
        return

    if entry["kind"] == "removed":
        if existing is None:
            return
        session.delete(existing)
        return

    # kind == changed
    if existing is None:
        return
    for change in entry.get("changes", []):
        if change["field"] in _MEMORY_FIELDS:
            setattr(existing, change["field"], change["new"])


def _apply_cpu(session: Session, device: Device, entry: dict) -> None:
    """按裁决结果处理单个 CPU 槽位条目(kind=added/removed/changed,选择已过滤为 new)。"""
    slot = entry["slot"]
    existing = session.exec(
        select(Cpu).where(Cpu.device_id == device.id, Cpu.slot == slot)
    ).first()

    if entry["kind"] == "added":
        if existing is not None:  # 已存在(如旧 diff 残留)则幂等跳过
            return
        session.add(
            Cpu(device_id=device.id, slot=slot, model=entry["new"].get("model"))
        )
        return

    if entry["kind"] == "removed":
        if existing is None:
            return
        session.delete(existing)
        return

    # kind == changed
    if existing is None:
        return
    for change in entry.get("changes", []):
        if change["field"] == "model":
            existing.model = change["new"]


_DISK_FIELDS = ("type", "manufacturer", "model", "size", "size_unit")
_PSU_FIELDS = ("manufacturer", "model", "max_power_w")


def _apply_disk(session: Session, device: Device, entry: dict) -> None:
    """按裁决结果处理单块硬盘条目(kind=added/removed/changed,选择已过滤为 new)。"""
    sn = entry["serial_number"]
    existing = session.exec(
        select(Disk).where(
            Disk.device_id == device.id, Disk.serial_number == sn
        )
    ).first()

    if entry["kind"] == "added":
        if existing is not None:  # 已存在(如旧 diff 残留)则幂等跳过
            return
        new = entry["new"]
        session.add(
            Disk(
                device_id=device.id,
                serial_number=sn,
                type=new.get("type"),
                manufacturer=new.get("manufacturer"),
                model=new.get("model"),
                size=new.get("size"),
                size_unit=new.get("size_unit"),
            )
        )
        return

    if entry["kind"] == "removed":
        if existing is None:
            return
        session.delete(existing)
        return

    # kind == changed
    if existing is None:
        return
    for change in entry.get("changes", []):
        if change["field"] in _DISK_FIELDS:
            setattr(existing, change["field"], change["new"])


def _apply_psu(session: Session, device: Device, entry: dict) -> None:
    """按裁决结果处理单个电源模块条目(kind=added/removed/changed,选择已过滤为 new)。"""
    sn = entry["serial_number"]
    existing = session.exec(
        select(Psu).where(
            Psu.device_id == device.id, Psu.serial_number == sn
        )
    ).first()

    if entry["kind"] == "added":
        if existing is not None:  # 已存在(如旧 diff 残留)则幂等跳过
            return
        new = entry["new"]
        session.add(
            Psu(
                device_id=device.id,
                serial_number=sn,
                manufacturer=new.get("manufacturer"),
                model=new.get("model"),
                max_power_w=new.get("max_power_w"),
            )
        )
        return

    if entry["kind"] == "removed":
        if existing is None:
            return
        session.delete(existing)
        return

    # kind == changed
    if existing is None:
        return
    for change in entry.get("changes", []):
        if change["field"] in _PSU_FIELDS:
            setattr(existing, change["field"], change["new"])


def _apply_nic(session: Session, device: Device, entry: dict) -> None:
    """按裁决结果处理单个网卡条目(kind=added/removed/changed,选择已过滤为 new)。"""
    kind = entry["kind"]
    name = entry["name"]
    existing = session.exec(
        select(Nic).where(Nic.device_id == device.id, Nic.name == name)
    ).first()

    if kind == "added":
        if existing is not None:  # 已存在(如旧 diff 残留)则幂等跳过
            return
        nic = Nic(device_id=device.id, name=name, mac=entry["new"].get("mac"))
        session.add(nic)
        session.flush()
        for ip in entry["new"].get("ips", []):
            session.add(
                NicIP(nic_id=nic.id, ip=ip["ip"], prefix_length=ip["prefix_length"])
            )
        return

    if kind == "removed":
        if existing is None:
            return
        for nip in session.exec(select(NicIP).where(NicIP.nic_id == existing.id)).all():
            session.delete(nip)
        session.flush()  # 先删子表;无 relationship 时 UoW 删除顺序不保证
        session.delete(existing)
        return

    # kind == changed
    if existing is None:
        return
    for change in entry.get("changes", []):
        if change["field"] == "mac":
            existing.mac = change["new"]
        elif change["field"] == "ips":
            new_ips = {ip["ip"]: ip["prefix_length"] for ip in change["new"]}
            current = session.exec(select(NicIP).where(NicIP.nic_id == existing.id)).all()
            for nip in current:  # 删除新列表里没有的
                if nip.ip not in new_ips:
                    session.delete(nip)
            for ip, prefix in new_ips.items():  # 补上缺的
                if not any(nip.ip == ip for nip in current):
                    session.add(NicIP(nic_id=existing.id, ip=ip, prefix_length=prefix))


def apply_resolution(
    session: Session,
    pending: PendingChange,
    field_choices: dict[str, str],
    nic_choices: dict[str, str],
    memory_choices: dict[str, str] | None = None,
    cpu_choices: dict[str, str] | None = None,
    disk_choices: dict[str, str] | None = None,
    psu_choices: dict[str, str] | None = None,
) -> dict:
    """应用裁决:选择 new 的条目生效,选择 old 的保留现状。

    返回 {"applied": [生效摘要], "pending": PendingChange}。
    pending 标记 applied;有实际改动时写 change_history。
    """
    device = session.get(Device, pending.device_id)
    if device is None:
        raise ValueError(f"device {pending.device_id} 不存在")

    summaries: list[str] = []

    for entry in pending.diff.get("fields", []):
        choice = field_choices.get(entry["field"])
        if choice != "new":
            continue
        attr = _FIELD_ATTRS.get(entry["field"])
        if attr is None:
            continue
        setattr(device, attr, entry["new"])
        summaries.append(f"{entry['field']}: {entry['old']} -> {entry['new']}")

    for entry in pending.diff.get("nics", []):
        choice = nic_choices.get(entry["name"])
        if choice != "new":
            continue
        if entry["kind"] == "added":
            summaries.append(f"网卡 {entry['name']} 新增")
        elif entry["kind"] == "removed":
            summaries.append(f"网卡 {entry['name']} 删除")
        else:
            for change in entry.get("changes", []):
                if change["field"] == "mac":
                    summaries.append(
                        f"网卡 {entry['name']} mac: {change['old']} -> {change['new']}"
                    )
                elif change["field"] == "ips":
                    summaries.append(
                        f"网卡 {entry['name']} ips 变更为 "
                        f"{[ip['ip'] for ip in change['new']]}"
                    )
        _apply_nic(session, device, entry)

    for entry in pending.diff.get("memory", []):
        choice = (memory_choices or {}).get(entry["slot"])
        if choice != "new":
            continue
        if entry["kind"] == "added":
            summaries.append(f"内存 {entry['slot']} 新增")
        elif entry["kind"] == "removed":
            summaries.append(f"内存 {entry['slot']} 删除")
        else:
            for change in entry.get("changes", []):
                summaries.append(
                    f"内存 {entry['slot']} {change['field']}: "
                    f"{change['old']} -> {change['new']}"
                )
        _apply_memory(session, device, entry)

    for entry in pending.diff.get("cpus", []):
        choice = (cpu_choices or {}).get(entry["slot"])
        if choice != "new":
            continue
        if entry["kind"] == "added":
            summaries.append(f"CPU {entry['slot']} 新增")
        elif entry["kind"] == "removed":
            summaries.append(f"CPU {entry['slot']} 删除")
        else:
            for change in entry.get("changes", []):
                summaries.append(
                    f"CPU {entry['slot']} {change['field']}: "
                    f"{change['old']} -> {change['new']}"
                )
        _apply_cpu(session, device, entry)

    for entry in pending.diff.get("disks", []):
        choice = (disk_choices or {}).get(entry["serial_number"])
        if choice != "new":
            continue
        if entry["kind"] == "added":
            summaries.append(f"硬盘 {entry['serial_number']} 新增")
        elif entry["kind"] == "removed":
            summaries.append(f"硬盘 {entry['serial_number']} 删除")
        else:
            for change in entry.get("changes", []):
                summaries.append(
                    f"硬盘 {entry['serial_number']} {change['field']}: "
                    f"{change['old']} -> {change['new']}"
                )
        _apply_disk(session, device, entry)

    for entry in pending.diff.get("psus", []):
        choice = (psu_choices or {}).get(entry["serial_number"])
        if choice != "new":
            continue
        if entry["kind"] == "added":
            summaries.append(f"电源 {entry['serial_number']} 新增")
        elif entry["kind"] == "removed":
            summaries.append(f"电源 {entry['serial_number']} 删除")
        else:
            for change in entry.get("changes", []):
                summaries.append(
                    f"电源 {entry['serial_number']} {change['field']}: "
                    f"{change['old']} -> {change['new']}"
                )
        _apply_psu(session, device, entry)

    pending.status = "applied"
    pending.resolved_at = utcnow()
    device.updated_at = utcnow()
    session.add(pending)
    session.add(device)

    if summaries:
        session.add(
            ChangeHistory(
                device_id=device.id,
                summary="; ".join(summaries),
                source=pending.source,
                diff=pending.diff,
            )
        )
    session.commit()
    session.refresh(pending)
    return {"applied": summaries, "pending": pending}
