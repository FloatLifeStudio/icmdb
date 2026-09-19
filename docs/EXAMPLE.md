# CMDB 示例数据文档

> English version: [en/EXAMPLE.md](en/EXAMPLE.md)

> 采集器推送格式与完整示例。接口细节见 [API.md](./API.md)。
> 示例 JSON 文件:`tests/data/collector_example_full.json`(可直接用 curl 推送)。
> **本文档与示例数据均为模拟数据**(主机名、序列号、MAC、IP、UUID 等皆为虚构,IP 用 RFC 5737 文档段),非真实设备。

## 完整示例(全部硬件字段)

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

## 字段说明

各字段含义与必填性见 [API.md](./API.md#1-采集推送) 的字段说明表,此处只列要点:

- `agent` / `os` / `mgmt` / `hardware` 四段结构;`os.hostname` 是设备唯一匹配键
- 各硬件条目的身份:网卡 `name`、内存/CPU `slot`、硬盘/电源 `serial_number`、GPU `uuid`
- 所有硬件段均可选,不推不影响现有推送;`hardware.memory` / `cpus` / `disks` / `psus` / `gpu` 缺省即不更新对应类别
- `agent.full_sync=true`(默认)= 全量同步:库中多出的网卡/内存/CPU/硬盘/电源/GPU 进 diff 候删

## iagent 采集器实采格式

iagent(Go 采集器)按同一四段结构推送,但对齐实采语义:**单字段采集失败置 null,
身份为 null 的整条条目自动丢弃**(不进 diff 与存储),`mgmt` / `hardware` /
`nics[].ips` 可为 null,`agent.timestamp` 未采集时发空串。典型推送体:

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

服务端处理效果:身份为 null 的条目(空槽位内存、无 uuid 的 GPU、无 SN 的电源等)
整条丢弃;`mgmt=null` 不写管理口;`timestamp=""` 取服务器接收时间兜底;
`os.virt` 入库并在虚拟化类型变化时进 diff。

## 推送命令

```bash
curl -X POST http://<host>:8080/api/v1/devices \
  -H "Content-Type: application/json" \
  -d @tests/data/collector_example_full.json
```

## 测试场景

1. **首次推送** → `created`(hostname 不存在)或 `diff_created`(已存在,硬件条目作为新增条目进裁决)
2. **字段变化再推**(如 DIMM_A1 换型号、CPU 换型号、`os.virt` 变化)→ `diff_created`,字段级 changed
3. **full_sync=true 少一块硬件**(如删掉 DIMM_B1 或一块硬盘)→ 进 diff 候删,裁决选 `new` 即删除
4. **重复推送相同数据** → `unchanged`
5. **iagent 格式推送**(含 null 身份条目)→ null 条目丢弃,其余正常入库
6. **裁决**:`POST /api/v1/pending-changes/{id}/resolve`,请求体逐条目选 `new` / `old`(默认 UI 全选新值);生效后写变更历史
