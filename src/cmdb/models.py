"""SQLModel 表模型:devices / nics / nic_ips / pending_changes / change_history。"""

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
    """变更流水,仅记录裁决生效的改动;设备硬删后本表记录保留。"""

    id: int | None = Field(default=None, primary_key=True)
    device_id: int = Field(foreign_key="device.id", index=True)
    summary: str
    source: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
