"""Resolution application service tests: field choices, NIC add/remove/change, change_history"""

from datetime import datetime
from sqlmodel import Session, select

from cmdb.models import (
    ChangeHistory,
    Cpu,
    Device,
    Disk,
    Gpu,
    MemorySlot,
    Nic,
    NicIP,
    PendingChange,
    Psu,
)
from cmdb.schemas import DevicePush
from cmdb.services.ingest import ingest_push
from cmdb.services.resolve import apply_resolution

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
        base["hardware"]["gpu"] = overrides.pop("gpus")
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


def setup_conflict(session: Session, **push_overrides) -> PendingChange:
    """Create the device first, then push data with differences, return the pending change"""
    ingest_push(session, make_push(), RECEIVED_AT)
    result = ingest_push(session, make_push(**push_overrides), RECEIVED_AT)
    assert result["result"] == "diff_created"
    return session.get(PendingChange, result["pending_change_id"])


def test_apply_field_choice_new(engine):
    with Session(engine) as session:
        pending = setup_conflict(
            session, mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                           "prefix_length": 24}
        )
        result = apply_resolution(session, pending, {"mgmt.ip": "new"}, {})

        assert result["applied"] == ["mgmt.ip: 192.0.2.11 -> 192.0.2.12"]
        device = session.get(Device, pending.device_id)
        assert device.mgmt_ip == "192.0.2.12"  # new value applied
        assert device.serial_number == "DEMO-SN-0001"  # unselected fields unchanged
        assert pending.status == "applied"
        assert pending.resolved_at is not None
        histories = session.exec(select(ChangeHistory)).all()
        assert len(histories) == 1
        assert histories[0].summary == "mgmt.ip: 192.0.2.11 -> 192.0.2.12"
        assert histories[0].source == "collector"


def test_apply_field_choice_old_keeps_current(engine):
    with Session(engine) as session:
        pending = setup_conflict(
            session, mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                           "prefix_length": 24}
        )
        result = apply_resolution(session, pending, {"mgmt.ip": "old"}, {})

        assert result["applied"] == []  # current state kept, no applied changes
        device = session.get(Device, pending.device_id)
        assert device.mgmt_ip == "192.0.2.11"
        assert session.exec(select(ChangeHistory)).all() == []
        assert pending.status == "applied"


def test_apply_nic_added(engine):
    with Session(engine) as session:
        pending = setup_conflict(session, nics=[
            {"name": "eth0", "mac": "02:00:00:00:00:02",
             "ips": [{"ip": "198.51.100.11", "prefix_length": 24}]},
            {"name": "eth1", "mac": "02:00:00:00:00:03",
             "ips": [{"ip": "198.51.100.13", "prefix_length": 24}]},
            {"name": "eth9", "mac": "02:00:00:00:00:09",
             "ips": [{"ip": "198.51.100.19", "prefix_length": 24}]},
        ])
        result = apply_resolution(session, pending, {}, {"eth9": "new"})

        assert result["applied"] == ["网卡 eth9 新增"]
        device = session.get(Device, pending.device_id)
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert len(nics) == 3
        eth9 = next(n for n in nics if n.name == "eth9")
        ips = session.exec(select(NicIP).where(NicIP.nic_id == eth9.id)).all()
        assert len(ips) == 1
        assert ips[0].ip == "198.51.100.19"


def test_apply_nic_removed(engine):
    with Session(engine) as session:
        pending = setup_conflict(session, nics=[
            {"name": "eth0", "mac": "02:00:00:00:00:02",
             "ips": [{"ip": "198.51.100.11", "prefix_length": 24}]},
        ])
        result = apply_resolution(session, pending, {}, {"eth1": "new"})

        assert result["applied"] == ["网卡 eth1 删除"]
        device = session.get(Device, pending.device_id)
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert [n.name for n in nics] == ["eth0"]  # eth1 and its IPs deleted
        ips = session.exec(select(NicIP)).all()
        assert [ip.ip for ip in ips] == ["198.51.100.11"]


def test_apply_nic_changed(engine):
    with Session(engine) as session:
        pending = setup_conflict(session, nics=[
            {"name": "eth0", "mac": "02:00:00:00:00:99",
             "ips": [{"ip": "198.51.100.11", "prefix_length": 24},
                     {"ip": "198.51.100.12", "prefix_length": 24}]},
            {"name": "eth1", "mac": "02:00:00:00:00:03",
             "ips": [{"ip": "198.51.100.13", "prefix_length": 24}]},
        ])
        result = apply_resolution(session, pending, {}, {"eth0": "new"})

        assert len(result["applied"]) == 2  # mac + ips entries
        device = session.get(Device, pending.device_id)
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        eth0 = next(n for n in nics if n.name == "eth0")
        assert eth0.mac == "02:00:00:00:00:99"
        ips = session.exec(select(NicIP).where(NicIP.nic_id == eth0.id)).all()
        assert sorted(ip.ip for ip in ips) == ["198.51.100.11", "198.51.100.12"]


def test_apply_mixed_choices(engine):
    """Host field set to new, removal candidate kept: mixed resolution"""
    with Session(engine) as session:
        pending = setup_conflict(session, nics=[
            {"name": "eth0", "mac": "02:00:00:00:00:02",
             "ips": [{"ip": "198.51.100.11", "prefix_length": 24}]},
        ])
        result = apply_resolution(session, pending, {"serial_number": "new"},
                                  {"eth1": "old"})

        device = session.get(Device, pending.device_id)
        assert device.serial_number == "DEMO-SN-0001"  # same as in db, choosing new has no real change
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert len(nics) == 2  # eth1 kept
        assert result["applied"] == []
        assert session.exec(select(ChangeHistory)).all() == []


def test_history_kept_after_device_delete(engine):
    """change_history survives a hard device delete (delete FK child tables first, then the device)"""
    with Session(engine) as session:
        pending = setup_conflict(
            session, mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                           "prefix_length": 24}
        )
        apply_resolution(session, pending, {"mgmt.ip": "new"}, {})
        device = session.get(Device, pending.device_id)

        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        for nic in nics:
            for nip in session.exec(select(NicIP).where(NicIP.nic_id == nic.id)).all():
                session.delete(nip)
        session.flush()  # delete nic_ips first
        for nic in nics:
            session.delete(nic)
        session.flush()  # then delete nics
        for p in session.exec(
            select(PendingChange).where(PendingChange.device_id == device.id)
        ).all():
            session.delete(p)
        session.flush()  # then delete pendings
        session.delete(device)
        session.commit()

        histories = session.exec(select(ChangeHistory)).all()
        assert len(histories) == 1  # history still there
        assert session.exec(select(PendingChange)).all() == []  # pendings deleted


def memory_slots(*slots) -> dict:
    return {
        "slots": [
            {"slot": s[0], "manufacturer": "Samsung", "part_number": s[1],
             "type": "DDR5", "size": s[2], "size_unit": "GB", "speed_mts": 4800,
             "serial_number": s[3]}
            for s in slots
        ]
    }


def test_apply_memory_added(engine):
    with Session(engine) as session:
        ingest_push(
            session,
            make_push(memory=memory_slots(
                ("DIMM_A1", "PN-A", 64, "111"))),
            RECEIVED_AT,
        )
        result = ingest_push(
            session,
            make_push(memory=memory_slots(
                ("DIMM_A1", "PN-A", 64, "111"), ("DIMM_B1", "PN-B", 64, "222"))),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])

        result = apply_resolution(session, pending, {}, {}, {"DIMM_B1": "new"})
        assert result["applied"] == ["内存 DIMM_B1 新增"]
        slots = session.exec(select(MemorySlot)).all()
        assert [m.slot for m in slots] == ["DIMM_A1", "DIMM_B1"]


def test_apply_memory_removed(engine):
    with Session(engine) as session:
        ingest_push(
            session,
            make_push(memory=memory_slots(
                ("DIMM_A1", "PN-A", 64, "111"), ("DIMM_B1", "PN-B", 64, "222"))),
            RECEIVED_AT,
        )
        result = ingest_push(
            session,
            make_push(memory=memory_slots(("DIMM_A1", "PN-A", 64, "111"))),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])

        result = apply_resolution(session, pending, {}, {}, {"DIMM_B1": "new"})
        assert result["applied"] == ["内存 DIMM_B1 删除"]
        slots = session.exec(select(MemorySlot)).all()
        assert [m.slot for m in slots] == ["DIMM_A1"]


def test_apply_memory_changed(engine):
    with Session(engine) as session:
        ingest_push(
            session,
            make_push(memory=memory_slots(("DIMM_A1", "PN-A", 64, "111"))),
            RECEIVED_AT,
        )
        result = ingest_push(
            session,
            make_push(memory=memory_slots(("DIMM_A1", "PN-B", 32, "111"))),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])

        result = apply_resolution(session, pending, {}, {}, {"DIMM_A1": "new"})
        assert len(result["applied"]) == 2  # part_number + size_gb
        mem = session.exec(select(MemorySlot)).one()
        assert mem.part_number == "PN-B"
        assert mem.size_gb == 32
        assert mem.serial_number == "111"  # unchanged fields kept


def test_apply_cpu_added_and_changed(engine):
    with Session(engine) as session:
        ingest_push(
            session,
            make_push(cpus=[{"slot": "CPU0", "model": "Xeon-6448Y"}]),
            RECEIVED_AT,
        )
        result = ingest_push(
            session,
            make_push(
                cpus=[
                    {"slot": "CPU0", "model": "Xeon-6448Y"},
                    {"slot": "CPU1", "model": "Xeon-6448Y"},
                ]
            ),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        apply_resolution(session, pending, {}, {}, {}, {"CPU1": "new"})
        assert len(session.exec(select(Cpu)).all()) == 2

        # model change
        result = ingest_push(
            session,
            make_push(
                cpus=[
                    {"slot": "CPU0", "model": "Xeon-6548Y"},
                    {"slot": "CPU1", "model": "Xeon-6448Y"},
                ]
            ),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        result = apply_resolution(session, pending, {}, {}, {}, {"CPU0": "new"})
        assert result["applied"] == ["CPU CPU0 model: Xeon-6448Y -> Xeon-6548Y"]
        cpu0 = session.exec(
            select(Cpu).where(Cpu.slot == "CPU0")
        ).one()
        assert cpu0.model == "Xeon-6548Y"


def disks(*specs) -> list[dict]:
    return [
        {"serial_number": sn, "type": t, "manufacturer": m, "model": mdl,
         "size": s, "size_unit": u}
        for sn, t, m, mdl, s, u in specs
    ]


def test_apply_disk_added_removed_and_changed(engine):
    with Session(engine) as session:
        # added
        ingest_push(
            session,
            make_push(disks=disks(
                ("SN1", "SSD", "Samsung", "990EVO", 8, "TB"))),
            RECEIVED_AT,
        )
        result = ingest_push(
            session,
            make_push(disks=disks(
                ("SN1", "SSD", "Samsung", "990EVO", 8, "TB"),
                ("SN2", "HDD", "HGST", "HUH728080ALE604", 8, "TB"))),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        result = apply_resolution(session, pending, {}, {}, {}, {}, {"SN2": "new"})
        assert result["applied"] == ["硬盘 SN2 新增"]
        assert [d.serial_number for d in session.exec(select(Disk)).all()] == ["SN1", "SN2"]

        # model change
        result = ingest_push(
            session,
            make_push(disks=disks(
                ("SN1", "SSD", "Samsung", "990PRO", 8, "TB"),
                ("SN2", "HDD", "HGST", "HUH728080ALE604", 8, "TB"))),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        result = apply_resolution(session, pending, {}, {}, {}, {}, {"SN1": "new"})
        assert result["applied"] == ["硬盘 SN1 model: 990EVO -> 990PRO"]

        # one disk fewer with full_sync -> removal candidate
        result = ingest_push(
            session,
            make_push(disks=disks(("SN1", "SSD", "Samsung", "990PRO", 8, "TB"))),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        result = apply_resolution(session, pending, {}, {}, {}, {}, {"SN2": "new"})
        assert result["applied"] == ["硬盘 SN2 删除"]
        assert [d.serial_number for d in session.exec(select(Disk)).all()] == ["SN1"]


def test_apply_psu_added_and_changed(engine):
    with Session(engine) as session:
        ingest_push(
            session,
            make_push(psus=[{"serial_number": "PSN1", "manufacturer": "GreatWall",
                             "model": "CRPS2700D2", "max_power_w": 2700}]),
            RECEIVED_AT,
        )
        result = ingest_push(
            session,
            make_push(psus=[
                {"serial_number": "PSN1", "manufacturer": "GreatWall",
                 "model": "CRPS2700D2", "max_power_w": 2700},
                {"serial_number": "PSN2", "manufacturer": "GreatWall",
                 "model": "CRPS2700D2", "max_power_w": 2700},
            ]),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        result = apply_resolution(session, pending, {}, {}, {}, {}, {}, {"PSN2": "new"})
        assert result["applied"] == ["电源 PSN2 新增"]
        assert len(session.exec(select(Psu)).all()) == 2

        # power change
        result = ingest_push(
            session,
            make_push(psus=[
                {"serial_number": "PSN1", "manufacturer": "GreatWall",
                 "model": "CRPS2700D2", "max_power_w": 2400},
                {"serial_number": "PSN2", "manufacturer": "GreatWall",
                 "model": "CRPS2700D2", "max_power_w": 2700},
            ]),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        result = apply_resolution(session, pending, {}, {}, {}, {}, {}, {"PSN1": "new"})
        assert result["applied"] == ["电源 PSN1 max_power_w: 2700 -> 2400"]


def gpus(*slots) -> dict:
    return {
        "slots": [
            {"uuid": s[0], "name": s[1], "serial_number": s[2],
             "size": s[3], "size_unit": "GB", "driver_version": "535.0",
             "pcie_id": s[4]}
            for s in slots
        ]
    }


def test_gpu_added_removed_and_changed(engine):
    with Session(engine) as session:
        ingest_push(
            session,
            make_push(gpus=gpus(
                ("GPU-A", "H100", "SN1", 80, "0000:1B:00.0"),
                ("GPU-B", "H100", "SN2", 80, "0000:1C:00.0"),
            )),
            RECEIVED_AT,
        )
        assert len(session.exec(select(Gpu)).all()) == 2

        # one GPU fewer with full_sync -> removal candidate
        result = ingest_push(
            session,
            make_push(gpus=gpus(("GPU-A", "H100", "SN1", 80, "0000:1B:00.0"))),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        result = apply_resolution(
            session, pending, {}, {}, {}, {}, {}, {}, {"GPU-B": "new"}
        )
        assert result["applied"] == ["GPU GPU-B 删除"]
        assert [g.uuid for g in session.exec(select(Gpu)).all()] == ["GPU-A"]

        # driver version change -> changed
        result = ingest_push(
            session,
            make_push(gpus=gpus(
                ("GPU-A", "H100", "SN1", 80, "0000:1B:00.0"),
            )),
            RECEIVED_AT,
        )
        result = ingest_push(
            session,
            make_push(gpus=gpus(
                ("GPU-A", "H100", "SN1", 80, "0000:1B:00.1"),
            )),
            RECEIVED_AT,
        )
        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        result = apply_resolution(
            session, pending, {}, {}, {}, {}, {}, {}, {"GPU-A": "new"}
        )
        assert result["applied"] == [
            "GPU GPU-A pcie_id: 0000:1B:00.0 -> 0000:1B:00.1"
        ]
