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
- hostname 是匹配键,不参与 diff
- 推送体中标量字段为 None 视为未采集,不清空库中已有数据
- 网卡身份是 name:同名视为同一块网卡,mac/ips 变化进 changed
- kind=removed 仅在 full_sync=true 时产生(库中多出的网卡候删)
"""

from cmdb.schemas import DevicePush, NicIn

# 主机字段:推送体字段路径 -> 快照键
_HOST_FIELDS = {
    "serial_number": "serial_number",
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


def _host_diff(snapshot: dict, push: DevicePush) -> list[dict]:
    """主机字段级 diff,返回差异条目列表。"""
    pushed = {
        "serial_number": push.serial_number,
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
                {"name": nic.name, "kind": "changed", "changes": changes}
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


def diff_push(snapshot: dict, push: DevicePush) -> dict:
    """比较推送体与库中设备当前快照,返回完整 diff 清单。

    snapshot 由 ingest 层从 ORM 对象构建:
    {"serial_number", "mgmt_mac", "mgmt_ip", "mgmt_prefix_length",
     "nics": {name: {"name", "mac", "ips": {ip: prefix}}}}
    """
    diff = {
        "fields": _host_diff(snapshot, push),
        "nics": _nics_diff(snapshot.get("nics", {}), push.nics, push.full_sync),
    }
    diff["has_changes"] = bool(diff["fields"] or diff["nics"])
    return diff


def merge_diff(existing: dict, new: dict) -> dict:
    """合并同设备的新旧待裁决 diff(始终一条 pending)。

    语义:同一条目(字段路径 / 网卡名)以最新推送为准,新条目追加,去重。
    """
    merged_fields: list[dict] = []
    field_index: dict[str, int] = {}
    for entry in existing.get("fields", []) + new.get("fields", []):
        key = entry["field"]
        if key in field_index:
            merged_fields[field_index[key]] = entry
        else:
            field_index[key] = len(merged_fields)
            merged_fields.append(entry)

    merged_nics: list[dict] = []
    nic_index: dict[str, int] = {}
    for entry in existing.get("nics", []) + new.get("nics", []):
        key = entry["name"]
        if key in nic_index:
            merged_nics[nic_index[key]] = entry
        else:
            nic_index[key] = len(merged_nics)
            merged_nics.append(entry)

    return {
        "fields": merged_fields,
        "nics": merged_nics,
        "has_changes": bool(merged_fields or merged_nics),
    }
