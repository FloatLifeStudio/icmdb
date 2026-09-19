# CMDB Example Data Guide

> Chinese version: [../EXAMPLE.md](../EXAMPLE.md)

> Collector push format with a complete example. See [API.md](./API.md) for API details.
> Example JSON file: `tests/data/collector_example_full.json` (can be pushed directly with curl).
> **This document and the sample data are simulated** (hostnames, serial numbers, MACs, IPs and UUIDs are
> all fictional; IPs use RFC 5737 documentation ranges), not real devices.

## Complete Example (All Hardware Fields)

```json
{
  "agent": {
    "version": "1.2.0",
    "source": "collector",
    "timestamp": "2026-09-13T10:00:00+08:00",
    "full_sync": true
  },
  "os": {
    "hostname": "demo-gpu-01",
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
        "ips": [
          {
            "ip": "198.51.100.11",
            "prefix_length": 24
          }
        ]
      },
      {
        "name": "eth1",
        "mac": "02:00:00:00:00:03",
        "ips": [
          {
            "ip": "198.51.100.13",
            "prefix_length": 24
          }
        ]
      },
      {
        "name": "eth2",
        "mac": "02:00:00:00:00:04",
        "ips": [
          {
            "ip": "198.51.100.14",
            "prefix_length": 24
          }
        ]
      },
      {
        "name": "eth3",
        "mac": "02:00:00:00:00:05",
        "ips": [
          {
            "ip": "198.51.100.16",
            "prefix_length": 24
          }
        ]
      }
    ],
    "memory": {
      "slots": [
        {
          "slot": "DIMM_A1",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-A01"
        },
        {
          "slot": "DIMM_A2",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-A02"
        },
        {
          "slot": "DIMM_A3",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-A03"
        },
        {
          "slot": "DIMM_A4",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-A04"
        },
        {
          "slot": "DIMM_A5",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-A05"
        },
        {
          "slot": "DIMM_A6",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-A06"
        },
        {
          "slot": "DIMM_A7",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-A07"
        },
        {
          "slot": "DIMM_A8",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-A08"
        },
        {
          "slot": "DIMM_B1",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-B01"
        },
        {
          "slot": "DIMM_B2",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-B02"
        },
        {
          "slot": "DIMM_B3",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-B03"
        },
        {
          "slot": "DIMM_B4",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-B04"
        },
        {
          "slot": "DIMM_B5",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-B05"
        },
        {
          "slot": "DIMM_B6",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-B06"
        },
        {
          "slot": "DIMM_B7",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-B07"
        },
        {
          "slot": "DIMM_B8",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "DEMO-MEM-B08"
        }
      ]
    },
    "cpus": [
      {
        "slot": "CPU0",
        "model": "Intel(R) Xeon(R) Platinum 8470"
      },
      {
        "slot": "CPU1",
        "model": "Intel(R) Xeon(R) Platinum 8470"
      }
    ],
    "disks": [
      {
        "serial_number": "DEMO-SN-0002",
        "type": "SSD",
        "manufacturer": "Samsung",
        "model": "PM1733a",
        "size": 1920,
        "size_unit": "GB"
      },
      {
        "serial_number": "DEMO-SN-0003",
        "type": "SSD",
        "manufacturer": "Samsung",
        "model": "PM1733a",
        "size": 1920,
        "size_unit": "GB"
      }
    ],
    "psus": [
      {
        "serial_number": "DEMO-SN-0005",
        "manufacturer": "GreatWall",
        "model": "CRPS3000D",
        "max_power_w": 3000
      },
      {
        "serial_number": "DEMO-SN-0006",
        "manufacturer": "GreatWall",
        "model": "CRPS3000D",
        "max_power_w": 3000
      }
    ],
    "gpu": {
      "slots": [
        {
          "uuid": "GPU-00000000-0000-0000-0000-000000000000",
          "name": "NVIDIA A800-SXM4-80GB",
          "serial_number": "DEMO-GPU-0002",
          "size": 80,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:3b:00.0"
        },
        {
          "uuid": "GPU-00000000-0000-0000-0000-000000000001",
          "name": "NVIDIA A800-SXM4-80GB",
          "serial_number": "DEMO-GPU-0003",
          "size": 80,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:5c:00.0"
        },
        {
          "uuid": "GPU-00000000-0000-0000-0000-000000000002",
          "name": "NVIDIA A800-SXM4-80GB",
          "serial_number": "DEMO-GPU-0004",
          "size": 80,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:86:00.0"
        },
        {
          "uuid": "GPU-00000000-0000-0000-0000-000000000003",
          "name": "NVIDIA A800-SXM4-80GB",
          "serial_number": "DEMO-GPU-0005",
          "size": 80,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:9a:00.0"
        },
        {
          "uuid": "GPU-00000000-0000-0000-0000-000000000004",
          "name": "NVIDIA A800-SXM4-80GB",
          "serial_number": "DEMO-GPU-0006",
          "size": 80,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:ab:00.0"
        },
        {
          "uuid": "GPU-00000000-0000-0000-0000-000000000005",
          "name": "NVIDIA A800-SXM4-80GB",
          "serial_number": "DEMO-GPU-0007",
          "size": 80,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:af:00.0"
        },
        {
          "uuid": "GPU-00000000-0000-0000-0000-000000000006",
          "name": "NVIDIA A800-SXM4-80GB",
          "serial_number": "DEMO-GPU-0001",
          "size": 80,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:b3:00.0"
        },
        {
          "uuid": "GPU-00000000-0000-0000-0000-000000000007",
          "name": "NVIDIA A800-SXM4-80GB",
          "serial_number": "DEMO-GPU-0008",
          "size": 80,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:d8:00.0"
        }
      ]
    }
  }
}
```

## Field Reference

For the meaning and requiredness of each field, see the field tables in [API.md](./API.md#1-collector-push); only the key points are listed here:

- `agent` / `os` / `mgmt` / `hardware` four-section structure; `os.hostname` is the unique device matching key
- Identity of each hardware entry: NICs `name`, memory/CPU `slot`, disks/PSUs `serial_number`, GPU `uuid`
- All hardware sections are optional; omitting one does not affect existing pushes; a missing `hardware.memory` / `cpus` / `disks` / `psus` / `gpu` means that category is not updated
- `agent.full_sync=true` (default) = full sync: NICs/memory/CPU/disks/PSUs/GPUs found in the DB beyond the push become diff candidates for deletion

## iagent Collector Real-World Format

iagent (a Go collector) pushes with the same four-section structure, but aligned with real-world collection semantics: **a single-field collection failure sets the field to null,
and an entire entry whose identity is null is dropped automatically** (it never reaches diff or storage); `mgmt` / `hardware` /
`nics[].ips` may be null, and `agent.timestamp` is sent as an empty string when not collected. A typical push body:

```json
{
  "agent": {"version": "0.3.0", "source": "iagent", "timestamp": "", "full_sync": true},
  "os": {
    "hostname": "demo-gpu-02",
    "type": "linux",
    "version": "Ubuntu 22.04",
    "kernel": "5.15.0-91-generic",
    "virt": "kvm"
  },
  "mgmt": null,
  "hardware": {
    "chassis_serial_number": null,
    "nics": [
      {"name": "eth0", "mac": "02:00:00:00:00:2A", "ips": null},
      {"name": "eth1", "mac": null, "ips": [{"ip": "203.0.113.7", "prefix_length": 24}]}
    ],
    "memory": {
      "slots": [
        {"slot": "DIMM_A1", "size": 32, "size_unit": "GB"},
        {"slot": null, "size": null}
      ]
    },
    "cpus": [
      {"slot": "CPU0", "model": "Intel(R) Xeon Platinum 8470"},
      {"slot": null, "model": null}
    ],
    "disks": [
      {"serial_number": "DEMO-SN-0004", "type": "SSD", "size": 480, "size_unit": "GB"},
      {"serial_number": null, "type": "HDD"}
    ],
    "psus": [{"serial_number": null, "max_power_w": 2700}],
    "gpu": {
      "slots": [
        {"uuid": "GPU-demo-0002", "name": "NVIDIA A800-SXM4-80GB", "size": 80, "size_unit": "GB"},
        {"uuid": null, "name": null}
      ]
    }
  }
}
```

Server-side processing: entries with a null identity (empty memory slots, GPUs without a uuid, PSUs without an SN, etc.)
are dropped entirely; `mgmt=null` skips the management port; `timestamp=""` falls back to the server's receive time;
`os.virt` is stored and enters the diff when the virtualization type changes.

## Push Command

```bash
curl -X POST http://<host>:8080/api/v1/devices \
  -H "Content-Type: application/json" \
  -d @tests/data/collector_example_full.json
```

## Test Scenarios

1. **First push** → `created` (hostname does not exist) or `diff_created` (already exists, hardware entries enter resolution as new entries)
2. **Push again with changed fields** (e.g. DIMM_A1 with a different model, a different CPU model, a changed `os.virt`) → `diff_created`, with field-level changed entries
3. **full_sync=true with one hardware item removed** (e.g. delete DIMM_B1 or a disk) → enters diff as a deletion candidate; choosing `new` in the resolution deletes it
4. **Push the same data repeatedly** → `unchanged`
5. **Push in iagent format** (with null-identity entries) → null entries are dropped, the rest are stored normally
6. **Resolution**: `POST /api/v1/pending-changes/{id}/resolve`, choosing `new` / `old` per entry in the request body (the UI defaults to selecting all new values); once effective, the change is written to change history
