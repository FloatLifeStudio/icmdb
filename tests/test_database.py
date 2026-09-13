"""数据库层冒烟测试:建表、插入、唯一约束、WAL。"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from cmdb.database import init_db, make_engine, migrate
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


def test_migrate_adds_missing_columns(tmp_path):
    """旧库(无 diff 列)迁移后补上新列;旧 tags 列迁到 devicetag 表后删列。"""
    eng = make_engine(str(tmp_path / "old.db"))
    with eng.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE device (id INTEGER PRIMARY KEY, hostname VARCHAR, "
            "tags TEXT NOT NULL DEFAULT '')"
        )
        conn.exec_driver_sql(
            "CREATE TABLE changehistory (id INTEGER PRIMARY KEY, device_id INTEGER, "
            "summary VARCHAR)"
        )
        conn.exec_driver_sql(
            "INSERT INTO device (hostname, tags) VALUES ('old-host', '生产,web')"
        )
        conn.commit()

    init_db(eng)  # 生产流程先 create_all(补建 devicetag 等新表)再迁移
    migrate(eng)
    with eng.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(device)")}
        assert "tags" not in cols  # 旧列已删除
        row = conn.exec_driver_sql(
            "SELECT hostname FROM device WHERE hostname = 'old-host'"
        ).fetchone()
        assert row[0] == "old-host"  # 已有数据保留
        tags = conn.exec_driver_sql(
            "SELECT name FROM devicetag WHERE device_id = 1 ORDER BY id"
        ).fetchall()
        assert [t[0] for t in tags] == ["生产", "web"]  # 旧标签迁入新表
        hcols = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(changehistory)")
        }
        assert "diff" in hcols
