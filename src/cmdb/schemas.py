"""Pydantic 推送体/响应模型,对应采集 JSON 结构。"""

from datetime import datetime

from pydantic import BaseModel, Field


class MgmtInfo(BaseModel):
    """管理口信息。"""

    mac: str | None = None
    ip: str | None = None
    prefix_length: int | None = None


class NicIPIn(BaseModel):
    """推送体中网卡上的单个 IP。"""

    ip: str
    prefix_length: int | None = None


class NicIn(BaseModel):
    """推送体中的单块网卡,ips 数量不定。"""

    name: str
    mac: str | None = None
    ips: list[NicIPIn] = []


class DevicePush(BaseModel):
    """采集推送体:POST /api/v1/devices 的 body。

    timestamp 缺省时由服务器接收时间兜底;full_sync=true 表示全量同步,
    库中多出的网卡进 diff 候删。
    """

    hostname: str
    serial_number: str | None = None
    mgmt: MgmtInfo = MgmtInfo()
    nics: list[NicIn] = []
    timestamp: datetime | None = None
    full_sync: bool = False
    source: str | None = None


class NicIPOut(NicIPIn):
    """响应中的 IP(含 id)。"""

    id: int


class NicOut(BaseModel):
    """响应中的网卡(含 id 与 IP 列表)。"""

    id: int
    name: str
    mac: str | None = None
    ips: list[NicIPOut] = []


class DeviceOut(BaseModel):
    """设备详情响应。"""

    id: int
    hostname: str
    serial_number: str | None = None
    mgmt_mac: str | None = None
    mgmt_ip: str | None = None
    mgmt_prefix_length: int | None = None
    last_pushed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # 动态计算:active / suspected_offline
    status: str
    tags: list[str] = []
    nics: list[NicOut] = []


class DeviceCreatedOut(BaseModel):
    """推送响应:result 三分支 created / unchanged / diff_created。"""

    result: str
    device_id: int
    # diff_created 时返回待裁决记录 id
    pending_change_id: int | None = None


class ResolutionIn(BaseModel):
    """裁决请求体:每条 diff 条目选 "new"(采用新数据)或 "old"(保留现状)。

    对 removed 网卡,"new" 即删除该网卡。
    """

    field_choices: dict[str, str] = {}
    nic_choices: dict[str, str] = {}


class TagUpdate(BaseModel):
    """标签更新:全量替换为给定标签列表。"""

    tags: list[str] = []


class BatchDeleteIn(BaseModel):
    """批量删除的设备 id 列表。"""

    ids: list[int]
