"""裁决应用服务测试:字段选择、网卡增删改、change_history。"""

from datetime import datetime
from sqlmodel import Session, select

from cmdb.models import ChangeHistory, Device, Nic, NicIP, PendingChange
from cmdb.schemas import DevicePush
from cmdb.services.ingest import ingest_push
from cmdb.services.resolve import apply_resolution

RECEIVED_AT = datetime(2026, 9, 11, 15, 30, 0)


def make_push(**overrides) -> DevicePush:
    """构造基础推送体(2 块网卡),可按字段覆盖。"""
    base = {
        "hostname": "S1A01DC-VL101",
        "serial_number": "PF4ABC123456",
        "mgmt": {
            "mac": "AA:BB:CC:DD:EE:01",
            "ip": "192.168.10.101",
            "prefix_length": 24,
        },
        "nics": [
            {"name": "eth0", "mac": "AA:BB:CC:DD:EE:02",
             "ips": [{"ip": "10.10.1.101", "prefix_length": 24}]},
            {"name": "eth1", "mac": "AA:BB:CC:DD:EE:03",
             "ips": [{"ip": "10.10.2.101", "prefix_length": 24}]},
        ],
        "full_sync": True,
        "source": "collector",
    }
    base.update(overrides)
    return DevicePush(**base)


def setup_conflict(session: Session, **push_overrides) -> PendingChange:
    """先创建设备,再推一次有差异的数据,返回待裁决记录。"""
    ingest_push(session, make_push(), RECEIVED_AT)
    result = ingest_push(session, make_push(**push_overrides), RECEIVED_AT)
    assert result["result"] == "diff_created"
    return session.get(PendingChange, result["pending_change_id"])


def test_apply_field_choice_new(engine):
    with Session(engine) as session:
        pending = setup_conflict(
            session, mgmt={"mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.10.200",
                           "prefix_length": 24}
        )
        result = apply_resolution(session, pending, {"mgmt.ip": "new"}, {})

        assert result["applied"] == ["mgmt.ip: 192.168.10.101 -> 192.168.10.200"]
        device = session.get(Device, pending.device_id)
        assert device.mgmt_ip == "192.168.10.200"  # 新值生效
        assert device.serial_number == "PF4ABC123456"  # 未选择的保持不变
        assert pending.status == "applied"
        assert pending.resolved_at is not None
        histories = session.exec(select(ChangeHistory)).all()
        assert len(histories) == 1
        assert histories[0].summary == "mgmt.ip: 192.168.10.101 -> 192.168.10.200"
        assert histories[0].source == "collector"


def test_apply_field_choice_old_keeps_current(engine):
    with Session(engine) as session:
        pending = setup_conflict(
            session, mgmt={"mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.10.200",
                           "prefix_length": 24}
        )
        result = apply_resolution(session, pending, {"mgmt.ip": "old"}, {})

        assert result["applied"] == []  # 保留现状,无生效改动
        device = session.get(Device, pending.device_id)
        assert device.mgmt_ip == "192.168.10.101"
        assert session.exec(select(ChangeHistory)).all() == []
        assert pending.status == "applied"


def test_apply_nic_added(engine):
    with Session(engine) as session:
        pending = setup_conflict(session, nics=[
            {"name": "eth0", "mac": "AA:BB:CC:DD:EE:02",
             "ips": [{"ip": "10.10.1.101", "prefix_length": 24}]},
            {"name": "eth1", "mac": "AA:BB:CC:DD:EE:03",
             "ips": [{"ip": "10.10.2.101", "prefix_length": 24}]},
            {"name": "eth9", "mac": "AA:BB:CC:DD:EE:09",
             "ips": [{"ip": "10.10.9.1", "prefix_length": 24}]},
        ])
        result = apply_resolution(session, pending, {}, {"eth9": "new"})

        assert result["applied"] == ["网卡 eth9 新增"]
        device = session.get(Device, pending.device_id)
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert len(nics) == 3
        eth9 = next(n for n in nics if n.name == "eth9")
        ips = session.exec(select(NicIP).where(NicIP.nic_id == eth9.id)).all()
        assert len(ips) == 1
        assert ips[0].ip == "10.10.9.1"


def test_apply_nic_removed(engine):
    with Session(engine) as session:
        pending = setup_conflict(session, nics=[
            {"name": "eth0", "mac": "AA:BB:CC:DD:EE:02",
             "ips": [{"ip": "10.10.1.101", "prefix_length": 24}]},
        ])
        result = apply_resolution(session, pending, {}, {"eth1": "new"})

        assert result["applied"] == ["网卡 eth1 删除"]
        device = session.get(Device, pending.device_id)
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert [n.name for n in nics] == ["eth0"]  # eth1 连带 IP 已删
        ips = session.exec(select(NicIP)).all()
        assert [ip.ip for ip in ips] == ["10.10.1.101"]


def test_apply_nic_changed(engine):
    with Session(engine) as session:
        pending = setup_conflict(session, nics=[
            {"name": "eth0", "mac": "AA:BB:CC:DD:EE:99",
             "ips": [{"ip": "10.10.1.101", "prefix_length": 24},
                     {"ip": "10.10.1.102", "prefix_length": 24}]},
            {"name": "eth1", "mac": "AA:BB:CC:DD:EE:03",
             "ips": [{"ip": "10.10.2.101", "prefix_length": 24}]},
        ])
        result = apply_resolution(session, pending, {}, {"eth0": "new"})

        assert len(result["applied"]) == 2  # mac + ips 两条
        device = session.get(Device, pending.device_id)
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        eth0 = next(n for n in nics if n.name == "eth0")
        assert eth0.mac == "AA:BB:CC:DD:EE:99"
        ips = session.exec(select(NicIP).where(NicIP.nic_id == eth0.id)).all()
        assert sorted(ip.ip for ip in ips) == ["10.10.1.101", "10.10.1.102"]


def test_apply_mixed_choices(engine):
    """主机字段选新、网卡候删保留,混合裁决。"""
    with Session(engine) as session:
        pending = setup_conflict(session, nics=[
            {"name": "eth0", "mac": "AA:BB:CC:DD:EE:02",
             "ips": [{"ip": "10.10.1.101", "prefix_length": 24}]},
        ])
        result = apply_resolution(session, pending, {"serial_number": "new"},
                                  {"eth1": "old"})

        device = session.get(Device, pending.device_id)
        assert device.serial_number == "PF4ABC123456"  # 与库中相同,选择 new 无实际变化
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert len(nics) == 2  # eth1 保留
        assert result["applied"] == []
        assert session.exec(select(ChangeHistory)).all() == []


def test_history_kept_after_device_delete(engine):
    """设备硬删后 change_history 保留(先删 FK 子表,再删设备)。"""
    with Session(engine) as session:
        pending = setup_conflict(
            session, mgmt={"mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.10.200",
                           "prefix_length": 24}
        )
        apply_resolution(session, pending, {"mgmt.ip": "new"}, {})
        device = session.get(Device, pending.device_id)

        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        for nic in nics:
            for nip in session.exec(select(NicIP).where(NicIP.nic_id == nic.id)).all():
                session.delete(nip)
        session.flush()  # 先删 nic_ips
        for nic in nics:
            session.delete(nic)
        session.flush()  # 再删 nic
        for p in session.exec(
            select(PendingChange).where(PendingChange.device_id == device.id)
        ).all():
            session.delete(p)
        session.flush()  # 再删 pending
        session.delete(device)
        session.commit()

        histories = session.exec(select(ChangeHistory)).all()
        assert len(histories) == 1  # 历史仍在
        assert session.exec(select(PendingChange)).all() == []  # pending 已删
