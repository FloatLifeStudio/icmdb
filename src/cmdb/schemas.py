"""Pydantic push body / response models, matching the collection JSON structure

Aligned with the iagent collector's actual collection semantics:
- a single failed field is set to null, identity fields (slot/uuid/serial_number other than the nic name) may be null,
  entries with a null identity are dropped automatically and never enter diff or storage
- list fields (nics.ips) may be null
- an empty agent.timestamp string is treated as not collected
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class MgmtInfo(BaseModel):
    """Management interface info"""

    mac: str | None = None
    ip: str | None = None
    prefix_length: int | None = None


class NicIPIn(BaseModel):
    """A single IP on a nic in the push body"""

    ip: str
    prefix_length: int | None = None


class NicIn(BaseModel):
    """A single nic in the push body, variable number of ips; the collector sets ips=null for nics without an IP"""

    name: str
    mac: str | None = None
    ips: list[NicIPIn] | None = None

    @field_validator("ips", mode="before")
    @classmethod
    def _none_ips(cls, v):
        return v or []


class AgentInfo(BaseModel):
    """Collector info: version, source identifier, collection time"""

    version: str | None = None
    source: str | None = None
    timestamp: datetime | None = None
    # Full sync flag: hardware entries missing from the inventory enter the diff candidates; the new format defaults to full sync
    full_sync: bool = True

    @field_validator("timestamp", mode="before")
    @classmethod
    def _empty_timestamp(cls, v):
        # The collector sends an empty string when no time was collected, treated as not collected
        if isinstance(v, str) and not v.strip():
            return None
        return v


class OsInfo(BaseModel):
    """OS info, hostname is the unique device matching key; virt is the virtualization type (bare_metal/kvm/...)"""

    hostname: str
    type: str | None = None
    version: str | None = None
    kernel: str | None = None
    virt: str | None = None


class GpuSlotIn(BaseModel):
    """A single GPU in the push body, uuid is the identity (may be null, dropped automatically)"""

    uuid: str | None = None
    name: str | None = None
    serial_number: str | None = None
    size: int | None = None
    size_unit: str | None = None
    driver_version: str | None = None
    pcie_id: str | None = None


class GpuInfo(BaseModel):
    """GPU info in the push body"""

    slots: list[GpuSlotIn] = []


class MemorySlotIn(BaseModel):
    """A single memory stick in the push body, slot is the identity (may be null, dropped automatically), e.g. DIMM_A1"""

    slot: str | None = None
    manufacturer: str | None = None
    part_number: str | None = None
    type: str | None = None
    size: int | None = None
    size_unit: str | None = None
    speed_mts: int | None = None
    serial_number: str | None = None


class MemoryInfo(BaseModel):
    """Memory info in the push body"""

    slots: list[MemorySlotIn] = []


class CpuSlotIn(BaseModel):
    """A single CPU in the push body, slot is the identity (may be null, dropped automatically), e.g. CPU0"""

    slot: str | None = None
    model: str | None = None


class DiskIn(BaseModel):
    """A single disk in the push body, serial_number is the identity (may be null, dropped automatically), type is SSD / HDD"""

    serial_number: str | None = None
    type: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    size: int | None = None
    size_unit: str | None = None


class PsuIn(BaseModel):
    """A single PSU module in the push body, serial_number is the identity (may be null, dropped automatically)"""

    serial_number: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    max_power_w: int | None = None


class HardwareInfo(BaseModel):
    """Hardware info, chassis_serial_number is the chassis serial number

    Entries with a null identity field (failed slot collection) are dropped automatically, without affecting reception of the whole payload
    """

    chassis_serial_number: str | None = None
    nics: list[NicIn] = []
    memory: MemoryInfo | None = None
    cpus: list[CpuSlotIn] | None = None
    disks: list[DiskIn] | None = None
    psus: list[PsuIn] | None = None
    gpu: GpuInfo | None = None

    @model_validator(mode="after")
    def _normalise_identity(self) -> "HardwareInfo":
        """Drop null-identity entries (failed collection) and dedup repeated identities (keep the first)

        Duplicate identities in one payload would otherwise break the unique constraints on ingest
        """
        if self.nics:
            self.nics = self._dedup(self.nics, key=lambda n: n.name)
        if self.memory:
            self.memory.slots = self._dedup(self.memory.slots, key=lambda s: s.slot)
        if self.cpus:
            self.cpus = self._dedup(self.cpus, key=lambda c: c.slot)
        if self.disks:
            self.disks = self._dedup(self.disks, key=lambda d: d.serial_number)
        if self.psus:
            self.psus = self._dedup(self.psus, key=lambda p: p.serial_number)
        if self.gpu:
            self.gpu.slots = self._dedup(self.gpu.slots, key=lambda g: g.uuid)
        return self

    @staticmethod
    def _dedup(entries: list, key) -> list:
        seen: set = set()
        out = []
        for entry in entries:
            k = key(entry)
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(entry)
        return out


class DevicePush(BaseModel):
    """Collection push body (new format): agent + os + mgmt + hardware

    When agent.timestamp is missing it falls back to the server receive time; agent.full_sync=true (default)
    means full sync, hardware entries missing from the inventory enter the diff candidates. null mgmt/hardware is treated as not collected
    """

    agent: AgentInfo = AgentInfo()
    os: OsInfo
    mgmt: MgmtInfo = MgmtInfo()
    hardware: HardwareInfo = HardwareInfo()

    @field_validator("mgmt", mode="before")
    @classmethod
    def _null_mgmt(cls, v):
        return v or MgmtInfo()

    @field_validator("hardware", mode="before")
    @classmethod
    def _null_hardware(cls, v):
        return v or HardwareInfo()


def normalise_legacy(raw: dict) -> dict:
    """Convert the legacy format (top-level hostname/serial_number/nics etc.) to the new format

    The new format is recognized by the "os" key; legacy collector pushes are converted automatically, no impact on usage
    """
    if "os" in raw:
        return raw
    memory = raw.get("memory")
    if memory:
        # Legacy memory slots use size_gb (nominal GB), convert to size + size_unit
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
    """IP in responses (with id)"""

    id: int


class MemorySlotOut(MemorySlotIn):
    """Memory slot in responses (with id and normalized capacity)"""

    id: int
    size_gb: int | None = None


class CpuSlotOut(CpuSlotIn):
    """CPU slot in responses (with id)"""

    id: int


class DiskOut(DiskIn):
    """Disk in responses (with id and normalized capacity)"""

    id: int
    size_gb: int | None = None


class GpuOut(GpuSlotIn):
    """GPU in responses (with id and normalized capacity)"""

    id: int
    size_gb: int | None = None


class PsuOut(PsuIn):
    """PSU module in responses (with id)"""

    id: int


class NicOut(BaseModel):
    """Nic in responses (with id and IP list)"""

    id: int
    name: str
    mac: str | None = None
    ips: list[NicIPOut] = []


class DeviceOut(BaseModel):
    """Device detail response"""

    id: int
    hostname: str
    serial_number: str | None = None
    os_type: str | None = None
    os_version: str | None = None
    kernel: str | None = None
    os_virt: str | None = None
    agent_version: str | None = None
    # CMDB metadata (editable in the UI, untouched by pushes)
    location: str | None = None
    owner: str | None = None
    purpose: str | None = None
    mgmt_mac: str | None = None
    mgmt_ip: str | None = None
    mgmt_prefix_length: int | None = None
    last_pushed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Computed dynamically: active / suspected_offline
    status: str
    tags: list[str] = []
    nics: list[NicOut] = []
    memory: list[MemorySlotOut] = []
    cpus: list[CpuSlotOut] = []
    disks: list[DiskOut] = []
    psus: list[PsuOut] = []
    gpus: list[GpuOut] = []


class DeviceCreatedOut(BaseModel):
    """Push response: result has three branches created / unchanged / diff_created"""

    result: str
    device_id: int
    # When diff_created, returns the pending change record id
    pending_change_id: int | None = None


class ResolutionIn(BaseModel):
    """Resolution request body: each diff entry picks "new" (adopt new data) or "old" (keep current state)

    For removed nics/memory slots, "new" means deleting the entry
    """

    field_choices: dict[str, str] = {}
    nic_choices: dict[str, str] = {}
    memory_choices: dict[str, str] = {}
    cpu_choices: dict[str, str] = {}
    disk_choices: dict[str, str] = {}
    psu_choices: dict[str, str] = {}
    gpu_choices: dict[str, str] = {}


class TagUpdate(BaseModel):
    """Tag update: fully replaced by the given tag list"""

    tags: list[str] = []


class MetadataIn(BaseModel):
    """Device metadata update (location/owner/purpose): None = no change, empty string = clear"""

    location: str | None = None
    owner: str | None = None
    purpose: str | None = None


class BatchDeleteIn(BaseModel):
    """List of device ids to batch delete"""

    ids: list[int]
