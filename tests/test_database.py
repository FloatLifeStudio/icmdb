"""Database layer smoke tests: table creation, insert, unique constraints, WAL"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from cmdb.database import init_db, make_engine, migrate
from cmdb.models import Device, Nic, NicIP


def _make_device(session: Session) -> Device:
    device = Device(
        hostname="demo-node-01",
        serial_number="DEMO-SN-0001",
        mgmt_mac="02:00:00:00:00:01",
        mgmt_ip="192.0.2.11",
        mgmt_prefix_length=24,
    )
    session.add(device)
    session.flush()
    return device


def test_create_device_with_nics(engine):
    with Session(engine) as session:
        device = _make_device(session)
        nic = Nic(device_id=device.id, name="eth0", mac="02:00:00:00:00:02")
        session.add(nic)
        session.flush()
        session.add(NicIP(nic_id=nic.id, ip="198.51.100.11", prefix_length=24))
        session.commit()

        loaded = session.get(Device, device.id)
        assert loaded.hostname == "demo-node-01"
        assert loaded.last_pushed_at is None


def test_duplicate_hostname_rejected(engine):
    with Session(engine) as session:
        _make_device(session)
        with pytest.raises(IntegrityError):
            session.add(Device(hostname="demo-node-01"))
            session.commit()


def test_duplicate_nic_name_rejected(engine):
    with Session(engine) as session:
        device = _make_device(session)
        session.add(Nic(device_id=device.id, name="eth0", mac="02:00:00:00:00:02"))
        session.commit()
        with pytest.raises(IntegrityError):
            session.add(Nic(device_id=device.id, name="eth0", mac="02:00:00:00:00:09"))
            session.commit()


def test_wal_mode(engine):
    with engine.connect() as conn:
        mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        assert mode == "wal"


def test_migrate_adds_missing_columns(tmp_path):
    """An old database (without diff columns) gains the new columns after migration; the legacy tags column is migrated to the devicetag table then dropped"""
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

    init_db(eng)  # production flow runs create_all first (creates devicetag and other new tables) then migrates
    migrate(eng)
    with eng.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(device)")}
        assert "tags" not in cols  # legacy column dropped
        row = conn.exec_driver_sql(
            "SELECT hostname FROM device WHERE hostname = 'old-host'"
        ).fetchone()
        assert row[0] == "old-host"  # existing data preserved
        tags = conn.exec_driver_sql(
            "SELECT name FROM devicetag WHERE device_id = 1 ORDER BY id"
        ).fetchall()
        assert [t[0] for t in tags] == ["生产", "web"]  # legacy tags migrated into the new table
        hcols = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(changehistory)")
        }
        assert "diff" in hcols
