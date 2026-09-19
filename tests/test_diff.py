"""Field-level diff service tests"""

from cmdb.schemas import DevicePush, MgmtInfo, NicIPIn, NicIn
from cmdb.services.diff import diff_push


def make_push(**overrides) -> DevicePush:
    """Build a new-format push payload, overridable per field; legacy keys map onto the new structure"""
    base = {
        "agent": {"source": "collector", "full_sync": True},
        "os": {"hostname": "demo-node-01"},
        "mgmt": MgmtInfo(mac="02:00:00:00:00:01", ip="192.0.2.11", prefix_length=24),
        "hardware": {
            "chassis_serial_number": "DEMO-SN-0001",
            "nics": [
                NicIn(name="eth0", mac="02:00:00:00:00:02",
                      ips=[NicIPIn(ip="198.51.100.11", prefix_length=24)]),
                NicIn(name="eth1", mac="02:00:00:00:00:03",
                      ips=[NicIPIn(ip="198.51.100.13", prefix_length=24)]),
            ],
        },
    }
    # convenience overrides: legacy keys map onto the new structure
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
    base.update(overrides)  # same-name fields like mgmt override directly
    return DevicePush(**base)


def make_snapshot() -> dict:
    """Database snapshot consistent with make_push"""
    return {
        "serial_number": "DEMO-SN-0001",
        "mgmt_mac": "02:00:00:00:00:01",
        "mgmt_ip": "192.0.2.11",
        "mgmt_prefix_length": 24,
        "nics": {
            "eth0": {"name": "eth0", "mac": "02:00:00:00:00:02",
                     "ips": {"198.51.100.11": 24}},
            "eth1": {"name": "eth1", "mac": "02:00:00:00:00:03",
                     "ips": {"198.51.100.13": 24}},
        },
    }


def test_no_diff_when_identical():
    diff = diff_push(make_snapshot(), make_push())
    assert diff["has_changes"] is False
    assert diff["fields"] == []
    assert diff["nics"] == []


def test_host_field_diff():
    push = make_push(mgmt=MgmtInfo(mac="02:00:00:00:00:01", ip="192.0.2.12",
                                   prefix_length=24))
    diff = diff_push(make_snapshot(), push)
    assert diff["has_changes"] is True
    assert diff["fields"] == [
        {"field": "mgmt.ip", "old": "192.0.2.11", "new": "192.0.2.12"}
    ]


def test_pushed_none_field_skipped():
    """A push missing serial_number is treated as not collected: no diff, no data cleared"""
    push = make_push(serial_number=None)
    diff = diff_push(make_snapshot(), push)
    assert diff["has_changes"] is False


def test_nic_added():
    push = make_push(nics=[
        NicIn(name="eth0", mac="02:00:00:00:00:02",
              ips=[NicIPIn(ip="198.51.100.11", prefix_length=24)]),
        NicIn(name="eth1", mac="02:00:00:00:00:03",
              ips=[NicIPIn(ip="198.51.100.13", prefix_length=24)]),
        NicIn(name="eth2", mac="02:00:00:00:00:04", ips=[]),
    ])
    diff = diff_push(make_snapshot(), push)
    assert diff["has_changes"] is True
    assert len(diff["nics"]) == 1
    assert diff["nics"][0]["kind"] == "added"
    assert diff["nics"][0]["name"] == "eth2"
    assert diff["nics"][0]["new"]["mac"] == "02:00:00:00:00:04"


def test_nic_changed_mac():
    push = make_push(nics=[
        NicIn(name="eth0", mac="02:00:00:00:00:99",
              ips=[NicIPIn(ip="198.51.100.11", prefix_length=24)]),
        NicIn(name="eth1", mac="02:00:00:00:00:03",
              ips=[NicIPIn(ip="198.51.100.13", prefix_length=24)]),
    ])
    diff = diff_push(make_snapshot(), push)
    eth0 = next(n for n in diff["nics"] if n["name"] == "eth0")
    assert eth0["kind"] == "changed"
    assert eth0["changes"] == [
        {"field": "mac", "old": "02:00:00:00:00:02", "new": "02:00:00:00:00:99"}
    ]
    # changed entries carry whole old/new representations for the frontend two-column view
    assert eth0["old"] == {
        "name": "eth0",
        "mac": "02:00:00:00:00:02",
        "ips": [{"ip": "198.51.100.11", "prefix_length": 24}],
    }
    assert eth0["new"]["mac"] == "02:00:00:00:00:99"


def test_nic_changed_ips():
    push = make_push(nics=[
        NicIn(name="eth0", mac="02:00:00:00:00:02",
              ips=[NicIPIn(ip="198.51.100.11", prefix_length=24),
                   NicIPIn(ip="198.51.100.12", prefix_length=24)]),
        NicIn(name="eth1", mac="02:00:00:00:00:03",
              ips=[NicIPIn(ip="198.51.100.13", prefix_length=24)]),
    ])
    diff = diff_push(make_snapshot(), push)
    eth0 = next(n for n in diff["nics"] if n["name"] == "eth0")
    assert eth0["kind"] == "changed"
    ips_change = next(c for c in eth0["changes"] if c["field"] == "ips")
    assert len(ips_change["old"]) == 1
    assert len(ips_change["new"]) == 2


def test_nic_removed_only_with_full_sync():
    """With full_sync=true, extra NICs in the database become removal candidates; with false they are left untouched"""
    push = make_push(nics=[NicIn(name="eth0", mac="02:00:00:00:00:02",
                                 ips=[NicIPIn(ip="198.51.100.11", prefix_length=24)])])

    diff = diff_push(make_snapshot(), push)
    removed = [n for n in diff["nics"] if n["kind"] == "removed"]
    assert len(removed) == 1
    assert removed[0]["name"] == "eth1"
    assert removed[0]["old"]["mac"] == "02:00:00:00:00:03"

    push.agent.full_sync = False
    diff = diff_push(make_snapshot(), push)
    assert diff["has_changes"] is False


