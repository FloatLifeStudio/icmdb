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

from cmdb.models import ChangeHistory, Device, Nic, NicIP, PendingChange, utcnow

# 主机字段路径 -> Device 属性
_FIELD_ATTRS = {
    "serial_number": "serial_number",
    "mgmt.mac": "mgmt_mac",
    "mgmt.ip": "mgmt_ip",
    "mgmt.prefix_length": "mgmt_prefix_length",
}


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
            )
        )
    session.commit()
    session.refresh(pending)
    return {"applied": summaries, "pending": pending}
