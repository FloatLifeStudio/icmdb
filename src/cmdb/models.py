"""SQLModel 表模型:device / device_tag / nic / nic_ip / memoryslot / cpu /
disk / psu / pending_change / changehistory。"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """统一 naive UTC 时间(SQLite DATETIME 存取不带 tzinfo)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime) -> datetime:
    """归一化为 naive UTC:带时区先转 UTC 再去 tzinfo。"""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class Device(SQLModel, table=True):
    """主机主表,hostname 为唯一匹配键。"""

    id: int | None = Field(default=None, primary_key=True)
    hostname: str = Field(unique=True, index=True)
    serial_number: str | None = None
    mgmt_mac: str | None = None
    mgmt_ip: str | None = None
    mgmt_prefix_length: int | None = None
    last_pushed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DeviceTag(SQLModel, table=True):
    """设备标签(CMDB 元数据,UI 可编辑,不属于采集数据)。

    一行一个 device-tag 对,精确匹配筛选;替代旧的逗号分隔 TEXT 列。
    """

    __table_args__ = (UniqueConstraint("device_id", "name"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    name: str = Field(index=True)


class Nic(SQLModel, table=True):
    """网卡表,name 为网卡身份(device 内唯一)。"""

    __table_args__ = (UniqueConstraint("device_id", "name"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    name: str
    mac: str | None = None


class NicIP(SQLModel, table=True):
    """网卡上的 IP 表。"""

    __table_args__ = (UniqueConstraint("nic_id", "ip"),)

    id: int | None = Field(default=None, primary_key=True)
    nic_id: int = Field(foreign_key="nic.id", index=True)
    ip: str
    prefix_length: int | None = None


class MemorySlot(SQLModel, table=True):
    """内存槽位表,slot 为身份(device 内唯一),如 DIMM_A1。"""

    __table_args__ = (UniqueConstraint("device_id", "slot"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    slot: str
    manufacturer: str | None = None
    part_number: str | None = None
    type: str | None = None
    size_gb: int | None = None
    speed_mts: int | None = None
    serial_number: str | None = None


class Cpu(SQLModel, table=True):
    """CPU 槽位表,slot 为身份(device 内唯一),如 CPU0。"""

    __table_args__ = (UniqueConstraint("device_id", "slot"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    slot: str
    model: str | None = None


def normalized_size_gb(size: int | None, size_unit: str | None) -> int | None:
    """容量归一化为 GB(理论标称值):TB 按 1024 换算,其余按 GB。"""
    if size is None:
        return None
    return size * 1024 if (size_unit or "").upper() == "TB" else size


class Disk(SQLModel, table=True):
    """硬盘表,serial_number 为身份(device 内唯一),type 为 SSD / HDD。

    size + size_unit 为标称容量原始值;size_gb 为归一化数值列,便于排序与统计。
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
    """电源模块表,serial_number 为身份(device 内唯一)。"""

    __table_args__ = (UniqueConstraint("device_id", "serial_number"),)

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    serial_number: str
    manufacturer: str | None = None
    model: str | None = None
    max_power_w: int | None = None


class PendingChange(SQLModel, table=True):
    """冲突待裁决,同一设备仅一条 pending,新推送合并进同一条。"""

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    source: str | None = None
    # 推送原始 JSON(含 timestamp / full_sync / source)
    payload: dict = Field(sa_column=Column(JSON))
    # 字段级差异清单 JSON,结构见 services/diff.py
    diff: dict = Field(sa_column=Column(JSON))
    # pending / applied / discarded
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None


class ChangeHistory(SQLModel, table=True):
    """变更流水,仅记录裁决生效的改动。

    device_id 不设外键:设备硬删后本表记录保留,历史独立于设备存活。
    diff 存裁决时的完整差异清单,供历史详情查看。
    """

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(index=True)
    summary: str
    source: str | None = None
    diff: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
