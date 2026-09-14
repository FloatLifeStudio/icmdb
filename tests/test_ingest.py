"""推送处理服务测试:三分支、pending 合并、真实采集示例 JSON 端到端。"""

import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from cmdb.models import Device, Nic, NicIP, PendingChange
from cmdb.schemas import DevicePush, normalise_legacy
from cmdb.services.ingest import ingest_push

# naive UTC(与库中存取格式一致)
RECEIVED_AT = datetime(2026, 9, 11, 15, 30, 0)


def make_push(**overrides) -> DevicePush:
    """构造新格式推送体(2 块网卡),可按字段覆盖;旧键名自动映射到新结构。"""
    base = {
        "agent": {"source": "collector", "full_sync": True},
        "os": {"hostname": "S1A01DC-VL101"},
        "mgmt": {
            "mac": "AA:BB:CC:DD:EE:01",
            "ip": "192.168.10.101",
            "prefix_length": 24,
        },
        "hardware": {
            "chassis_serial_number": "PF4ABC123456",
            "nics": [
                {"name": "eth0", "mac": "AA:BB:CC:DD:EE:02",
                 "ips": [{"ip": "10.10.1.101", "prefix_length": 24}]},
                {"name": "eth1", "mac": "AA:BB:CC:DD:EE:03",
                 "ips": [{"ip": "10.10.2.101", "prefix_length": 24}]},
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


def test_conflict_pushes_replace_with_latest(engine):
    """多次冲突推送未裁决:以最新一次推送的 diff 为准,不累计。"""
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
        # 仍是同一条 pending
        assert second["pending_change_id"] == first["pending_change_id"]
        pendings = session.exec(select(PendingChange)).all()
        assert len(pendings) == 1
        diff = pendings[0].diff
        # 整体替换:只剩最新一次推送的差异(mgmt.ip 已回到库中值,不再待裁决)
        fields = {f["field"]: f for f in diff["fields"]}
        assert fields["hardware.chassis_serial_number"]["new"] == "PF4ABC999999"
        assert "mgmt.ip" not in fields


def test_gpu_added_replaced_by_latest_push(engine):
    """第一次推 2 块 GPU,未裁决又推 2 块不同 UUID 的 GPU:待裁决以最后一次为准。"""
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
        # 只保留最新一次推送的 2 块,不累计成 4 块
        assert uuids == {"GPU-ccc", "GPU-ddd"}


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
    """用户真实采集示例 JSON(新格式,4 块网卡)端到端推送。"""
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
        # last_pushed_at 取 agent.timestamp(2026-09-13T10:00+08:00 -> UTC)
        assert device.last_pushed_at == datetime(2026, 9, 13, 2, 0, 0)

        # 再次推送一致数据 -> unchanged
        again = ingest_push(session, push, RECEIVED_AT)
        assert again["result"] == "unchanged"


def test_iagent_format_payload(engine):
    """iagent 采集器实采格式:virt 字段、null 身份条目丢弃、ips=null、
    mgmt=null、timestamp 空串兜底。"""
    raw = {
        "agent": {"version": "0.3.0", "source": "iagent", "timestamp": "",
                  "full_sync": True},
        "os": {
            "hostname": "GPU-NODE-07",
            "type": "linux",
            "version": "Ubuntu 22.04",
            "kernel": "5.15.0-91-generic",
            "virt": "kvm",
        },
        "mgmt": None,
        "hardware": {
            "chassis_serial_number": None,
            "nics": [
                {"name": "eth0", "mac": "D0:8D:7D:C2:F7:2A", "ips": None},
                {"name": "eth1", "mac": None,
                 "ips": [{"ip": "10.20.0.7", "prefix_length": 24}]},
            ],
            "memory": {
                "slots": [
                    {"slot": "DIMM_A1", "size": 32, "size_unit": "GB"},
                    # 采集失败的槽位:slot 为 null,整条丢弃
                    {"slot": None, "size": None, "size_unit": None},
                ]
            },
            "cpus": [
                {"slot": "CPU0", "model": "Intel(R) Xeon Platinum 8470"},
                {"slot": None, "model": None},
            ],
            "disks": [
                {"serial_number": "S5XNX0GF123456", "type": "SSD",
                 "size": 480, "size_unit": "GB"},
                # SN 采集失败 -> 丢弃
                {"serial_number": None, "type": "HDD"},
            ],
            "psus": [{"serial_number": None, "max_power_w": 2700}],
            "gpu": {
                "slots": [
                    {"uuid": "GPU-9a2b3c4d", "name": "NVIDIA A800-SXM4-80GB",
                     "size": 80, "size_unit": "GB"},
                    # uuid 采集失败 -> 丢弃
                    {"uuid": None, "name": "NVIDIA A800-SXM4-80GB"},
                ]
            },
        },
    }
    push = DevicePush(**raw)
    # null 身份条目在 schema 层被丢弃
    assert len(push.hardware.memory.slots) == 1
    assert len(push.hardware.cpus) == 1
    assert len(push.hardware.disks) == 1
    assert len(push.hardware.psus) == 0
    assert len(push.hardware.gpu.slots) == 1

    with Session(engine) as session:
        result = ingest_push(session, push, RECEIVED_AT)
        assert result["result"] == "created"

        device = get_device(session, "GPU-NODE-07")
        assert device.os_virt == "kvm"
        assert device.os_type == "linux"
        # timestamp 空串 -> 未采集,取接收时间兜底
        assert device.last_pushed_at == RECEIVED_AT
        # mgmt=null -> 不写管理口
        assert device.mgmt_mac is None and device.mgmt_ip is None

        nics = session.exec(select(Nic).where(Nic.device_id == device.id)).all()
        assert len(nics) == 2
        nic0 = next(n for n in nics if n.name == "eth0")
        nic1 = next(n for n in nics if n.name == "eth1")
        assert nic0.mac == "D0:8D:7D:C2:F7:2A"
        # eth0 ips=null -> 无 IP;eth1 有 IP
        assert session.exec(
            select(NicIP).where(NicIP.nic_id == nic0.id)
        ).all() == []
        ips1 = session.exec(select(NicIP).where(NicIP.nic_id == nic1.id)).all()
        assert [(i.ip, i.prefix_length) for i in ips1] == [("10.20.0.7", 24)]

        # 一致数据重推 -> unchanged(不产生 pending)
        again = ingest_push(session, push, RECEIVED_AT)
        assert again["result"] == "unchanged"


def test_iagent_virt_change_goes_to_diff(engine):
    """virt 变化进主机字段 diff。"""
    with Session(engine) as session:
        first = make_push(
            hostname="S1A01DC-VL101",
            os={"hostname": "S1A01DC-VL101", "virt": "bare_metal"},
        )
        result = ingest_push(session, first, RECEIVED_AT)
        assert result["result"] == "created"

        second = make_push(
            hostname="S1A01DC-VL101",
            os={"hostname": "S1A01DC-VL101", "virt": "kvm"},
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
