# CMDB v2

CMDB (CMDB v2) — collection push, field-level diff conflict resolution, storage and display.

Pipeline: collection (external shell) → JSON → CMDB API → CMDB storage → UI display. The system only handles storage and queries; it does not do collection.

## Design Decisions

Core trade-offs, confirmed item by item:

- **Device identity**: hostname (the unique matching key; a host rename = a new device plus a leftover old device, the old one must be deleted manually)
- **Push format**: `agent` / `os` / `mgmt` / `hardware` four-section structure (v2.2); aligned with the real-world collection semantics of the iagent collector (v2.3): identity fields may be null, entries with a null identity are dropped automatically, `mgmt` / `hardware` / `ips` may be null; the legacy format containing only a top-level hostname is automatically normalized for compatibility
- **nics semantics**: explicit full sync in the push body (`agent.full_sync=true`; extras in the DB become diff candidates for deletion) / incremental (only what is pushed is stored)
- **Conflict resolution**: field-level diff; when the same device already has a pending change, the diff is recomputed from the latest push and replaces it wholesale (no accumulation); once a resolution takes effect it is written to change_history
- **Hardware extensions**: NICs (`name` as identity), memory/CPU (`slot` as identity), disks/PSUs (`serial_number` as identity), GPU (`uuid` as identity); OS includes virtualization type `os.virt`; fields are optional — a category not pushed is not updated
- **Suspected offline**: computed dynamically at query time, default threshold of 1 day (24 hours), editable online on the system settings page (`CMDB_OFFLINE_THRESHOLD_DAYS` only serves as the initial default); data is never deleted automatically
- **Write permissions**: the push API is the only data write entry point; the UI supports management operations such as resolution, deletion, tags and CSV import
- **Device metadata**: purpose is CMDB metadata (edited inline on the detail page, imported/exported via CSV, never changed by pushes); location/owner/tags have been removed from the UI and CSV
- **Operation audit**: management operations such as deletion/resolution/tags/metadata/user management/system settings are automatically recorded in the audit log, visible in the UI to admin only
- **Users and roles**: two-level roles — admin (can operate) / viewer (view only); admin can manage users and reset passwords; all users can change their own password; the push API requires no authentication by default, so collectors need no changes
- **API keys**: named keys (`cmdb_` prefix, viewable/copyable/revocable anytime), managed by admin; once enabled in system settings, pushes require a key (the `X-API-Key` header), keys = push + read-only, blocking forged pushes
- **Deletion semantics**: DELETE hard-deletes a device and its NIC, memory, CPU, disk, PSU and GPU data; change_history is preserved (for traceability)

## Tech Stack

- Backend: Python FastAPI + SQLite (SQLModel ORM)
- Frontend: Vue 3 + TS + Element Plus (the build output is served by FastAPI — one service, one port)

## Quick Start

```bash
# Backend (run uv sync first to install dependencies on the first run)
uv sync
uv run uvicorn cmdb.main:app --port 8080

# Frontend dev (in another terminal, /api proxied to 8080)
cd web/frontend && npm install && npm run dev
```

Production deployment: after `npm run build`, the frontend output goes to `src/cmdb/static` and is served by FastAPI,
so only the backend service needs to be started.

Database backup: `scripts/backup_db.py` uses `VACUUM INTO` to produce a consistent snapshot into `backups/`,
keeping the most recent 14 copies; it can be hooked into cron to run daily:

```cron
40 2 * * * /usr/bin/python3 /home/fs/icmdb/backup_db.py >> /home/fs/icmdb/backups/backup.log 2>&1
```

## Testing

```bash
uv run pytest tests/ -v
```

## Configuration (Environment Variables)

| Environment Variable | Default | Description |
|---|---|---|
| `CMDB_DB_PATH` | `cmdb.db` | SQLite database file path |
| `CMDB_OFFLINE_THRESHOLD_DAYS` | `1` | Suspected-offline threshold (days), only the initial default for system settings |
| `CMDB_STATIC_DIR` | `src/cmdb/static` | Frontend build output directory |
| `CMDB_ADMIN_USER` | `admin` | Login username |
| `CMDB_ADMIN_PASSWORD` | `admin` | Login password |
| `CMDB_SECRET_KEY` | `cmdb-session-secret` | Session cookie signing key |
| `CMDB_SESSION_EXPIRE_DAYS` | `7` | Session lifetime (days) |

## Documentation

- Overview (database/API/push JSON in detail with design review): [docs/OVERVIEW.md](docs/OVERVIEW.md)
- API usage guide: [docs/API.md](docs/API.md)
- Example data guide: [docs/EXAMPLE.md](docs/EXAMPLE.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
