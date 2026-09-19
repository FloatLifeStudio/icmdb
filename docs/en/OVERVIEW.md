# CMDB Data and API Overview

> Chinese version: [../OVERVIEW.md](../OVERVIEW.md)

This document is a panoramic introduction to CMDB v2: the push JSON, every database table, every API endpoint, what each field does and how they map to each other, plus the design rationale and a soundness review. For a day-to-day operations quick reference see [API.md](API.md); for collection examples see [EXAMPLE.md](EXAMPLE.md).

---

## Table of Contents

- [1. Overall architecture and data flow](#1-overall-architecture-and-data-flow)
- [2. Push JSON (collector integration)](#2-push-json-collector-integration)
- [3. Database tables](#3-database-tables)
- [4. API endpoints](#4-api-endpoints)
- [5. Field mapping reference](#5-field-mapping-reference)
- [6. Design rationale summary](#6-design-rationale-summary)
- [7. Design soundness review](#7-design-soundness-review)

---

## 1. Overall Architecture and Data Flow

```
Collector (iagent / legacy collector / curl)
        │  POST /api/v1/devices (open, no login required)
        ▼
┌───────────────────────────────────────────────────┐
│ FastAPI (cmdb.main)                               │
│  ┌─────────┐  ┌─────────┐  ┌─────────────────┐    │
│  │schemas  │→ │services │→ │ models(SQLModel)│    │
│  │validate/│  │diff/    │  │ 14 tables       │    │
│  │normalise│  │ingest/  │  │                 │    │
│  │         │  │resolve  │  │                 │    │
│  └─────────┘  └─────────┘  └─────────────────┘    │
│  Middleware: session cookie + role (admin/viewer) gate    │
└───────────────────────────────────────────────────┘
        │
        ▼
Vue 3 frontend (build output served by FastAPI, single service on port 8080)
```

**Core data flow (the three outcomes of a single push)**:

```
Push → hostname matched against devices in the DB
  ├─ not found            → created       creates the device + all hardware directly
  ├─ found and diff empty → unchanged     only refreshes last_pushed_at
  └─ found with diffs     → diff_created  diffs go to pending_change, existing data untouched, awaiting manual resolution
```

**Key design principle**: the push API is the only data write entry point. Manual resolution (adopt new data), CSV import and UI editing are all auxiliary channels around this entry point; every change happens within a framework that is traceable and rollback-capable (resolve with old).

---

## 2. Push JSON (Collector Integration)

### 2.1 New format (four-section structure)

```json
{
  "agent": {
    "version": "1.2.0",
    "source": "iagent",
    "timestamp": "2026-09-19T08:30:00Z",
    "full_sync": true
  },
  "os": {
    "hostname": "web-01",
    "type": "Linux",
    "version": "Ubuntu 22.04",
    "kernel": "5.15.0-91-generic",
    "virt": "kvm"
  },
  "mgmt": {
    "mac": "aa:bb:cc:dd:ee:ff",
    "ip": "192.0.2.10",
    "prefix_length": 24
  },
  "hardware": {
    "chassis_serial_number": "SN-CHASSIS-001",
    "nics": [
      {"name": "eth0", "mac": "aa:bb:cc:00:00:01",
       "ips": [{"ip": "10.0.0.1", "prefix_length": 24}]},
      {"name": "eth1", "mac": null, "ips": null}
    ],
    "memory": {
      "slots": [
        {"slot": "DIMM_A1", "manufacturer": "Samsung", "part_number": "M323R4GA3PB0",
         "type": "DDR4", "size": 32, "size_unit": "GB", "speed_mts": 3200,
         "serial_number": "MEM-SN-001"}
      ]
    },
    "cpus": [
      {"slot": "CPU0", "model": "Intel(R) Xeon(R) Gold 6330"}
    ],
    "disks": [
      {"serial_number": "DISK-SN-001", "type": "SSD", "manufacturer": "Samsung",
       "model": "990EVO", "size": 8, "size_unit": "TB"}
    ],
    "psus": [
      {"serial_number": "PSU-SN-001", "manufacturer": "GreatWall",
       "model": "CRPS2700D2", "max_power_w": 2700}
    ],
    "gpu": {
      "slots": [
        {"uuid": "GPU-UUID-001", "name": "NVIDIA A100", "serial_number": "GPU-SN-001",
         "size": 80, "size_unit": "GB", "driver_version": "550.54",
         "pcie_id": "0000:3f:00.0"}
      ]
    }
  }
}
```

### 2.2 Field-by-field description

**agent — collector info**

| Field | Type | Purpose | Stored in |
|---|---|---|---|
| `version` | string, nullable | Collector version | `device.agent_version` |
| `source` | string, nullable | Source identifier (`iagent` / `csv_import` etc.), goes into pending-change records | `pending_change.source` |
| `timestamp` | datetime, nullable | Collection time; **an empty string is treated as not collected**; falls back to the server receive time when absent | `device.last_pushed_at` |
| `full_sync` | bool, default true | Full-sync flag: extra hardware entries in the DB go into the diff for deletion; false = incremental (only what is pushed is stored) | Not persisted, affects diff behavior |

**os — operating system**

| Field | Type | Purpose | Stored in |
|---|---|---|---|
| `hostname` | string, **required** | The device's unique matching key; a missing hostname rejects the whole payload with 422 | `device.hostname` |
| `type` | string, nullable | OS type (Linux / Windows...) | `device.os_type` |
| `version` | string, nullable | OS version (Ubuntu 22.04...) | `device.os_version` |
| `kernel` | string, nullable | Kernel version | `device.kernel` |
| `virt` | string, nullable | Virtualization type (bare_metal / kvm / ...) | `device.os_virt` |

**mgmt — management port** (the whole section may be null, treated as not collected)

| Field | Type | Purpose | Stored in |
|---|---|---|---|
| `mac` | string, nullable | Management-port MAC | `device.mgmt_mac` |
| `ip` | string, nullable | Management-port IP | `device.mgmt_ip` |
| `prefix_length` | int, nullable | Subnet prefix length | `device.mgmt_prefix_length` |

**hardware — hardware** (the whole section may be null)

| Field | Type | Purpose | Stored in |
|---|---|---|---|
| `chassis_serial_number` | string, nullable | Chassis serial number | `device.serial_number` |
| `nics[]` | list | NICs, `name` is the identity | `nic` + `nic_ip` tables |
| `nics[].name` | string, **required** | NIC name (eth0...), unique within a device | `nic.name` |
| `nics[].mac` | string, nullable | MAC address | `nic.mac` |
| `nics[].ips[]` | list, nullable | IP list, null for a NIC with no IPs | `nic_ip` table |
| `nics[].ips[].ip` | string, required | IP address | `nic_ip.ip` |
| `nics[].ips[].prefix_length` | int, nullable | Subnet prefix | `nic_ip.prefix_length` |
| `memory.slots[]` | list | Memory, `slot` is the identity | `memoryslot` table |
| `memory.slots[].slot` | string, nullable | Slot number (DIMM_A1), null entries are dropped automatically | `memoryslot.slot` |
| `...manufacturer` / `part_number` | string, nullable | Manufacturer / part number | Same table, same-named column |
| `...type` | string, nullable | Memory generation (DDR4...) | Same table, same-named column |
| `...size` / `size_unit` | int + string, nullable | Nominal capacity (32 GB / 64 GB) | Same table, same-named column + normalized `size_gb` column |
| `...speed_mts` | int, nullable | Frequency (MT/s) | `memoryslot.speed_mts` |
| `...serial_number` | string, nullable | DIMM SN (can be distinguished from a disk with the same SN; the scope is per table) | Same table, same-named column |
| `cpus[]` | list | CPUs, `slot` is the identity (CPU0) | `cpu` table |
| `cpus[].slot` | string, nullable | Slot number, null entries are dropped automatically | `cpu.slot` |
| `cpus[].model` | string, nullable | CPU model | `cpu.model` |
| `disks[]` | list | Disks, `serial_number` is the identity | `disk` table |
| `disks[].serial_number` | string, nullable | Disk SN (natural identity: a disk swap = old deleted, new added), null entries are dropped automatically | `disk.serial_number` |
| `...type` | string, nullable | SSD / HDD | `disk.type` |
| `...manufacturer` / `model` | string, nullable | Brand / model | Same table, same-named column |
| `...size` / `size_unit` | int + string, nullable | Nominal capacity | Same table, same-named column + `size_gb` |
| `psus[]` | list | PSU modules, `serial_number` is the identity | `psu` table |
| `psus[].serial_number` | string, nullable | PSU SN, null entries are dropped automatically | `psu.serial_number` |
| `...manufacturer` / `model` | string, nullable | Brand / model | Same table, same-named column |
| `...max_power_w` | int, nullable | Maximum power (watts) | `psu.max_power_w` |
| `gpu.slots[]` | list | GPUs, `uuid` is the identity (the nvidia-smi UUID, stable and globally unique) | `gpu` table |
| `gpu.slots[].uuid` | string, nullable | UUID, null entries are dropped automatically | `gpu.uuid` |
| `...name` / `serial_number` | string, nullable | Model / SN | Same table, same-named column |
| `...size` / `size_unit` | int + string, nullable | VRAM | Same table, same-named column + `size_gb` |
| `...driver_version` | string, nullable | Driver version | `gpu.driver_version` |
| `...pcie_id` | string, nullable | PCIe address | `gpu.pcie_id` |

### 2.3 Fault tolerance semantics (aligned with the iagent collector)

| Case | Handling | Rationale |
|---|---|---|
| Identity field (slot / uuid / serial_number) is null | **The whole entry is dropped automatically**, never enters diff or storage | A slot that failed to collect has no identity; storing it would be unusable for comparison; acceptance of the whole payload is unaffected |
| Scalar field is null | Treated as "not collected", existing data in the DB is **not cleared** | A partial collection failure should not erase the previously collected values |
| `mgmt` / `hardware` / `nics[].ips` is null | Treated as not collected / no IPs | The collector sends null for fields with no data |
| `agent.timestamp` is an empty string | Treated as not collected, falls back to the server receive time | The collector sends an empty string when it could not get the time |
| `hostname` missing | The whole payload gets 422 | No matching key means it cannot be stored |

### 2.4 Automatic legacy format compatibility

Legacy collector pushes with a flat structure containing only top-level `hostname` / `serial_number` / `nics` etc. are normalized automatically by the server (`normalise_legacy`) into the new format; the legacy format's memory `size_gb` is converted to `size + size_unit`. The legacy format defaults to `full_sync=false` (incremental semantics).

---

## 3. Database Tables

SQLite (WAL mode, foreign key constraints enabled), tables created with SQLModel, **14 tables** in total. All child tables reference `device` through a `device_id` foreign key and are indexed.

### 3.1 `device` — host main table

| Field | Type | Description |
|---|---|---|
| `id` | int PK | Auto-incrementing primary key |
| `hostname` | string, unique+index | The device's unique matching key |
| `serial_number` | string | Chassis serial number (from `hardware.chassis_serial_number`) |
| `mgmt_mac` / `mgmt_ip` / `mgmt_prefix_length` | string × 2 / int | Management-port triple |
| `os_type` / `os_version` / `os_virt` / `kernel` | string | The four OS essentials (type/version/virt from `os.*`) |
| `agent_version` | string | Collector version |
| `location` / `owner` / `purpose` | string | **CMDB metadata**: server/rack location, owner, purpose. Editable in the UI, CSV import/export, **pushes never change it** |
| `last_pushed_at` | datetime | Last push time (naive UTC), the basis for the suspected-offline determination |
| `created_at` / `updated_at` | datetime | Creation / last update time |

### 3.2 `nic` / `nic_ip` — NICs and IPs

`nic`: id, `device_id` (FK+index), `name` (identity, unique constraint device_id+name), `mac`.
`nic_ip`: id, `nic_id` (FK+index), `ip` (unique constraint nic_id+ip), `prefix_length`.

IPs get their own table: one NIC can have multiple IPs (IPv4/IPv6, multiple addresses), and a one-to-many relationship must be split into a table.

### 3.3 `memoryslot` — memory slots

id, `device_id` (FK+index), `slot` (identity, unique constraint device_id+slot), `manufacturer`, `part_number`, `type` (memory generation), `size` + `size_unit` (nominal raw value), `size_gb` (normalized column, TB×1024, for easy sorting and statistics), `speed_mts`, `serial_number`.

### 3.4 `cpu` — CPU slots

id, `device_id` (FK+index), `slot` (identity, unique constraint device_id+slot), `model`. CPU collection only gathers the model, deliberately kept minimal.

### 3.5 `disk` — disks

id, `device_id` (FK+index), `serial_number` (identity, unique constraint device_id+serial_number), `type` (SSD/HDD), `manufacturer`, `model`, `size` + `size_unit` + `size_gb` (normalized). The SN is the disk's natural identity: same-SN data changes = changed, a new SN = added, a disk swap = old disk deleted + new disk added.

### 3.6 `psu` — PSU modules

id, `device_id` (FK+index), `serial_number` (identity, unique constraint device_id+serial_number), `manufacturer`, `model`, `max_power_w`.

### 3.7 `gpu` — GPU

id, `device_id` (FK+index), `uuid` (identity, unique constraint device_id+uuid), `name`, `serial_number`, `size` + `size_unit` + `size_gb`, `driver_version`, `pcie_id`.

### 3.8 `device_tag` — device tags

id, `device_id` (FK+index), `name` (indexed), unique constraint device_id+name. One row per device-tag pair. **CMDB metadata** (editable in the UI, not part of the collected data), replacing the legacy comma-separated TEXT column — once split into a table, exact-match filtering and a unique constraint become possible.

### 3.9 `pending_change` — pending conflict resolution

| Field | Type | Description |
|---|---|---|
| `id` | int PK | Auto-incrementing primary key |
| `device_id` | int, FK+index | Associated device |
| `source` | string | Push source (agent.source) |
| `payload` | JSON | Raw push JSON (the full context can be reviewed at resolution time) |
| `diff` | JSON | Field-level diff list, structure in §5.2 |
| `status` | string, indexed | pending / applied / discarded |
| `created_at` / `resolved_at` | datetime | Creation / resolution time |

**Only one pending record per device**: a new push recomputes the diff and replaces it as a whole, never accumulating — the resolver always faces the latest view.

### 3.10 `changehistory` — change log

id, `device_id` (indexed, **no foreign key**), `summary` (e.g. "disk DISK-SN-001 added"), `source`, `diff` (JSON, the full diff at resolution time), `created_at` (indexed).

The absence of a foreign key on `device_id` is deliberate: history records survive a device hard delete, and their traceability value is independent of the device's existence.

### 3.11 `user` — users

id, `username` (unique+index), `password_hash` (PBKDF2-SHA256, stored as salt:digest), `role` (admin / viewer, indexed), `created_at`.

### 3.12 `systemsetting` — system settings

id, `key` (unique+index), `value`, `updated_at`. Key-value storage; the only key currently in use is `offline_threshold_hours` (the suspected-offline threshold, in hours), where the `CMDB_OFFLINE_THRESHOLD_DAYS` environment variable is only the initial default.

### 3.13 `auditlog` — operation audit

id, `username` (indexed), `action` (indexed, e.g. "delete device"), `detail` (e.g. the hostname), `created_at` (indexed). Management operations are written in the same transaction as the operation; admin only can view.

### 3.14 Lightweight migration mechanism

`migrate()` in `database.py` performs idempotent column additions (SQLite ALTER TABLE) on existing tables + backfills legacy data (splitting the tags TEXT column, normalizing disk/memory capacity, adding indexes to existing tables); new databases are created directly by `create_all`. Alembic was not introduced — schema changes are infrequent and it is unnecessary in the single-file SQLite scenario.

---

## 4. API Endpoints

All endpoints are mounted under `/api/v1`. Authentication is handled uniformly by middleware: **everything requires login except login/session checks**; write operations (resolve / delete / tags / metadata / user management / settings) are admin only. Roles are queried from the DB in real time, so changes take effect immediately. When the system setting `api_key_enabled` is on, `POST /devices` requires a valid API key (the `X-API-Key` header, see API.md §12); key requests may also GET read-only, while all other writes return 403.

### 4.1 Collector push

| Endpoint | Auth | Description |
|---|---|---|
| `POST /devices` | **Open** | The only data write entry point. Request body in §2; legacy formats converted automatically. Returns `{"result": "created\|unchanged\|diff_created", "device_id": N, "pending_change_id": N\|null}` |

**Why open**: collectors are widely distributed and have no user system, so requiring login would hinder onboarding; a push only creates devices and pending records, and the real data change (resolution) is gate-kept by a human, keeping the blast radius of a forged push under control.

### 4.2 Devices

| Endpoint | Auth | Description |
|---|---|---|
| `GET /devices` | Login | Paginated (`page`/`page_size`, default 1/20). `search` fuzzy-matches hostname / serial_number / mgmt_ip + **NIC business IP reverse lookup**; `status=active\|suspected_offline` filtered at the SQL layer by the threshold; `tag` exact match; `sort_by` whitelist (hostname/serial_number/mgmt_ip/last_pushed_at) + `sort_order`. Returns `{total, page, page_size, items: [DeviceOut]}` |
| `GET /devices/{id}` | Login | Device detail, full DeviceOut (including all child-table data and the dynamic status) |
| `DELETE /devices/{id}` | admin | Hard-deletes the device and all child-table data; change_history is preserved. 204 |
| `POST /devices/batch-delete` | admin | `{"ids": [1,2,3]}`, same behavior as a single delete; returns `{"deleted": [id]}` |
| `PUT /devices/{id}/tags` | admin | `{"tags": ["production","web"]}`, full replacement |
| `PUT /devices/{id}/metadata` | admin | Updates location/owner/purpose; all fields optional, None = no change, empty string = clear |
| `GET /devices/export/csv` | Login | Exports all devices as CSV (UTF-8 BOM, Excel-compatible); columns include tags and metadata |
| `POST /devices/import/csv` | admin | multipart upload, row format matches the export (can be imported back); each row goes through the push cleansing logic, `source=csv_import`, `last_pushed_at` untouched |

**DeviceOut structure** (shared by list and detail): id, hostname, serial_number, os_type/version/virt, kernel, agent_version, location/owner/purpose, mgmt_mac/ip/prefix_length, last_pushed_at, created_at/updated_at, **status (computed dynamically: active / suspected_offline, not persisted)**, tags, nics (with ips), memory, cpus, disks, psus, gpus.

**Why status is not persisted**: suspected-offline is a relative judgment of "how long since the last push"; the threshold can change, and persisting it would require a full refresh; computing it dynamically at query time is always consistent with the current settings.

### 4.3 Pending conflict resolution

| Endpoint | Auth | Description |
|---|---|---|
| `GET /pending-changes` | Login | `status=pending` (default) / `all`; sorted by creation time |
| `GET /pending-changes/{id}` | Login | Diff detail: payload + field-level diff list |
| `POST /pending-changes/{id}/resolve` | admin | Resolve, request body below; repeated resolve 409 |

Resolve request body — each diff entry chooses `new` (adopt the new data) / `old` (keep the current state); for a removed entry, choosing `new` means deletion:

```json
{
  "field_choices": {"mgmt.ip": "new"},
  "nic_choices": {"eth3": "new", "eth1": "old"},
  "memory_choices": {}, "cpu_choices": {},
  "disk_choices": {}, "psu_choices": {}, "gpu_choices": {}
}
```

After a resolution takes effect it is written to change_history, and the pending record is set to applied (discarded if everything chose old with no actual change). The apply logic is idempotent: an added entry that already exists is skipped, a removed entry that does not exist is skipped.

**Why manual resolution**: collected data can be wrong (collector bugs, transient states like memory hot-swaps), and automatic overwriting would lose the correct current state; a field-level either-or choice lets the admin see every diff clearly before deciding, with a full audit trail throughout.

### 4.4 Change history (read-only)

| Endpoint | Auth | Description |
|---|---|---|
| `GET /change-history` | Login | `device_id` optional filter; newest first; still queryable after a device hard delete |
| `GET /change-history/{id}` | Login | Contains the full diff at resolution time |

### 4.5 Dashboard (read-only)

| Endpoint | Auth | Description |
|---|---|---|
| `GET /dashboard` | Login | `total_devices`, `active` / `suspected_offline` (computed dynamically under the current threshold), `pending_changes`, `recent_changes` (the 10 most recent changes) |

### 4.6 User login / user management

| Endpoint | Auth | Description |
|---|---|---|
| `POST /auth/login` | Open | Validates the users table, issues an HttpOnly session cookie (HMAC signed, default 7 days) |
| `POST /auth/logout` | Login | Clears the cookie |
| `POST /auth/change-password` | Login | Changes one's own password, requires verifying the original password, available to all roles |
| `GET /auth/me` | Open* | Returns the current user and role; not logged in 401. The frontend uses it to determine session state and admin rights |
| `GET /users` | admin | User list |
| `POST /users` | admin | Creates a user (role=admin/viewer, default viewer); duplicate 409 |
| `PUT /users/{id}` | admin | Resets password / changes role, whichever is passed is changed; demoting the last admin 409 |
| `DELETE /users/{id}` | admin | Cannot delete yourself or the last admin 409 |

### 4.7 System settings / operation audit

| Endpoint | Auth | Description |
|---|---|---|
| `GET /settings/system` | Login | `{"offline_threshold_hours": 24}` |
| `PUT /settings/system` | admin | Changes the threshold (1~8760 hours); device status is computed immediately under the new threshold |
| `GET /audit-logs` | admin | Audit log, `username` filter, `limit` (default 100, max 1000), newest first |

---

## 5. Field Mapping Reference

### 5.1 Push JSON → database → API response

| Push field | Database | Response field (DeviceOut) |
|---|---|---|
| `os.hostname` | `device.hostname` | `hostname` |
| `hardware.chassis_serial_number` | `device.serial_number` | `serial_number` |
| `os.type` / `os.version` / `os.kernel` / `os.virt` | `device.os_type` / `os_version` / `kernel` / `os_virt` | Same name |
| `mgmt.mac` / `mgmt.ip` / `mgmt.prefix_length` | `device.mgmt_mac` / `mgmt_ip` / `mgmt_prefix_length` | Same name |
| `agent.version` | `device.agent_version` | `agent_version` |
| `agent.timestamp` (or the receive time) | `device.last_pushed_at` | `last_pushed_at` + dynamic `status` |
| — (non-collected data) | `device.location` / `owner` / `purpose` | Same name |
| — (non-collected data) | `devicetag` table | `tags` |
| `hardware.nics[].name` / `.mac` | `nic.name` / `nic.mac` | `nics[].name` / `.mac` |
| `hardware.nics[].ips[]` | `nic_ip` table | `nics[].ips[]` |
| `hardware.memory.slots[]` | `memoryslot` table | `memory[]` (the response field name has no slots) |
| `hardware.cpus[]` | `cpu` table | `cpus[]` |
| `hardware.disks[]` | `disk` table | `disks[]` |
| `hardware.psus[]` | `psu` table | `psus[]` |
| `hardware.gpu.slots[]` | `gpu` table | `gpus[]` (the response field name has no slots) |

Note two naming differences: in the push body, memory is `memory.slots[]` and GPU is `gpu.slots[]` (aligned with the collector's JSON structure); in the response they are the flat `memory[]` / `gpus[]` (each entry carries the database `id`).

### 5.2 Diff list structure (pending_change.diff / changehistory.diff)

```json
{
  "fields":  [{"field": "mgmt.ip", "old": "10.0.0.1", "new": "10.0.0.2"}],
  "nics":    [{"name": "eth3", "kind": "added", "changes": [],
                "old": null, "new": {"name": "eth3", "mac": "...", "ips": [...]}}],
  "memory":  [{"slot": "DIMM_A1", "kind": "changed",
                "changes": [{"field": "size", "old": 32, "new": 64}],
                "old": {...}, "new": {...}}],
  "cpus":    [], "disks": [], "psus": [], "gpus": [],
  "has_changes": true
}
```

- Hardware entries have three `kind` states: added / removed / changed; a changed entry's `changes` is a per-field diff
- `removed` is produced only when `agent.full_sync=true` (extra entries in the DB as delete candidates)
- `old` / `new` store the complete entries, so the resolution detail can be reviewed in full

### 5.3 Identity key reference

| Data | Identity key | Rationale |
|---|---|---|
| Device | `hostname` | Unique at the OS level; a hostname rename = a new device + a leftover old device (delete the old one manually) |
| NIC | `name` | Unique within a device (eth0...), a rename is treated as a card swap |
| Memory / CPU | `slot` | Slots are physically fixed (DIMM_A1 / CPU0), so the same slot can be compared across collections |
| Disk / PSU | `serial_number` | No stable slot; the SN is the natural identity; a disk swap = old deleted, new added |
| GPU | `uuid` | nvidia-smi UUID, stable and unique across machines |

---

## 6. Design Rationale Summary

| Decision | Why |
|---|---|
| Push is the only write entry point | A single source of data, every change traceable; manual operations (resolve / import / UI editing) are auxiliary channels |
| Diff + manual resolution instead of automatic overwrite | Collected data can be wrong; a field-level either-or choice + a full audit trail, with errors rollback-capable (choose old) |
| One pending record per device, replaced wholesale by new pushes | Avoids a pile-up of pending records for the same device; the resolver always faces the latest view, never stale diffs |
| Suspected-offline computed dynamically, not persisted | The threshold can be changed online, and dynamic computation is always consistent; data is not deleted automatically, and a resumed push restores active |
| `full_sync` explicitly flags full/incremental | Collectors may push only part of the hardware (collection failures / partial integration); the collector declares the semantics, the server does not guess |
| null scalars do not clear DB data | A partial collection failure should not erase the last valid values |
| Entries with a null identity are dropped automatically | Entries without an identity cannot be compared; storing them is noise |
| CMDB metadata separated from collected data | location/owner/purpose/tags are human input, never overwritten by pushes; the two sources never step on each other |
| Normalized capacity column `size_gb` | The raw value (size + unit) is preserved for display; the normalized column makes sorting and statistics easy |
| change_history has no foreign key | History survives a device hard delete; traceability is independent of the device's existence |
| SQLite + WAL, single file | The on-prem ops scenario has a small device count (hundreds); zero maintenance and backup is just copying the file; a backup script is already in cron |
| Lightweight migration (ALTER TABLE) instead of Alembic | Schema changes are infrequent; Alembic is over-engineering in the single-file SQLite scenario |
| Sessions use an HMAC-signed cookie instead of a server-side session | Stateless, no extra table; changing the key logs everyone out; roles are queried from the DB in real time, so changes take effect immediately |

---

## 7. Design Soundness Review

### 7.1 What is sound

1. **Push tolerance semantics aligned with the real collector**: null identity dropped, null scalars do not clear data, timestamp fallback — these were not decided arbitrarily; they were confirmed one by one against iagent's actual output, with zero surprises during integration.
2. **Three-branch push result (created/unchanged/diff_created)**: collectors can perceive the push outcome, with a clear boundary of responsibility.
3. **Idempotent resolution + a full audit trail**: added/removed idempotent skips, the pending→applied/discarded state machine, the diff stored as a snapshot at resolution time — both replays and mis-operations are safe.
4. **Identity keys fit the physical reality of hardware**: slots for memory/CPU, SN for disks/PSUs, UUID for GPUs; each one's "same-identity change = changed" semantics holds up.
5. **Performance awareness is in place**: one IN query per child-table type for the list (avoiding N+1), count via aggregation, status filtered at the SQL layer, a sort-field whitelist against injection, and a unique index on hostname.
6. **The auth model is simple and sufficient**: two role levels + real-time DB queries, with the open push backed up by the human-gate-kept resolution.

### 7.2 Potential issues and improvement directions (sorted by impact)

1. **Forged pushes are unauthenticated (medium, security)**: POST /devices is open by default, meaning anyone on the intranet can flood the CMDB with fake devices and forged diffs. Resolution is gate-kept by a human, but fake devices pollute the list and statistics. **Addressed**: v2.3 introduces API keys (`X-API-Key` + a system setting toggle); once enabled, pushes require a valid key, keys = push + read-only, keeping the blast radius of a leak contained; default off guarantees zero breakage.
2. **SQLite single writer, push concurrency limited (low, imperceptible at the current scale)**: WAL mitigates read/write mutual exclusion, but writes are still serial. A few hundred devices pushing every few minutes is plenty; at a thousand-plus devices pushing frequently, PostgreSQL would be needed (architecturally the SQLModel migration cost is manageable, but JSON column queries and the migration scripts would all need rewriting).
3. **Hostname renames produce orphan devices (low, a fallback already exists)**: hostname is the matching key, so a rename = a new device + a leftover old device (suspected-offline will expose it), and the old one must be deleted manually. Automatic merging risks mis-identification (two devices taking the same hostname one after another); the current "expose + delete manually" is a pragmatic choice; the improvement direction is a one-click "merge into the new device" in the UI.
4. **No pagination for pending changes (low)**: `GET /pending-changes` returns everything; the device count is small + only one pending record per device, so the list will not explode, but in extreme cases (many devices changing at once) pagination could be added.
5. **CSV import races with pushes (very low)**: import processes rows one by one, not atomically (each row is an independent ingest), and can interleave with concurrent pushes; in a single-admin scenario it is almost never encountered.
6. **The audit log is immutable but has no export (low)**: admin only can view it, and the limit is 1000 max; for compliance retention, an export or writing to an external log could be added.
7. **The dashboard loads all devices (very low)**: statistics compute status per device in the Python layer; imperceptible with hundreds of devices, but it should be aggregated at the SQL layer once the volume grows.

### 7.3 Conclusion

The current design is **sound and self-consistent** for its target scenario of "on-prem ops, hundreds of devices, a single or a few admins": every trade-off (dynamic status, one pending record, lightweight migration, SQLite) matches the scenario, with no obvious over-engineering; the alignment of the tolerance semantics with the collector is the key to this system's smooth integration. The one improvement most worth investing in — the **collection token** — has landed in v2.3 as API keys (a low-cost way to block forged pushes); the remaining issues can wait until the volume grows.
