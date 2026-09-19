# CMDB API Documentation

> Chinese version: [../API.md](../API.md)

> Base URL: `http://<host>:8080/api/v1`
> Response format: REST style, HTTP status code + JSON body
> Collector push (POST /devices) is the only data write entry point, **and does not require login** (collectors need no changes)
> All other APIs require login (session cookie); see [User login](#9-user-login) for the login endpoint
> Permissions: admin can operate (resolve / delete / tags / CSV import / user management), viewer is read-only, write operations return 403
> Timestamps: timestamps in responses are uniformly naive UTC (no timezone suffix); clients should parse as UTC and then
> convert to the viewer's local timezone for display, e.g. in JS: `new Date(ts + 'Z')`
> See [EXAMPLE.md](./EXAMPLE.md) for a full push example

## Table of Contents

- [Collector push](#1-collector-push) — the only endpoint a collector needs to integrate with
- [Device list / detail / delete](#2-devices)
- [Pending conflicts](#3-pending-conflicts)
- [Change history](#4-change-history)
- [Dashboard](#5-dashboard)
- [Device extension endpoints](#6-device-extension-endpoints)
- [Error codes](#7-error-codes)
- [System settings](#8-system-settings)
- [User login](#9-user-login)
- [User management](#10-user-management)
- [Operation audit](#11-operation-audit)
- [API keys](#12-api-keys)

---

## 1. Collector Push

### `POST /api/v1/devices`

Collectors push device data. Matching is by hostname, with three outcomes:

| result | Meaning | Follow-up behavior |
|---|---|---|
| `created` | No such hostname in the DB | Create device + NICs + IPs |
| `unchanged` | Present in the DB with no field-level diffs | Only refresh last_pushed_at |
| `diff_created` | Present in the DB with diffs | Diffs go to pending resolution, **existing data untouched** |

**Request body** (since v2.2: the four-section `agent` / `os` / `mgmt` / `hardware` structure):

```json
{
  "agent": {
    "version": "1.2.0",
    "source": "collector",
    "timestamp": "2026-09-13T10:00:00+08:00",
    "full_sync": true
  },
  "os": {
    "hostname": "demo-node-01",
    "type": "Linux",
    "version": "Ubuntu 22.04",
    "kernel": "5.15.0-91-generic",
    "virt": "bare_metal"
  },
  "mgmt": {
    "mac": "02:00:00:00:00:01",
    "ip": "192.0.2.11",
    "prefix_length": 24
  },
  "hardware": {
    "chassis_serial_number": "DEMO-SN-0001",
    "nics": [
      {
        "name": "eth0",
        "mac": "02:00:00:00:00:02",
        "ips": [{"ip": "198.51.100.11", "prefix_length": 24}]
      },
      {
        "name": "eth1",
        "mac": "02:00:00:00:00:03",
        "ips": [{"ip": "198.51.100.13", "prefix_length": 24}]
      }
    ],
    "memory": {
      "slots": [
        {
          "slot": "DIMM_A1",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 64,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-01"
        }
      ]
    },
    "cpus": [
      {"slot": "CPU0", "model": "Intel(R) Xeon(R) Gold 6448Y"},
      {"slot": "CPU1", "model": "Intel(R) Xeon(R) Gold 6448Y"}
    ],
    "disks": [
      {"serial_number": "DEMO-SN-0010", "type": "SSD", "manufacturer": "Samsung",
       "model": "990EVO", "size": 8, "size_unit": "TB"},
      {"serial_number": "DEMO-SN-0011", "type": "HDD", "manufacturer": "HGST",
       "model": "HUH728080ALE604", "size": 8, "size_unit": "TB"}
    ],
    "psus": [
      {"serial_number": "DEMO-SN-0005", "manufacturer": "GreatWall",
       "model": "CRPS2700D2", "max_power_w": 2700}
    ],
    "gpu": {
      "slots": [
        {
          "uuid": "GPU-00000000-0000-0000-0000-9a1b2c3d4e5f",
          "name": "NVIDIA GeForce RTX 4090",
          "serial_number": "DEMO-GPU-0001",
          "size": 24,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:3b:00.0"
        }
      ]
    }
  }
}
```

**Field descriptions**:

| Field | Required | Description |
|---|---|---|
| `agent` | ❌ | Collector info, all fields default-absent |
| `agent.version` | ❌ | Collector version, written to the device detail |
| `agent.source` | ❌ | Source identifier, written to pending-change records and change history |
| `agent.timestamp` | ❌ | Collection time in ISO 8601 (with timezone, normalized to UTC); if absent, the server receive time is used |
| `agent.full_sync` | ❌ | Defaults to **true**. **true = full sync**: extra hardware entries in the DB go into the diff for deletion; false = incremental: extras in the DB are left untouched |
| `os.hostname` | ✅ | The device's unique matching key; a hostname rename = a new device |
| `os.type` / `os.version` / `os.kernel` / `os.virt` | ❌ | OS type / version / kernel / virtualization type (bare_metal/kvm/vmware/qemu/xen...); values not collected (None) do not clear existing values in the DB |
| `mgmt` | ❌ | Management-port info: mac / ip / prefix_length |
| `hardware.chassis_serial_number` | ❌ | Chassis serial number; not collected does not clear existing values in the DB |
| `hardware.nics` | ❌ | NIC array, however many are pushed is how many are stored; `name` is the NIC identity |
| `hardware.memory` | ❌ | Memory info: `slots` array, `slot` is the identity; fields include manufacturer / part_number / type (generation) / size + size_unit (nominal capacity, GB or TB) / speed_mts (MT/s) / serial_number |
| `hardware.cpus` | ❌ | CPU array, `slot` is the identity; fields include model |
| `hardware.disks` | ❌ | Disk array, `serial_number` is the identity; fields include type (SSD/HDD) / manufacturer / model / size + size_unit (nominal capacity) |
| `hardware.psus` | ❌ | PSU array, `serial_number` is the identity; fields include manufacturer / model / max_power_w (max power in W) |
| `hardware.gpu` | ❌ | GPU info: `slots` array, `uuid` is the identity; fields include name / serial_number / size + size_unit (VRAM) / driver_version / pcie_id |

**Tolerance semantics aligned with the iagent collector's real-world collection** (since v2.3):

- Identity fields (slot / uuid / serial_number other than NIC `name`) may be null: when a single field
  fails to collect it is set to null, and **an entry whose identity is null is dropped automatically** —
  it never enters the diff or storage and does not affect acceptance of the whole payload
- `mgmt` / `hardware` may be null: treated as not collected, existing data in the DB is not cleared
- `nics[].ips` may be null: a NIC with no IPs sends no IPs
- An empty `agent.timestamp` string is treated as not collected, falling back to the server receive time

**Legacy format compatibility**: legacy push bodies containing only a top-level `hostname` are still accepted;
the server normalizes them automatically into the new structure (legacy `serial_number` →
`hardware.chassis_serial_number`, legacy top-level `timestamp` / `full_sync` / `source` → `agent.*`,
legacy memory `size_gb` → `size` + `GB`). New collectors should always push the new format.

**curl example**:

```bash
curl -X POST http://<host>:8080/api/v1/devices \
  -H "Content-Type: application/json" \
  -d @collector.json
```

**Response**:

```json
{"result": "created", "device_id": 1, "pending_change_id": null}
```

On `diff_created`, `pending_change_id` is the pending-change record id, which can be used to resolve it in the UI or via the API.

**Conflict merging**: when a device already has one pending record that has not been handled yet, and another conflicting push arrives, the **latest push wins** — the diff is recomputed as a whole and replaces the same record, without accumulating with old diffs; multiple records never pile up.

---

## 2. Devices

### `GET /api/v1/devices` — Device list

**Query parameters**:

| Parameter | Default | Description |
|---|---|---|
| `page` | 1 | Page number |
| `page_size` | 20 | Items per page |
| `search` | - | Fuzzy search covering hostname / serial_number / mgmt_ip / NIC business IPs (reverse lookup) |
| `status` | - | `active` / `suspected_offline`, filtered at the SQL layer by the push threshold |
| `tag` | - | Exact match by tag |
| `sort_by` | - | Sort field, whitelist: `hostname` / `serial_number` / `mgmt_ip` / `last_pushed_at` |
| `sort_order` | `asc` | `asc` / `desc` |

```bash
curl "http://<host>:8080/api/v1/devices?page=1&search=demo&status=active"
```

**Response**:

```json
{
  "total": 1,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 1,
      "hostname": "demo-node-01",
      "serial_number": "DEMO-SN-0001",
      "mgmt_mac": "02:00:00:00:00:01",
      "mgmt_ip": "192.0.2.11",
      "mgmt_prefix_length": 24,
      "last_pushed_at": "2026-09-11T08:43:39",
      "created_at": "2026-09-11T08:43:39",
      "updated_at": "2026-09-11T08:43:39",
      "status": "active",
      "nics": [
        {
          "id": 1,
          "name": "eth0",
          "mac": "02:00:00:00:00:02",
          "ips": [{"id": 1, "ip": "198.51.100.11", "prefix_length": 24}]
        }
      ]
    }
  ]
}
```

`status` is computed dynamically: if no push has arrived beyond the threshold (default 1 day, i.e. 24 hours; configurable via `CMDB_OFFLINE_THRESHOLD_DAYS`), the device is marked `suspected_offline`; data is not deleted automatically.

### `GET /api/v1/devices/{id}` — Device detail

The response structure is the same as a list item. Returns 404 if the device does not exist.

### `DELETE /api/v1/devices/{id}` — Manual delete

Hard-deletes the device and its NIC, memory, CPU, disk, PSU and GPU data (pending-change records are deleted along with it); **change history is preserved**. Returns 204 on success.

```bash
curl -X DELETE http://<host>:8080/api/v1/devices/1
```

---

## 3. Pending Conflicts

### `GET /api/v1/pending-changes` — Pending list

**Query parameters**: `status` defaults to `pending`; `all` shows everything including handled records (applied / discarded).

```bash
curl "http://<host>:8080/api/v1/pending-changes"
```

**Response** (`diff` is the field-level diff list):

```json
{
  "items": [
    {
      "id": 1,
      "device_id": 1,
      "source": "collector",
      "payload": {"...": "raw push JSON, same structure as the POST /devices request body"},
      "diff": {
        "fields": [
          {"field": "mgmt.ip", "old": "192.0.2.11", "new": "192.0.2.12"}
        ],
        "nics": [
          {
            "name": "eth1",
            "kind": "removed",
            "changes": [],
            "old": {"name": "eth1", "mac": "02:00:00:00:00:03",
                    "ips": [{"ip": "198.51.100.13", "prefix_length": 24}]},
            "new": null
          }
        ],
        "has_changes": true
      },
      "status": "pending",
      "created_at": "2026-09-11T08:43:57",
      "resolved_at": null
    }
  ]
}
```

The `kind` of `nics` entries:

| kind | Meaning |
|---|---|
| `added` | In the push but not in the DB (new NIC) |
| `removed` | Extra in the DB when full_sync=true (a delete candidate) |
| `changed` | The mac or ips of a same-named NIC changed, listed item by item in the `changes` array |

`memory` / `cpus` entries share the structure above (`slot` as identity) with the same `kind` meanings. `disks` / `psus` entries share the structure above (`serial_number` as identity), as do `gpus` entries (`uuid` as identity).

### `GET /api/v1/pending-changes/{id}` — Diff detail

Returns a single record (payload + diff).

### `POST /api/v1/pending-changes/{id}/resolve` — Resolve

Choose `new` (adopt the new data) or `old` (keep the current state) for each entry. For a `removed` NIC, choosing `new` means deleting that NIC.

**Request body**:

```json
{
  "field_choices": {"mgmt.ip": "new"},
  "nic_choices": {"eth1": "new", "eth2": "old"},
  "memory_choices": {"DIMM_A1": "new"},
  "cpu_choices": {"CPU0": "new"},
  "disk_choices": {"DEMO-SN-0010": "new"},
  "psu_choices": {"DEMO-SN-0005": "new"},
  "gpu_choices": {"GPU-demo-0001": "new"}
}
```

| Field | Description |
|---|---|
| `field_choices` | Host fields: field path -> `new` / `old` |
| `nic_choices` | NIC entries: NIC name -> `new` / `old` |
| `memory_choices` | Memory slot entries: slot name -> `new` / `old` |
| `cpu_choices` | CPU slot entries: slot name -> `new` / `old` |
| `disk_choices` | Disk entries: SN -> `new` / `old` |
| `psu_choices` | PSU entries: SN -> `new` / `old` |
| `gpu_choices` | GPU entries: UUID -> `new` / `old` |

**Response**:

```json
{
  "applied": ["mgmt.ip: 192.0.2.11 -> 192.0.2.12", "nic eth1 deleted"],
  "pending_id": 1,
  "status": "applied"
}
```

After a resolution takes effect it is written to change history; when everything is set to `old` there is no actual change and the record is only marked applied.
Resolving an already-handled record again returns 409.

---

## 4. Change History

### `GET /api/v1/change-history`

**Query parameters**: `device_id` is optional, filtering by device. A device's history remains queryable even after a hard delete.

```bash
curl "http://<host>:8080/api/v1/change-history?device_id=1"
```

**Response**:

```json
{
  "items": [
    {
      "id": 1,
      "device_id": 1,
      "summary": "mgmt.ip: 192.0.2.11 -> 192.0.2.12; nic eth1 deleted",
      "source": "collector",
      "diff": {"...": "full diff at resolution time, same structure as the pending-changes diff"},
      "created_at": "2026-09-11T08:43:57"
    }
  ]
}
```

### `GET /api/v1/change-history/{id}` — Change detail

Contains the full diff at resolution time.

---

## 5. Dashboard

### `GET /api/v1/dashboard`

Asset overview statistics: totals, active / suspected offline, pending-change count, and the 10 most recent changes.

```bash
curl "http://<host>:8080/api/v1/dashboard"
```

```json
{
  "total_devices": 150,
  "active": 61,
  "suspected_offline": 89,
  "pending_changes": 1,
  "recent_changes": ["...the 10 most recent changes, entry structure same as change history (including summary / diff)..."]
}
```

---

## 6. Device Extension Endpoints

### `GET /api/v1/devices/export/csv` — Export CSV

Exports all devices as UTF-8 with BOM (Excel Chinese-compatible); includes the purpose
metadata column. `Content-Disposition: attachment`.

### `POST /api/v1/devices/import/csv` — CSV import

Uploaded as `multipart/form-data` with the field name `file`; the row format matches the export (so it can be imported back directly).

```bash
curl -X POST http://<host>:8080/api/v1/devices/import/csv \
  -F "file=@devices.csv"
```

**Behavior**: each row goes through the same cleansing logic as a push (hostname matching, diffs to pending resolution),
with `source` marked as `csv_import`; the purpose metadata is set along with the import;
`last_pushed_at` is not touched (importing back does not roll back the last push time).

```json
{"created": 1, "unchanged": 0, "diff_created": 0, "errors": []}
```

`errors` describes rows that failed to parse (missing hostname etc.), without affecting the import of the remaining rows.

### `PUT /api/v1/devices/{id}/tags` — Update tags (endpoint kept)

```json
{"tags": ["production", "web"]}
```

The endpoint remains (API compatible); the tags feature has been removed from the UI and CSV.

### `PUT /api/v1/devices/{id}/metadata` — Update device info

Updates CMDB metadata (location/owner/purpose); pushes never change it, only UI/import editing;
location and owner endpoints remain but are removed from the UI, the UI edits purpose only:

```json
{"purpose": "web service"}
```

All fields are optional: `None` = no change, empty string = clear; leading and trailing whitespace is trimmed automatically.
Returns `{"device_id": 1, "location": "...", "owner": "...", "purpose": "..."}`.

### `POST /api/v1/devices/batch-delete` — Batch delete

```json
{"ids": [1, 2, 3]}
```

Same behavior as a single delete (hard delete, history preserved); returns `{"deleted": [the ids actually deleted]}`.

**List search enhancements**: `search` also covers hostname / serial_number / mgmt_ip /
NIC business IPs (reverse device lookup by IP); the `tag` parameter matches tags exactly.

---

## 7. Error Codes

| Status code | Scenario |
|---|---|
| 401 | Not logged in or wrong password (push endpoint excluded) |
| 403 | Logged in but without admin rights (resolve / delete / user management and other write operations) |
| 404 | Device / pending-change record does not exist |
| 409 | Pending-change record already handled (repeated resolve); duplicate username; last-admin protection |
| 422 | Request body validation failed (e.g. missing hostname) |

Error response: `{"detail": "..."}` (FastAPI validation errors are `{"detail": [...]}`).

## 8. System Settings

Key-values are stored in the systemsetting table, with environment variables as defaults; after a change, device status is computed immediately under the new threshold.

### `GET /api/v1/settings/system`

Returns `{"offline_threshold_hours": 24, "api_key_enabled": false}` (the suspected-offline threshold in hours + the API key feature toggle).

### `PUT /api/v1/settings/system`

Admin only (others get 403). Request body `{"offline_threshold_hours": 24, "api_key_enabled": false}`,
threshold value range 1 ~ 8760, invalid values get 422; `api_key_enabled` is optional and kept unchanged when omitted.
When enabled, collector pushes must carry a valid key (see [API keys](#12-api-keys)).

## 9. User Login

User accounts are stored in the users table (PBKDF2 hash); the first admin account is seeded at first startup via `CMDB_ADMIN_USER` /
`CMDB_ADMIN_PASSWORD` (default `admin` / `admin`).
After login an HttpOnly session cookie is issued (HMAC signed, default 7 days,
configurable via `CMDB_SESSION_EXPIRE_DAYS`), carried automatically by subsequent requests.

**Login scope**: only the UI and the APIs it calls; `POST /api/v1/devices` (collector push) stays open.

### `POST /api/v1/auth/login`

```json
{"username": "admin", "password": "admin"}
```

On success returns `{"username": "admin"}` and sets the session cookie; on failure returns 401.

### `POST /api/v1/auth/logout`

Clears the session cookie and returns `{"ok": true}`.

### `POST /api/v1/auth/change-password`

The currently logged-in user changes their own password (the original password must be verified), available to all roles:

```json
{"old_password": "old password", "new_password": "new password"}
```

A wrong original password returns 401.

### `GET /api/v1/auth/me`

Returns the current logged-in user and role `{"username": "admin", "role": "admin"}`; not logged in returns 401
(the UI uses it to determine session state).

## 10. User Management

Admin only (others get 403). There are two roles: `admin` (can operate) and `viewer` (read-only).
The first admin account is seeded at first startup via `CMDB_ADMIN_USER` / `CMDB_ADMIN_PASSWORD`;
role changes take effect immediately (no re-login needed).

### `GET /api/v1/users`

Returns all users: `{"items": [{"id": 1, "username": "admin", "role": "admin", "created_at": "..."}]}`

### `POST /api/v1/users`

```json
{"username": "ops1", "password": "initial password", "role": "viewer"}
```

`role` can only be `admin` / `viewer` (default viewer); a duplicate username returns 409.

### `PUT /api/v1/users/{id}` — Reset password / change role

```json
{"password": "new password"}
```

Both `password` and `role` are optional — whichever is passed is changed; the last admin cannot be demoted (409).

### `DELETE /api/v1/users/{id}` — Delete user

Cannot delete yourself or the last admin (409).

**Permission matrix**:

| Operation | admin | viewer |
|---|---|---|
| Collector push (POST /devices, no login required) | ✅ | ✅ |
| View list / detail / history / dashboard | ✅ | ✅ |
| Resolve / delete device / batch delete | ✅ | ❌ 403 |
| Edit tags / edit device info / CSV import | ✅ | ❌ |
| User management / operation log | ✅ | ❌ |
| API key management | ✅ | ❌ |

## 11. Operation Audit

Management operations are automatically recorded in the audit log (written to the auditlog table in the same transaction as the operation):
device delete / batch delete, tag updates, device info updates, CSV import, resolve, user create/delete/update,
and system settings changes. Admin only can view.

### `GET /api/v1/audit-logs`

An optional `username` query parameter filters by operator, and `limit` caps the number of entries (default 100, max 1000):

```json
{"items": [{"id": 1, "username": "admin", "action": "delete device",
            "detail": "web-01", "created_at": "..."}]}
```

Sorted by time descending; viewer access returns 403.

## 12. API Keys

API keys are for **collector push + read-only API access**, closing the "forged pushes have no gate" gap:

- Format `cmdb_` + 32 hex chars; the full key is stored (viewable/copyable anytime) with a 12-char prefix for identification
- Permissions: with a key, `POST /devices` (push) and any `GET` are allowed; **all other writes and the key management endpoints return 403** — the blast radius of a leaked key stays contained
- Default **off** (system setting `api_key_enabled`): nothing changes, push stays open and the session cookie flow is untouched
- When on: `POST /devices` requires a valid key, missing or invalid returns 401; requests with `X-API-Key` are handled under key permissions (checked before the session cookie); each request refreshes the key's last_used_at
- Revocation (delete) takes effect immediately; requests using the key get 401 right away; creation and revocation are both audited
- Key management is admin-only (others get 403)

### `GET /api/v1/api-keys`

Returns all keys (**including the full key value**, copyable anytime):

```json
{"items": [{"id": 1, "name": "iagent-prod", "key": "cmdb_a1b2c3...",
            "prefix": "cmdb_a1b2c3", "created_at": "...", "last_used_at": "..."}]}
```

### `POST /api/v1/api-keys`

```json
{"name": "iagent-prod"}
```

Returns the newly created key (including the full key value); a blank name returns 422. Name keys per collector/source so they can be revoked individually.

### `DELETE /api/v1/api-keys/{id}` — revoke a key

Returns `{"ok": true}`; a nonexistent key returns 404.

### curl usage

Push (once `api_key_enabled` is on, the key is required):

```bash
curl -X POST http://<host>:8080/api/v1/devices \
  -H "X-API-Key: cmdb_<your-key>" \
  -H "Content-Type: application/json" \
  -d @tests/data/collector_example_full.json
```

Read-only GET works the same way:

```bash
curl -H "X-API-Key: cmdb_<your-key>" http://<host>:8080/api/v1/devices
```

## Appendix: Configuration (environment variables)

| Environment variable | Default | Description |
|---|---|---|
| `CMDB_DB_PATH` | `cmdb.db` | SQLite database file path |
| `CMDB_OFFLINE_THRESHOLD_DAYS` | `1` | Suspected-offline threshold (days), only the initial default for the system setting |
| `CMDB_STATIC_DIR` | `src/cmdb/static` | Frontend build output directory |
| `CMDB_ADMIN_USER` | `admin` | Login username |
| `CMDB_ADMIN_PASSWORD` | `admin` | Login password |
| `CMDB_SECRET_KEY` | `cmdb-session-secret` | Session cookie signing key |
| `CMDB_SESSION_EXPIRE_DAYS` | `7` | Session validity (days) |
