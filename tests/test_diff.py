"""字段级 diff 服务测试。"""

from cmdb.schemas import DevicePush, MgmtInfo, NicIPIn, NicIn
from cmdb.services.diff import diff_push, merge_diff


def make_push(**overrides) -> DevicePush:
    """构造新格式推送体,可按字段覆盖;旧键名自动映射到新结构。"""
    base = {
        "agent": {"source": "collector", "full_sync": True},
        "os": {"hostname": "S1A01DC-VL101"},
        "mgmt": MgmtInfo(mac="AA:BB:CC:DD:EE:01", ip="192.168.10.101", prefix_length=24),
        "hardware": {
            "chassis_serial_number": "PF4ABC123456",
            "nics": [
                NicIn(name="eth0", mac="AA:BB:CC:DD:EE:02",
                      ips=[NicIPIn(ip="10.10.1.101", prefix_length=24)]),
                NicIn(name="eth1", mac="AA:BB:CC:DD:EE:03",
                      ips=[NicIPIn(ip="10.10.2.101", prefix_length=24)]),
            ],
        },
    }
    # 便捷覆盖:旧键名映射到新结构
    for key in ("nics", "memory", "cpus", "disks", "psus"):
        if key in overrides:
            base["hardware"][key] = overrides.pop(key)
    if "gpus" in overrides:
        base["hardware"]["gpu"] = {"slots": overrides.pop("gpus")}
    if "serial_number" in overrides:
        base["hardware"]["chassis_serial_number"] = overrides.pop("serial_number")
    if "timestamp" in overrides:
        base["agent"]["timestamp"] = overrides.pop("timestamp")
    if "full_sync" in overrides:
        base["agent"]["full_sync"] = overrides.pop("full_sync")
    hostname = overrides.pop("hostname", None)
    if hostname:
        base["os"]["hostname"] = hostname
    base.update(overrides)  # mgmt 等同名字段直接覆盖
    return DevicePush(**base)


def make_snapshot() -> dict:
    """与 make_push 一致的库中快照。"""
    return {
        "serial_number": "PF4ABC123456",
        "mgmt_mac": "AA:BB:CC:DD:EE:01",
        "mgmt_ip": "192.168.10.101",
        "mgmt_prefix_length": 24,
        "nics": {
            "eth0": {"name": "eth0", "mac": "AA:BB:CC:DD:EE:02",
                     "ips": {"10.10.1.101": 24}},
            "eth1": {"name": "eth1", "mac": "AA:BB:CC:DD:EE:03",
                     "ips": {"10.10.2.101": 24}},
        },
    }


def test_no_diff_when_identical():
    diff = diff_push(make_snapshot(), make_push())
    assert diff["has_changes"] is False
    assert diff["fields"] == []
    assert diff["nics"] == []


def test_host_field_diff():
    push = make_push(mgmt=MgmtInfo(mac="AA:BB:CC:DD:EE:01", ip="192.168.10.200",
                                   prefix_length=24))
    diff = diff_push(make_snapshot(), push)
    assert diff["has_changes"] is True
    assert diff["fields"] == [
        {"field": "mgmt.ip", "old": "192.168.10.101", "new": "192.168.10.200"}
    ]


def test_pushed_none_field_skipped():
    """推送体缺 serial_number 视为未采集,不产生 diff、不清空数据。"""
    push = make_push(serial_number=None)
    diff = diff_push(make_snapshot(), push)
    assert diff["has_changes"] is False


def test_nic_added():
    push = make_push(nics=[
        NicIn(name="eth0", mac="AA:BB:CC:DD:EE:02",
              ips=[NicIPIn(ip="10.10.1.101", prefix_length=24)]),
        NicIn(name="eth1", mac="AA:BB:CC:DD:EE:03",
              ips=[NicIPIn(ip="10.10.2.101", prefix_length=24)]),
        NicIn(name="eth2", mac="AA:BB:CC:DD:EE:04", ips=[]),
    ])
    diff = diff_push(make_snapshot(), push)
    assert diff["has_changes"] is True
    assert len(diff["nics"]) == 1
    assert diff["nics"][0]["kind"] == "added"
    assert diff["nics"][0]["name"] == "eth2"
    assert diff["nics"][0]["new"]["mac"] == "AA:BB:CC:DD:EE:04"


def test_nic_changed_mac():
    push = make_push(nics=[
        NicIn(name="eth0", mac="AA:BB:CC:DD:EE:99",
              ips=[NicIPIn(ip="10.10.1.101", prefix_length=24)]),
        NicIn(name="eth1", mac="AA:BB:CC:DD:EE:03",
              ips=[NicIPIn(ip="10.10.2.101", prefix_length=24)]),
    ])
    diff = diff_push(make_snapshot(), push)
    eth0 = next(n for n in diff["nics"] if n["name"] == "eth0")
    assert eth0["kind"] == "changed"
    assert eth0["changes"] == [
        {"field": "mac", "old": "AA:BB:CC:DD:EE:02", "new": "AA:BB:CC:DD:EE:99"}
    ]


def test_nic_changed_ips():
    push = make_push(nics=[
        NicIn(name="eth0", mac="AA:BB:CC:DD:EE:02",
              ips=[NicIPIn(ip="10.10.1.101", prefix_length=24),
                   NicIPIn(ip="10.10.1.102", prefix_length=24)]),
        NicIn(name="eth1", mac="AA:BB:CC:DD:EE:03",
              ips=[NicIPIn(ip="10.10.2.101", prefix_length=24)]),
    ])
    diff = diff_push(make_snapshot(), push)
    eth0 = next(n for n in diff["nics"] if n["name"] == "eth0")
    assert eth0["kind"] == "changed"
    ips_change = next(c for c in eth0["changes"] if c["field"] == "ips")
    assert len(ips_change["old"]) == 1
    assert len(ips_change["new"]) == 2


def test_nic_removed_only_with_full_sync():
    """full_sync=true 时库中多出的网卡进候删;false 时保持不动。"""
    push = make_push(nics=[NicIn(name="eth0", mac="AA:BB:CC:DD:EE:02",
                                 ips=[NicIPIn(ip="10.10.1.101", prefix_length=24)])])

    diff = diff_push(make_snapshot(), push)
    removed = [n for n in diff["nics"] if n["kind"] == "removed"]
    assert len(removed) == 1
    assert removed[0]["name"] == "eth1"
    assert removed[0]["old"]["mac"] == "AA:BB:CC:DD:EE:03"

    push.agent.full_sync = False
    diff = diff_push(make_snapshot(), push)
    assert diff["has_changes"] is False


def test_merge_diff_newest_wins():
    existing = {
        "fields": [{"field": "mgmt.ip", "old": "a", "new": "b"}],
        "nics": [{"name": "eth3", "kind": "added", "changes": [],
                  "old": None, "new": {"name": "eth3"}}],
        "has_changes": True,
    }
    new = {
        "fields": [{"field": "mgmt.ip", "old": "a", "new": "c"},
                   {"field": "serial_number", "old": "x", "new": "y"}],
        "nics": [{"name": "eth3", "kind": "removed", "changes": [],
                  "old": {"name": "eth3"}, "new": None}],
        "has_changes": True,
    }
    merged = merge_diff(existing, new)
    # 同字段以最新推送为准
    mgmt_ip = next(f for f in merged["fields"] if f["field"] == "mgmt.ip")
    assert mgmt_ip["new"] == "c"
    # 新条目追加
    assert any(f["field"] == "serial_number" for f in merged["fields"])
    # removed 覆盖 added
    eth3 = next(n for n in merged["nics"] if n["name"] == "eth3")
    assert eth3["kind"] == "removed"
    assert merged["has_changes"] is True
