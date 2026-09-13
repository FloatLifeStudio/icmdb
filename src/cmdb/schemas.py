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


class AgentInfo(BaseModel):
    """采集器信息:版本、来源标识、采集时间。"""

    version: str | None = None
    source: str | None = None
    timestamp: datetime | None = None
    # 全量同步标记:库中多出的硬件条目进 diff 候删;新格式默认全量
    full_sync: bool = True


class OsInfo(BaseModel):
    """操作系统信息,hostname 为设备唯一匹配键。"""

    hostname: str
    type: str | None = None
    version: str | None = None
    kernel: str | None = None


class GpuSlotIn(BaseModel):
    """推送体中的单块 GPU,uuid 为身份。"""

    uuid: str
    name: str | None = None
    serial_number: str | None = None
    size: int | None = None
    size_unit: str | None = None
    driver_version: str | None = None
    pcie_id: str | None = None


class GpuInfo(BaseModel):
    """推送体中的 GPU 信息。"""

    slots: list[GpuSlotIn] = []


class MemorySlotIn(BaseModel):
    """推送体中的单条内存,slot 为身份,如 DIMM_A1。"""

    slot: str
    manufacturer: str | None = None
    part_number: str | None = None
    type: str | None = None
    size: int | None = None
    size_unit: str | None = None
    speed_mts: int | None = None
    serial_number: str | None = None


class MemoryInfo(BaseModel):
    """推送体中的内存信息。"""

    slots: list[MemorySlotIn] = []


class CpuSlotIn(BaseModel):
    """推送体中的单颗 CPU,slot 为身份,如 CPU0。"""

    slot: str
    model: str | None = None


class DiskIn(BaseModel):
    """推送体中的单块硬盘,serial_number 为身份,type 为 SSD / HDD。"""

    serial_number: str
    type: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    size: int | None = None
    size_unit: str | None = None


class PsuIn(BaseModel):
    """推送体中的单个电源模块,serial_number 为身份。"""

    serial_number: str
    manufacturer: str | None = None
    model: str | None = None
    max_power_w: int | None = None


class HardwareInfo(BaseModel):
    """硬件信息,chassis_serial_number 为整机序列号。"""

    chassis_serial_number: str | None = None
    nics: list[NicIn] = []
    memory: MemoryInfo | None = None
    cpus: list[CpuSlotIn] | None = None
    disks: list[DiskIn] | None = None
    psus: list[PsuIn] | None = None
    gpu: GpuInfo | None = None


class DevicePush(BaseModel):
    """采集推送体(新格式):agent + os + mgmt + hardware。

    agent.timestamp 缺省时由服务器接收时间兜底;agent.full_sync=true(默认)
    表示全量同步,库中多出的硬件条目进 diff 候删。
    """

    agent: AgentInfo = AgentInfo()
    os: OsInfo
    mgmt: MgmtInfo = MgmtInfo()
    hardware: HardwareInfo = HardwareInfo()


def normalise_legacy(raw: dict) -> dict:
    """旧格式(顶层 hostname/serial_number/nics 等)转换为新格式。

    新格式以 "os" 键为标志;旧采集器推送自动转换,不影响使用。
    """
    if "os" in raw:
        return raw
    memory = raw.get("memory")
    if memory:
        # 旧格式内存槽位是 size_gb(GB 标称),转为 size + size_unit
        for slot in memory.get("slots", []):
            if "size_gb" in slot and "size" not in slot:
                slot["size"] = slot.pop("size_gb")
                slot["size_unit"] = "GB"
    return {
        "agent": {
            "source": raw.get("source"),
            "timestamp": raw.get("timestamp"),
            "full_sync": raw.get("full_sync", False),
        },
        "os": {"hostname": raw.get("hostname")},
        "mgmt": raw.get("mgmt") or {},
        "hardware": {
            "chassis_serial_number": raw.get("serial_number"),
            "nics": raw.get("nics") or [],
            "memory": memory,
            "cpus": raw.get("cpus") or [],
            "disks": raw.get("disks") or [],
            "psus": raw.get("psus") or [],
        },
    }


class NicIPOut(NicIPIn):
    """响应中的 IP(含 id)。"""

    id: int


class MemorySlotOut(MemorySlotIn):
    """响应中的内存槽位(含 id 与归一化容量)。"""

    id: int
    size_gb: int | None = None


class CpuSlotOut(CpuSlotIn):
    """响应中的 CPU 槽位(含 id)。"""

    id: int


class DiskOut(DiskIn):
    """响应中的硬盘(含 id 与归一化容量)。"""

    id: int
    size_gb: int | None = None


class GpuOut(GpuSlotIn):
    """响应中的 GPU(含 id 与归一化容量)。"""

    id: int
    size_gb: int | None = None


class PsuOut(PsuIn):
    """响应中的电源模块(含 id)。"""

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
    os_type: str | None = None
    os_version: str | None = None
    kernel: str | None = None
    agent_version: str | None = None
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
    memory: list[MemorySlotOut] = []
    cpus: list[CpuSlotOut] = []
    disks: list[DiskOut] = []
    psus: list[PsuOut] = []
    gpus: list[GpuOut] = []


class DeviceCreatedOut(BaseModel):
    """推送响应:result 三分支 created / unchanged / diff_created。"""

    result: str
    device_id: int
    # diff_created 时返回待裁决记录 id
    pending_change_id: int | None = None


class ResolutionIn(BaseModel):
    """裁决请求体:每条 diff 条目选 "new"(采用新数据)或 "old"(保留现状)。

    对 removed 网卡/内存槽位,"new" 即删除该条目。
    """

    field_choices: dict[str, str] = {}
    nic_choices: dict[str, str] = {}
    memory_choices: dict[str, str] = {}
    cpu_choices: dict[str, str] = {}
    disk_choices: dict[str, str] = {}
    psu_choices: dict[str, str] = {}
    gpu_choices: dict[str, str] = {}


class TagUpdate(BaseModel):
    """标签更新:全量替换为给定标签列表。"""

    tags: list[str] = []


class BatchDeleteIn(BaseModel):
    """批量删除的设备 id 列表。"""

    ids: list[int]
