"""数据库层冒烟测试:建表、插入、唯一约束、WAL。"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from cmdb.models import Device, Nic, NicIP


def _make_device(session: Session) -> Device:
    device = Device(
        hostname="S1A01DC-VL101",
        serial_number="PF4ABC123456",
        mgmt_mac="AA:BB:CC:DD:EE:01",
        mgmt_ip="192.168.10.101",
        mgmt_prefix_length=24,
    )
    session.add(device)
    session.flush()
    return device


def test_create_device_with_nics(engine):
    with Session(engine) as session:
        device = _make_device(session)
        nic = Nic(device_id=device.id, name="eth0", mac="AA:BB:CC:DD:EE:02")
        session.add(nic)
        session.flush()
        session.add(NicIP(nic_id=nic.id, ip="10.10.1.101", prefix_length=24))
        session.commit()

        loaded = session.get(Device, device.id)
        assert loaded.hostname == "S1A01DC-VL101"
        assert loaded.last_pushed_at is None


def test_duplicate_hostname_rejected(engine):
    with Session(engine) as session:
        _make_device(session)
        with pytest.raises(IntegrityError):
            session.add(Device(hostname="S1A01DC-VL101"))
            session.commit()


def test_duplicate_nic_name_rejected(engine):
    with Session(engine) as session:
        device = _make_device(session)
        session.add(Nic(device_id=device.id, name="eth0", mac="AA:BB:CC:DD:EE:02"))
        session.commit()
        with pytest.raises(IntegrityError):
            session.add(Nic(device_id=device.id, name="eth0", mac="AA:BB:CC:DD:EE:09"))
            session.commit()


def test_wal_mode(engine):
    with engine.connect() as conn:
        mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        assert mode == "wal"
