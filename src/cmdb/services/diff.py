"""字段级 diff:比较推送体与库中当前快照。

diff 结构约定(pending_changes.diff 存的就是它):

{
  "fields": [ {"field": "mgmt.ip", "old": ..., "new": ...} ],
  "nics": [
    {"name": "eth1", "kind": "added|removed|changed",
     "changes": [ {"field": "mac"|"ips", "old": ..., "new": ...} ],
     "old": {...完整旧网卡}|null, "new": {...完整新网卡}|null }
  ],
  "has_changes": true
}

语义:
- os.hostname 是匹配键,不参与 diff
- 推送体中标量字段为 None 视为未采集,不清空库中已有数据
- 硬件条目身份:网卡 name、内存/CPU slot、硬盘/电源 serial_number、GPU uuid
- kind=removed 仅在 agent.full_sync=true 时产生(库中多出的条目候删)
"""

from cmdb.schemas import (
    CpuSlotIn,
    DevicePush,
    DiskIn,
    GpuSlotIn,
    MemorySlotIn,
    NicIn,
    PsuIn,
)

# 主机字段:推送体字段路径 -> 快照键
_HOST_FIELDS = {
    "hardware.chassis_serial_number": "serial_number",
    "os.type": "os_type",
    "os.version": "os_version",
    "os.virt": "os_virt",
    "os.kernel": "kernel",
    "mgmt.mac": "mgmt_mac",
    "mgmt.ip": "mgmt_ip",
    "mgmt.prefix_length": "mgmt_prefix_length",
}


def _nic_repr(nic: NicIn) -> dict:
    """网卡的完整表示,用于 added/removed 条目。"""
    return {
        "name": nic.name,
        "mac": nic.mac,
        "ips": [{"ip": ip.ip, "prefix_length": ip.prefix_length} for ip in nic.ips],
    }


def _memory_repr(mem: MemorySlotIn) -> dict:
    """内存槽位的完整表示,用于 added 条目。"""
    return {
        "slot": mem.slot,
        "manufacturer": mem.manufacturer,
        "part_number": mem.part_number,
        "type": mem.type,
        "size": mem.size,
        "size_unit": mem.size_unit,
        "speed_mts": mem.speed_mts,
        "serial_number": mem.serial_number,
    }


def _gpu_repr(gpu: GpuSlotIn) -> dict:
    """GPU 的完整表示,用于 added 条目。"""
    return {
        "uuid": gpu.uuid,
        "name": gpu.name,
        "serial_number": gpu.serial_number,
        "size": gpu.size,
        "size_unit": gpu.size_unit,
        "driver_version": gpu.driver_version,
        "pcie_id": gpu.pcie_id,
    }


def _host_diff(snapshot: dict, push: DevicePush) -> list[dict]:
    """主机字段级 diff,返回差异条目列表。"""
    pushed = {
        "hardware.chassis_serial_number": push.hardware.chassis_serial_number,
        "os.type": push.os.type,
        "os.version": push.os.version,
        "os.virt": push.os.virt,
        "os.kernel": push.os.kernel,
        "mgmt.mac": push.mgmt.mac,
        "mgmt.ip": push.mgmt.ip,
        "mgmt.prefix_length": push.mgmt.prefix_length,
    }
    entries = []
    for field, new in pushed.items():
        if new is None:
            continue
        old = snapshot.get(_HOST_FIELDS[field])
        if new != old:
            entries.append({"field": field, "old": old, "new": new})
    return entries


def _nics_diff(
    snapshot_nics: dict[str, dict], pushed_nics: list[NicIn], full_sync: bool
) -> list[dict]:
    """网卡级 diff。snapshot_nics: {name: {"name", "mac", "ips": {ip: prefix}}}。"""
    entries: list[dict] = []
    pushed_names = set()

    for nic in pushed_nics:
        pushed_names.add(nic.name)
        old = snapshot_nics.get(nic.name)
        if old is None:
            entries.append(
                {
                    "name": nic.name,
                    "kind": "added",
                    "changes": [],
                    "old": None,
                    "new": _nic_repr(nic),
                }
            )
            continue

        changes = []
        if nic.mac and nic.mac != old.get("mac"):
            changes.append({"field": "mac", "old": old.get("mac"), "new": nic.mac})

        new_ips = sorted(
            ({"ip": n.ip, "prefix_length": n.prefix_length} for n in nic.ips),
            key=lambda x: x["ip"],
        )
        old_ips = sorted(
            (
                {"ip": ip, "prefix_length": prefix}
                for ip, prefix in old.get("ips", {}).items()
            ),
            key=lambda x: x["ip"],
        )
        if new_ips != old_ips:
            changes.append({"field": "ips", "old": old_ips, "new": new_ips})

        if changes:
            entries.append(
                {
                    "name": nic.name,
                    "kind": "changed",
                    "changes": changes,
                    "old": {
                        "name": nic.name,
                        "mac": old.get("mac"),
                        "ips": old_ips,
                    },
                    "new": _nic_repr(nic),
                }
            )

    if full_sync:
        for name, old in sorted(snapshot_nics.items()):
            if name not in pushed_names:
                entries.append(
                    {
                        "name": name,
                        "kind": "removed",
                        "changes": [],
                        "old": {
                            "name": name,
                            "mac": old.get("mac"),
                            "ips": sorted(
                                (
                                    {"ip": ip, "prefix_length": prefix}
                                    for ip, prefix in old.get("ips", {}).items()
                                ),
                                key=lambda x: x["ip"],
                            ),
                        },
                        "new": None,
                    }
                )

    return entries


def _memory_diff(
    snapshot_memory: dict[str, dict],
    pushed_slots: list[MemorySlotIn],
    full_sync: bool,
) -> list[dict]:
    """内存槽位级 diff。snapshot_memory: {slot: {字段: 值}}。"""
    entries: list[dict] = []
    pushed_slots_names = set()

    for mem in pushed_slots:
        pushed_slots_names.add(mem.slot)
        old = snapshot_memory.get(mem.slot)
        if old is None:
            entries.append(
                {
                    "slot": mem.slot,
                    "kind": "added",
                    "changes": [],
                    "old": None,
                    "new": _memory_repr(mem),
                }
            )
            continue

        changes = []
        pushed_fields = {
            "manufacturer": mem.manufacturer,
            "part_number": mem.part_number,
            "type": mem.type,
            "size": mem.size,
            "size_unit": mem.size_unit,
            "speed_mts": mem.speed_mts,
            "serial_number": mem.serial_number,
        }
        for field, new in pushed_fields.items():
            if new is None:
                continue
            if new != old.get(field):
                changes.append({"field": field, "old": old.get(field), "new": new})
        if changes:
            entries.append(
                {
                    "slot": mem.slot,
                    "kind": "changed",
                    "changes": changes,
                    "old": old,
                    "new": _memory_repr(mem),
                }
            )

    if full_sync:
        for slot, old in sorted(snapshot_memory.items()):
            if slot not in pushed_slots_names:
                entries.append(
                    {
                        "slot": slot,
                        "kind": "removed",
                        "changes": [],
                        "old": old,
                        "new": None,
                    }
                )

    return entries


def _cpu_diff(
    snapshot_cpus: dict[str, dict],
    pushed_cpus: list[CpuSlotIn],
    full_sync: bool,
) -> list[dict]:
    """CPU 槽位级 diff。snapshot_cpus: {slot: {"slot", "model"}}。"""
    entries: list[dict] = []
    pushed_slots = set()

    for cpu in pushed_cpus:
        pushed_slots.add(cpu.slot)
        old = snapshot_cpus.get(cpu.slot)
        if old is None:
            entries.append(
                {
                    "slot": cpu.slot,
                    "kind": "added",
                    "changes": [],
                    "old": None,
                    "new": {"slot": cpu.slot, "model": cpu.model},
                }
            )
            continue

        if cpu.model and cpu.model != old.get("model"):
            entries.append(
                {
                    "slot": cpu.slot,
                    "kind": "changed",
                    "changes": [
                        {"field": "model", "old": old.get("model"), "new": cpu.model}
                    ],
                    "old": old,
                    "new": {"slot": cpu.slot, "model": cpu.model},
                }
            )

    if full_sync:
        for slot, old in sorted(snapshot_cpus.items()):
            if slot not in pushed_slots:
                entries.append(
                    {
                        "slot": slot,
                        "kind": "removed",
                        "changes": [],
                        "old": old,
                        "new": None,
                    }
                )

    return entries


def _disk_diff(
    snapshot_disks: dict[str, dict],
    pushed_disks: list[DiskIn],
    full_sync: bool,
) -> list[dict]:
    """硬盘级 diff。身份 serial_number。snapshot_disks: {sn: {字段: 值}}。"""
    entries: list[dict] = []
    pushed_sns = set()

    for disk in pushed_disks:
        pushed_sns.add(disk.serial_number)
        old = snapshot_disks.get(disk.serial_number)
        if old is None:
            entries.append(
                {
                    "serial_number": disk.serial_number,
                    "kind": "added",
                    "changes": [],
                    "old": None,
                    "new": {
                        "serial_number": disk.serial_number,
                        "type": disk.type,
                        "manufacturer": disk.manufacturer,
                        "model": disk.model,
                        "size": disk.size,
                        "size_unit": disk.size_unit,
                    },
                }
            )
            continue

        changes = []
        pushed_fields = {
            "type": disk.type,
            "manufacturer": disk.manufacturer,
            "model": disk.model,
            "size": disk.size,
            "size_unit": disk.size_unit,
        }
        for field, new in pushed_fields.items():
            if new is None:
                continue
            if new != old.get(field):
                changes.append({"field": field, "old": old.get(field), "new": new})
        if changes:
            entries.append(
                {
                    "serial_number": disk.serial_number,
                    "kind": "changed",
                    "changes": changes,
                    "old": old,
                    "new": {
                        "serial_number": disk.serial_number,
                        "type": disk.type,
                        "manufacturer": disk.manufacturer,
                        "model": disk.model,
                        "size": disk.size,
                        "size_unit": disk.size_unit,
                    },
                }
            )

    if full_sync:
        for sn, old in sorted(snapshot_disks.items()):
            if sn not in pushed_sns:
                entries.append(
                    {
                        "serial_number": sn,
                        "kind": "removed",
                        "changes": [],
                        "old": old,
                        "new": None,
                    }
                )

    return entries


def _psu_diff(
    snapshot_psus: dict[str, dict],
    pushed_psus: list[PsuIn],
    full_sync: bool,
) -> list[dict]:
    """电源模块级 diff。身份 serial_number。snapshot_psus: {sn: {字段: 值}}。"""
    entries: list[dict] = []
    pushed_sns = set()

    for psu in pushed_psus:
        pushed_sns.add(psu.serial_number)
        old = snapshot_psus.get(psu.serial_number)
        if old is None:
            entries.append(
                {
                    "serial_number": psu.serial_number,
                    "kind": "added",
                    "changes": [],
                    "old": None,
                    "new": {
                        "serial_number": psu.serial_number,
                        "manufacturer": psu.manufacturer,
                        "model": psu.model,
                        "max_power_w": psu.max_power_w,
                    },
                }
            )
            continue

        changes = []
        pushed_fields = {
            "manufacturer": psu.manufacturer,
            "model": psu.model,
            "max_power_w": psu.max_power_w,
        }
        for field, new in pushed_fields.items():
            if new is None:
                continue
            if new != old.get(field):
                changes.append({"field": field, "old": old.get(field), "new": new})
        if changes:
            entries.append(
                {
                    "serial_number": psu.serial_number,
                    "kind": "changed",
                    "changes": changes,
                    "old": old,
                    "new": {
                        "serial_number": psu.serial_number,
                        "manufacturer": psu.manufacturer,
                        "model": psu.model,
                        "max_power_w": psu.max_power_w,
                    },
                }
            )

    if full_sync:
        for sn, old in sorted(snapshot_psus.items()):
            if sn not in pushed_sns:
                entries.append(
                    {
                        "serial_number": sn,
                        "kind": "removed",
                        "changes": [],
                        "old": old,
                        "new": None,
                    }
                )

    return entries


def _gpu_diff(
    snapshot_gpus: dict[str, dict],
    pushed_gpus: list[GpuSlotIn],
    full_sync: bool,
) -> list[dict]:
    """GPU 级 diff。身份 uuid。snapshot_gpus: {uuid: {字段: 值}}。"""
    entries: list[dict] = []
    pushed_uuids = set()

    for gpu in pushed_gpus:
        pushed_uuids.add(gpu.uuid)
        old = snapshot_gpus.get(gpu.uuid)
        if old is None:
            entries.append(
                {
                    "uuid": gpu.uuid,
                    "kind": "added",
                    "changes": [],
                    "old": None,
                    "new": _gpu_repr(gpu),
                }
            )
            continue

        changes = []
        pushed_fields = {
            "name": gpu.name,
            "serial_number": gpu.serial_number,
            "size": gpu.size,
            "size_unit": gpu.size_unit,
            "driver_version": gpu.driver_version,
            "pcie_id": gpu.pcie_id,
        }
        for field, new in pushed_fields.items():
            if new is None:
                continue
            if new != old.get(field):
                changes.append({"field": field, "old": old.get(field), "new": new})
        if changes:
            entries.append(
                {
                    "uuid": gpu.uuid,
                    "kind": "changed",
                    "changes": changes,
                    "old": old,
                    "new": _gpu_repr(gpu),
                }
            )

    if full_sync:
        for uuid_, old in sorted(snapshot_gpus.items()):
            if uuid_ not in pushed_uuids:
                entries.append(
                    {
                        "uuid": uuid_,
                        "kind": "removed",
                        "changes": [],
                        "old": old,
                        "new": None,
                    }
                )

    return entries


def diff_push(snapshot: dict, push: DevicePush) -> dict:
    """比较推送体与库中设备当前快照,返回完整 diff 清单。

    snapshot 由 ingest 层从 ORM 对象构建:
    {"serial_number", "mgmt_mac", "mgmt_ip", "mgmt_prefix_length",
     "os_type", "os_version", "kernel",
     "nics": {name: {...}}, "memory": {slot: {...}}, "cpus": {slot: {...}},
     "disks": {sn: {...}}, "psus": {sn: {...}}, "gpus": {uuid: {...}}}
    """
    hw = push.hardware
    diff = {
        "fields": _host_diff(snapshot, push),
        "nics": _nics_diff(snapshot.get("nics", {}), hw.nics, push.agent.full_sync),
        "memory": _memory_diff(
            snapshot.get("memory", {}), (hw.memory.slots if hw.memory else []),
            push.agent.full_sync,
        ),
        "cpus": _cpu_diff(
            snapshot.get("cpus", {}), (hw.cpus if hw.cpus else []),
            push.agent.full_sync,
        ),
        "disks": _disk_diff(
            snapshot.get("disks", {}), (hw.disks if hw.disks else []),
            push.agent.full_sync,
        ),
        "psus": _psu_diff(
            snapshot.get("psus", {}), (hw.psus if hw.psus else []),
            push.agent.full_sync,
        ),
        "gpus": _gpu_diff(
            snapshot.get("gpus", {}), (hw.gpu.slots if hw.gpu else []),
            push.agent.full_sync,
        ),
    }
    diff["has_changes"] = bool(
        diff["fields"] or diff["nics"] or diff["memory"] or diff["cpus"]
        or diff["disks"] or diff["psus"] or diff["gpus"]
    )
    return diff
