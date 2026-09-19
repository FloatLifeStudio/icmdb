"""SQLModel table models: device / device_tag / nic / nic_ip / memoryslot / cpu /
disk / psu / pending_change / changehistory"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Uniform naive UTC time (SQLite DATETIME stores and reads without tzinfo)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime) -> datetime:
    """Normalize to naive UTC: timezone-aware values are first converted to UTC, then stripped of tzinfo"""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class Device(SQLModel, table=True):
    """Device main table, hostname is the unique matching key"""

    id: int | None = Field(default=None, primary_key=True)
    hostname: str = Field(unique=True, index=True)
    serial_number: str | None = None
    mgmt_mac: str | None = None
    mgmt_ip: str | None = None
    mgmt_prefix_length: int | None = None
    os_type: str | None = None
    os_version: str | None = None
    kernel: str | None = None
    os_virt: str | None = None
    agent_version: str | None = None
    # CMDB metadata (editable in the UI, untouched by pushes)
    location: str | None = None
    owner: str | None = None
    purpose: str | None = None
    last_pushed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DeviceTag(SQLModel, table=True):
    """Device tags (CMDB metadata, editable in the UI, not collection data)

    One device-tag pair per row, used for exact-match filtering; replaces the old comma-separated TEXT column
    """

    __table_args__ = (UniqueConstraint("device_id", "name"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    name: str = Field(index=True)


class Nic(SQLModel, table=True):
    """Nic table, name is the nic identity (unique within a device)"""

    __table_args__ = (UniqueConstraint("device_id", "name"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    name: str
    mac: str | None = None


class NicIP(SQLModel, table=True):
    """IP table on a nic"""

    __table_args__ = (UniqueConstraint("nic_id", "ip"),)

    id: int | None = Field(default=None, primary_key=True)
    nic_id: int = Field(foreign_key="nic.id", index=True)
    ip: str
    prefix_length: int | None = None


class MemorySlot(SQLModel, table=True):
    """Memory slot table, slot is the identity (unique within a device), e.g. DIMM_A1

    size + size_unit are the raw nominal capacity values; size_gb is the normalized numeric column
    """

    __table_args__ = (UniqueConstraint("device_id", "slot"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    slot: str
    manufacturer: str | None = None
    part_number: str | None = None
    type: str | None = None
    size: int | None = None
    size_unit: str | None = None
    size_gb: int | None = None
    speed_mts: int | None = None
    serial_number: str | None = None


class Gpu(SQLModel, table=True):
    """GPU table, uuid is the identity (unique within a device)

    size + size_unit are the raw nominal VRAM values; size_gb is the normalized numeric column
    """

    __table_args__ = (UniqueConstraint("device_id", "uuid"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    uuid: str
    name: str | None = None
    serial_number: str | None = None
    size: int | None = None
    size_unit: str | None = None
    size_gb: int | None = None
    driver_version: str | None = None
    pcie_id: str | None = None


class Cpu(SQLModel, table=True):
    """CPU slot table, slot is the identity (unique within a device), e.g. CPU0"""

    __table_args__ = (UniqueConstraint("device_id", "slot"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    slot: str
    model: str | None = None


def normalized_size_gb(size: int | None, size_unit: str | None) -> int | None:
    """Normalize capacity to GB (theoretical nominal value): TB converted at 1024, everything else treated as GB"""
    if size is None:
        return None
    return size * 1024 if (size_unit or "").upper() == "TB" else size


class Disk(SQLModel, table=True):
    """Disk table, serial_number is the identity (unique within a device), type is SSD / HDD

    size + size_unit are the raw nominal capacity values; size_gb is the normalized numeric column for easier sorting and statistics
    """

    __table_args__ = (UniqueConstraint("device_id", "serial_number"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    serial_number: str
    type: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    size: int | None = None
    size_unit: str | None = None
    size_gb: int | None = None


class Psu(SQLModel, table=True):
    """PSU module table, serial_number is the identity (unique within a device)"""

    __table_args__ = (UniqueConstraint("device_id", "serial_number"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    serial_number: str
    manufacturer: str | None = None
    model: str | None = None
    max_power_w: int | None = None


class PendingChange(SQLModel, table=True):
    """Conflict pending resolution, one pending per device, new pushes merge into the same one"""

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    source: str | None = None
    # Raw push JSON (includes timestamp / full_sync / source)
    payload: dict = Field(sa_column=Column(JSON))
    # Field-level diff list JSON, structure see services/diff.py
    diff: dict = Field(sa_column=Column(JSON))
    # pending / applied / discarded
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None


class ChangeHistory(SQLModel, table=True):
    """Change history, records only changes applied via resolution

    device_id has no foreign key: records in this table survive hard device deletion, history is independent of device lifetime
    diff stores the full diff list at resolution time, for viewing in the history detail
    """

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(index=True)
    summary: str
    source: str | None = None
    diff: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)


class User(SQLModel, table=True):
    """User table: admin can operate (resolve/delete/tags/user management), viewer can only view"""

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(default="viewer", index=True)  # admin | viewer
    created_at: datetime = Field(default_factory=utcnow)


class SystemSetting(SQLModel, table=True):
    """System setting key-value store (editable online in the UI, environment variables as defaults)"""

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: str
    updated_at: datetime = Field(default_factory=utcnow)


class AuditLog(SQLModel, table=True):
    """Audit log: records users' admin operations (delete/resolve/user management/settings changes etc.)"""

    id: int | None = Field(default=None, primary_key=True)
    username: str | None = Field(default=None, index=True)
    action: str = Field(index=True)
    detail: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
