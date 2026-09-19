"""Push processing service tests: three branches, pending merge, real collector example JSON end-to-end"""

import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from cmdb.models import Device, Nic, NicIP, PendingChange
from cmdb.schemas import DevicePush, normalise_legacy
from cmdb.services.ingest import ingest_push

# naive UTC (matches the database storage format)
RECEIVED_AT = datetime(2026, 9, 11, 15, 30, 0)


def make_push(**overrides) -> DevicePush:
    """Build a new-format push payload (2 NICs), overridable per field; legacy keys map onto the new structure"""
    base = {
        "agent": {"source": "collector", "full_sync": True},
        "os": {"hostname": "demo-node-01"},
        "mgmt": {
            "mac": "02:00:00:00:00:01",
            "ip": "192.0.2.11",
            "prefix_length": 24,
        },
        "hardware": {
            "chassis_serial_number": "DEMO-SN-0001",
            "nics": [
                {"name": "eth0", "mac": "02:00:00:00:00:02",
                 "ips": [{"ip": "198.51.100.11", "prefix_length": 24}]},
                {"name": "eth1", "mac": "02:00:00:00:00:03",
                 "ips": [{"ip": "198.51.100.13", "prefix_length": 24}]},
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


def get_device(session: Session, hostname: str) -> Device:
    return session.exec(select(Device).where(Device.hostname == hostname)).one()


def test_created_branch(engine):
    with Session(engine) as session:
        result = ingest_push(session, make_push(), RECEIVED_AT)

        assert result["result"] == "created"
        assert result["pending_change_id"] is None
        device = get_device(session, "demo-node-01")
        assert device.mgmt_ip == "192.0.2.11"
        assert device.last_pushed_at == RECEIVED_AT
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert len(nics) == 2
        ips = session.exec(select(NicIP)).all()
        assert len(ips) == 2


def test_unchanged_branch(engine):
    with Session(engine) as session:
        first = ingest_push(session, make_push(), RECEIVED_AT)
        second = ingest_push(session, make_push(), RECEIVED_AT)

        assert first["result"] == "created"
        assert second["result"] == "unchanged"
        # no duplicate device created
        devices = session.exec(select(Device)).all()
        assert len(devices) == 1
        assert session.exec(select(PendingChange)).all() == []


def test_diff_created_branch(engine):
    with Session(engine) as session:
        ingest_push(session, make_push(), RECEIVED_AT)
        push = make_push(mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                               "prefix_length": 24})
        result = ingest_push(session, push, RECEIVED_AT)

        assert result["result"] == "diff_created"
        assert result["pending_change_id"] is not None
        # existing data unchanged
        device = get_device(session, "demo-node-01")
        assert device.mgmt_ip == "192.0.2.11"
        # pending record created
        pending = session.get(PendingChange, result["pending_change_id"])
        assert pending.status == "pending"
        assert pending.diff["fields"] == [
            {"field": "mgmt.ip", "old": "192.0.2.11", "new": "192.0.2.12"}
        ]


def test_conflict_pushes_replace_with_latest(engine):
    """Multiple unresolved conflict pushes: the latest push's diff wins, no accumulation"""
    with Session(engine) as session:
        ingest_push(session, make_push(), RECEIVED_AT)
        first = ingest_push(
            session,
            make_push(mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                            "prefix_length": 24}),
            RECEIVED_AT,
        )
        second = ingest_push(
            session,
            make_push(serial_number="DEMO-SN-0009"),
            RECEIVED_AT,
        )

        assert first["result"] == "diff_created"
        assert second["result"] == "diff_created"
        # still the same pending record
        assert second["pending_change_id"] == first["pending_change_id"]
        pendings = session.exec(select(PendingChange)).all()
        assert len(pendings) == 1
        diff = pendings[0].diff
        # whole replacement: only the latest push's differences remain (mgmt.ip is back to the db value, no longer pending)
        fields = {f["field"]: f for f in diff["fields"]}
        assert fields["hardware.chassis_serial_number"]["new"] == "DEMO-SN-0009"
        assert "mgmt.ip" not in fields


def test_gpu_added_replaced_by_latest_push(engine):
    """First push of 2 GPUs, then 2 GPUs with different UUIDs while unresolved: the pending change uses the last push"""
    with Session(engine) as session:
        ingest_push(session, make_push(), RECEIVED_AT)
        first = ingest_push(
            session,
            make_push(gpus=[
                {"uuid": "GPU-aaa", "name": "A1"},
                {"uuid": "GPU-bbb", "name": "B1"},
            ]),
            RECEIVED_AT,
        )
        second = ingest_push(
            session,
            make_push(gpus=[
                {"uuid": "GPU-ccc", "name": "C1"},
                {"uuid": "GPU-ddd", "name": "D1"},
            ]),
            RECEIVED_AT,
        )

        assert first["result"] == "diff_created"
        assert second["result"] == "diff_created"
        assert second["pending_change_id"] == first["pending_change_id"]
        pendings = session.exec(select(PendingChange)).all()
        assert len(pendings) == 1
        uuids = {g["uuid"] for g in pendings[0].diff["gpus"]}
        # only the latest push's 2 GPUs kept, not accumulated into 4
        assert uuids == {"GPU-ccc", "GPU-ddd"}


def test_full_sync_removed_nic_in_diff(engine):
    with Session(engine) as session:
        ingest_push(session, make_push(), RECEIVED_AT)
        push = make_push(nics=[
            {"name": "eth0", "mac": "02:00:00:00:00:02",
             "ips": [{"ip": "198.51.100.11", "prefix_length": 24}]},
        ])
        result = ingest_push(session, push, RECEIVED_AT)

        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        removed = [n for n in pending.diff["nics"] if n["kind"] == "removed"]
        assert len(removed) == 1
        assert removed[0]["name"] == "eth1"


def test_push_timestamp_normalized_to_utc(engine):
    """A push timestamp with a timezone is normalized to naive UTC"""
    with Session(engine) as session:
        push = make_push(timestamp=datetime.fromisoformat("2026-09-11T23:30:00+08:00"))
        result = ingest_push(session, push, RECEIVED_AT)
        assert result["result"] == "created"
        device = get_device(session, "demo-node-01")
        assert device.last_pushed_at == datetime(2026, 9, 11, 15, 30, 0)


def test_real_collector_example_json(engine):
    """End-to-end push of a real user collector example JSON (new format, 4 NICs)"""
    example_path = Path(__file__).parent / "data" / "collector_example.json"
    raw = json.loads(example_path.read_text(encoding="utf-8"))
    push = DevicePush(**raw)

    with Session(engine) as session:
        result = ingest_push(session, push, RECEIVED_AT)
        assert result["result"] == "created"

        device = get_device(session, "demo-node-01")
        assert device.serial_number == "DEMO-SN-0001"
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert len(nics) == 4
        # last_pushed_at comes from agent.timestamp (2026-09-13T10:00+08:00 -> UTC)
        assert device.last_pushed_at == datetime(2026, 9, 13, 2, 0, 0)

        # pushing identical data again -> unchanged
        again = ingest_push(session, push, RECEIVED_AT)
        assert again["result"] == "unchanged"


def test_iagent_format_payload(engine):
    """iagent collector real-world format: virt field, null identity entries dropped, ips=null,
    mgmt=null, empty timestamp fallback"""
    raw = {
        "agent": {"version": "0.3.0", "source": "iagent", "timestamp": "",
                  "full_sync": True},
        "os": {
            "hostname": "demo-gpu-02",
            "type": "linux",
            "version": "Ubuntu 22.04",
            "kernel": "5.15.0-91-generic",
            "virt": "kvm",
        },
        "mgmt": None,
        "hardware": {
            "chassis_serial_number": None,
            "nics": [
                {"name": "eth0", "mac": "02:00:00:00:00:2A", "ips": None},
                {"name": "eth1", "mac": None,
                 "ips": [{"ip": "203.0.113.7", "prefix_length": 24}]},
            ],
            "memory": {
                "slots": [
                    {"slot": "DIMM_A1", "size": 32, "size_unit": "GB"},
                    # failed collection slot: slot is null, the whole entry is dropped
                    {"slot": None, "size": None, "size_unit": None},
                ]
            },
            "cpus": [
                {"slot": "CPU0", "model": "Intel(R) Xeon Platinum 8470"},
                {"slot": None, "model": None},
            ],
            "disks": [
                {"serial_number": "DEMO-SN-0004", "type": "SSD",
                 "size": 480, "size_unit": "GB"},
                # SN collection failed -> dropped
                {"serial_number": None, "type": "HDD"},
            ],
            "psus": [{"serial_number": None, "max_power_w": 2700}],
            "gpu": {
                "slots": [
                    {"uuid": "GPU-demo-0002", "name": "NVIDIA A800-SXM4-80GB",
                     "size": 80, "size_unit": "GB"},
                    # uuid collection failed -> dropped
                    {"uuid": None, "name": "NVIDIA A800-SXM4-80GB"},
                ]
            },
        },
    }
    push = DevicePush(**raw)
    # null identity entries are dropped at the schema layer
    assert len(push.hardware.memory.slots) == 1
    assert len(push.hardware.cpus) == 1
    assert len(push.hardware.disks) == 1
    assert len(push.hardware.psus) == 0
    assert len(push.hardware.gpu.slots) == 1

    with Session(engine) as session:
        result = ingest_push(session, push, RECEIVED_AT)
        assert result["result"] == "created"

        device = get_device(session, "demo-gpu-02")
        assert device.os_virt == "kvm"
        assert device.os_type == "linux"
        # empty timestamp -> not collected, falls back to the received time
        assert device.last_pushed_at == RECEIVED_AT
        # mgmt=null -> management interface not written
        assert device.mgmt_mac is None and device.mgmt_ip is None

        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert len(nics) == 2
        nic0 = next(n for n in nics if n.name == "eth0")
        nic1 = next(n for n in nics if n.name == "eth1")
        assert nic0.mac == "02:00:00:00:00:2A"
        # eth0 ips=null -> no IP; eth1 has one
        assert session.exec(
            select(NicIP).where(NicIP.nic_id == nic0.id)
        ).all() == []
        ips1 = session.exec(select(NicIP).where(NicIP.nic_id == nic1.id)).all()
        assert [(i.ip, i.prefix_length) for i in ips1] == [("203.0.113.7", 24)]

        # re-pushing identical data -> unchanged (no pending created)
        again = ingest_push(session, push, RECEIVED_AT)
        assert again["result"] == "unchanged"


def test_iagent_virt_change_goes_to_diff(engine):
    """A virt change goes into the host field diff"""
    with Session(engine) as session:
        first = make_push(
            hostname="demo-node-01",
            os={"hostname": "demo-node-01", "virt": "bare_metal"},
        )
        result = ingest_push(session, first, RECEIVED_AT)
        assert result["result"] == "created"

        second = make_push(
            hostname="demo-node-01",
            os={"hostname": "demo-node-01", "virt": "kvm"},
        )
        result = ingest_push(session, second, RECEIVED_AT)
        assert result["result"] == "diff_created"
        pending = session.exec(select(PendingChange)).first()
        virt_entries = [
            e for e in pending.diff["fields"] if e["field"] == "os.virt"
        ]
        assert virt_entries == [
            {"field": "os.virt", "old": "bare_metal", "new": "kvm"}
        ]
