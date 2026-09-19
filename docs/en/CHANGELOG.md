# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/), versions follow semantic versioning.

## Unreleased

### Added

- **API keys**: named keys (`cmdb_` + 32 hex, viewable/copyable anytime, admin-managed);
  once enabled in system settings (`api_key_enabled`, default off), collector pushes require a valid
  key (`X-API-Key`), keys allow push + read-only GET, other writes return 403; creation/revocation audited
- **User management**: two roles, admin / viewer (viewer is read-only, write ops return 403);
  admin can create / delete users, reset passwords, change roles, with last-admin protection
- **Change own password**: `POST /api/v1/auth/change-password`, all roles, requires the old password
- **`os.virt` virtualization type**: push / storage / diff / device detail / CSV full chain
  (bare_metal/kvm/vmware/qemu/xen...); existing DBs migrate automatically

### Aligned

- **iagent collector real-world collection semantics** (`POST /api/v1/devices`): identity fields
  (slot / uuid / serial_number) may be null, entries with a null identity are dropped automatically;
  `mgmt` / `hardware` / `nics[].ips` may be null (not collected does not clear existing data);
  an empty `agent.timestamp` string is treated as not collected, falling back to server receive time

## v2.2.0 - 2026-09-13

### Added

- **Push format redesign**: the `agent` / `os` / `mgmt` / `hardware` four-section structure
  (`agent`: version/source/timestamp/full_sync;`hardware`: chassis_serial_number +
  each hardware category); legacy formats with only a top-level hostname are normalized automatically
- **GPU support**: new GPU table (`uuid` as identity: name/SN/VRAM/driver/PCIe),
  full chain coverage across push, diff resolution, storage and display; diff entries carry full old/new
- **User login**: a single admin account (env config) protects the UI and its API calls;
  frontend login page + route guard; `POST /devices` stays open, collectors need no changes
- **Backup script**: `scripts/backup_db.py` uses `VACUUM INTO` for consistent snapshots, keeps 14 copies, cron-ready

### Changed

- **Latest push wins**: an unresolved device has its diff recomputed and replaced by the latest push, no accumulation
- **Two-column conflict comparison**: hardware entries use old (DB) / new (push) columns consistent with host fields
- Memory capacity moved to `size` + `size_unit` (JSON aligned), internal normalized `size_gb` column; automatic DB migration
- Tags normalized into the device_tag table; list query N+1 fixed; search debounce; CSV import fixes
- Example data switched to a common high-performance dual-socket eight-GPU server config (2× Xeon Platinum, 16× 32GB DDR5, 8× A800-80GB)

## v2.1.0 - 2026-09-13

### Added

- **Pending count badge**: the sidebar "conflicts" entry shows the pending count, refreshed right after a resolution
- **Dashboard change feed**: summarized by category (e.g. memory, CPU), rows expand for the full diff

### Changed

- Removed the outdated PLAN.md, design decisions merged into README; added CHANGELOG
- EXAMPLE.md field descriptions deduplicated, pointing to API.md
- Frontend vendor chunk split, main bundle 1MB -> 5.6kB

## v2.0.0 - 2026-09-13

First official release of CMDB v2. Built from scratch: collection push, field-level diff conflict resolution, storage and display.

### Added

- **Collection push**: the only data write entry; hostname matching with three branches (created / unchanged / diff_created),
  conflict merging, `full_sync` full/incremental flag
- **Hardware info**: NICs, memory (slot-level: vendor/model/generation/capacity/speed/SN), CPU (slot + model),
  disks (SSD/HDD, vendor/model/capacity/SN), PSUs (vendor/model/max power/SN)
- **Conflict resolution**: field-level diff with old/new side by side, per-entry new/old choice, applied resolutions written to change history
- **Device management**: pagination/search/tag filter, dynamic status (active / suspected_offline),
  manual delete, batch delete, tag editing
- **Dashboard**: total devices, active/suspected offline, pending count, recent changes
- **CSV import/export**: UTF-8 BOM, Excel compatible, round-trip capable
- **Frontend**: Vue 3 + TS + Element Plus, device list/detail, conflict resolution, dashboard;
  build artifacts served by FastAPI, single service single port
- **Deployment**: unauthenticated REST API, timestamps uniformly naive UTC

> Chinese version: [../CHANGELOG.md](../CHANGELOG.md)
