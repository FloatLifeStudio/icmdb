"""推送处理服务测试:三分支、pending 合并、真实采集示例 JSON 端到端。"""

import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from cmdb.models import Device, Nic, NicIP, PendingChange
from cmdb.schemas import DevicePush
from cmdb.services.ingest import ingest_push

# naive UTC(与库中存取格式一致)
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


def get_device(session: Session, hostname: str) -> Device:
    return session.exec(select(Device).where(Device.hostname == hostname)).one()


def test_created_branch(engine):
    with Session(engine) as session:
        result = ingest_push(session, make_push(), RECEIVED_AT)

        assert result["result"] == "created"
        assert result["pending_change_id"] is None
        device = get_device(session, "S1A01DC-VL101")
        assert device.mgmt_ip == "192.168.10.101"
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
        # 不重复建设备
        devices = session.exec(select(Device)).all()
        assert len(devices) == 1
        assert session.exec(select(PendingChange)).all() == []


def test_diff_created_branch(engine):
    with Session(engine) as session:
        ingest_push(session, make_push(), RECEIVED_AT)
        push = make_push(mgmt={"mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.10.200",
                               "prefix_length": 24})
        result = ingest_push(session, push, RECEIVED_AT)

        assert result["result"] == "diff_created"
        assert result["pending_change_id"] is not None
        # 现有数据未变
        device = get_device(session, "S1A01DC-VL101")
        assert device.mgmt_ip == "192.168.10.101"
        # pending 记录生成
        pending = session.get(PendingChange, result["pending_change_id"])
        assert pending.status == "pending"
        assert pending.diff["fields"] == [
            {"field": "mgmt.ip", "old": "192.168.10.101", "new": "192.168.10.200"}
        ]


def test_conflict_pushes_merge_into_one_pending(engine):
    with Session(engine) as session:
        ingest_push(session, make_push(), RECEIVED_AT)
        first = ingest_push(
            session,
            make_push(mgmt={"mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.10.200",
                            "prefix_length": 24}),
            RECEIVED_AT,
        )
        second = ingest_push(
            session,
            make_push(serial_number="PF4ABC999999"),
            RECEIVED_AT,
        )

        assert first["result"] == "diff_created"
        assert second["result"] == "diff_created"
        # 合并进同一条 pending
        assert second["pending_change_id"] == first["pending_change_id"]
        pendings = session.exec(select(PendingChange)).all()
        assert len(pendings) == 1
        diff = pendings[0].diff
        fields = {f["field"]: f for f in diff["fields"]}
        assert fields["mgmt.ip"]["new"] == "192.168.10.200"
        assert fields["serial_number"]["new"] == "PF4ABC999999"


def test_full_sync_removed_nic_in_diff(engine):
    with Session(engine) as session:
        ingest_push(session, make_push(), RECEIVED_AT)
        push = make_push(nics=[
            {"name": "eth0", "mac": "AA:BB:CC:DD:EE:02",
             "ips": [{"ip": "10.10.1.101", "prefix_length": 24}]},
        ])
        result = ingest_push(session, push, RECEIVED_AT)

        assert result["result"] == "diff_created"
        pending = session.get(PendingChange, result["pending_change_id"])
        removed = [n for n in pending.diff["nics"] if n["kind"] == "removed"]
        assert len(removed) == 1
        assert removed[0]["name"] == "eth1"


def test_push_timestamp_normalized_to_utc(engine):
    """推送体 timestamp 带时区时归一化为 naive UTC。"""
    with Session(engine) as session:
        push = make_push(timestamp=datetime.fromisoformat("2026-09-11T23:30:00+08:00"))
        result = ingest_push(session, push, RECEIVED_AT)
        assert result["result"] == "created"
        device = get_device(session, "S1A01DC-VL101")
        assert device.last_pushed_at == datetime(2026, 9, 11, 15, 30, 0)


def test_real_collector_example_json(engine):
    """用户真实采集示例 JSON(4 块网卡)端到端推送。"""
    example_path = Path(__file__).parent / "data" / "collector_example.json"
    raw = json.loads(example_path.read_text(encoding="utf-8"))
    push = DevicePush(**raw)

    with Session(engine) as session:
        result = ingest_push(session, push, RECEIVED_AT)
        assert result["result"] == "created"

        device = get_device(session, "S1A01DC-VL101")
        assert device.serial_number == "PF4ABC123456"
        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert len(nics) == 4
        assert device.last_pushed_at == RECEIVED_AT

        # 再次推送一致数据 -> unchanged
        again = ingest_push(session, push, RECEIVED_AT)
        assert again["result"] == "unchanged"
