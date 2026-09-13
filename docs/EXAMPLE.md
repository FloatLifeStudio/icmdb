# CMDB 示例数据文档

> 采集器推送格式与完整示例。接口细节见 [API.md](./API.md)。
> 示例 JSON 文件:`tests/data/collector_example_full.json`(可直接用 curl 推送)。

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
    "hostname": "S1A01DC-VL101",
    "type": "Linux",
    "version": "Ubuntu 22.04",
    "kernel": "5.15.0-91-generic"
  },
  "mgmt": {
    "mac": "AA:BB:CC:DD:EE:01",
    "ip": "192.168.10.101",
    "prefix_length": 24
  },
  "hardware": {
    "chassis_serial_number": "PF4ABC123456",
    "nics": [
      {
        "name": "eth0",
        "mac": "AA:BB:CC:DD:EE:02",
        "ips": [{"ip": "10.10.1.101", "prefix_length": 24}]
      },
      {
        "name": "eth1",
        "mac": "AA:BB:CC:DD:EE:03",
        "ips": [{"ip": "10.10.2.101", "prefix_length": 24}]
      },
      {
        "name": "eth2",
        "mac": "AA:BB:CC:DD:EE:04",
        "ips": [{"ip": "10.10.3.101", "prefix_length": 24}]
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
          "serial_number": "123123456"
        },
        {
          "slot": "DIMM_A2",
          "manufacturer": "Samsung",
          "part_number": "M321R8GA0BB0-CQKZJ",
          "type": "DDR5",
          "size": 64,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "123123457"
        },
        {
          "slot": "DIMM_B1",
          "manufacturer": "Kingston",
          "part_number": "KSM56R46BD4PMI-32HAI",
          "type": "DDR5",
          "size": 32,
          "size_unit": "GB",
          "speed_mts": 4800,
          "serial_number": "123123458"
        }
      ]
    },
    "cpus": [
      {"slot": "CPU0", "model": "Intel(R) Xeon(R) Gold 6448Y"},
      {"slot": "CPU1", "model": "Intel(R) Xeon(R) Gold 6448Y"},
      {"slot": "CPU2", "model": "Intel(R) Xeon(R) Gold 6448Y"}
    ],
    "disks": [
      {
        "serial_number": "123123123",
        "type": "SSD",
        "manufacturer": "Samsung",
        "model": "990EVO",
        "size": 8,
        "size_unit": "TB"
      },
      {
        "serial_number": "123123124",
        "type": "SSD",
        "manufacturer": "Samsung",
        "model": "990EVO",
        "size": 8,
        "size_unit": "TB"
      },
      {
        "serial_number": "123456",
        "type": "HDD",
        "manufacturer": "HGST",
        "model": "HUH728080ALE604",
        "size": 8,
        "size_unit": "TB"
      }
    ],
    "psus": [
      {
        "serial_number": "2P0123123132",
        "manufacturer": "GreatWall",
        "model": "CRPS2700D2",
        "max_power_w": 2700
      },
      {
        "serial_number": "2P0123123133",
        "manufacturer": "GreatWall",
        "model": "CRPS2700D2",
        "max_power_w": 2700
      },
      {
        "serial_number": "2P0123123134",
        "manufacturer": "GreatWall",
        "model": "CRPS2700D2",
        "max_power_w": 2700
      }
    ],
    "gpu": {
      "slots": [
        {
          "uuid": "GPU-3f2a1b9c-8d4e-4f6a-b7c8-9a1b2c3d4e5f",
          "name": "NVIDIA GeForce RTX 4090",
          "serial_number": "G123456",
          "size": 24,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:3b:00.0"
        },
        {
          "uuid": "GPU-5a4b3c2d-1e6f-4a5b-8c9d-0e1f2a3b4c5d",
          "name": "NVIDIA GeForce RTX 4090",
          "serial_number": "G123457",
          "size": 24,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:5c:00.0"
        },
        {
          "uuid": "GPU-7c8d9e0f-1a2b-4c3d-8e5f-6a7b8c9d0e1f",
          "name": "NVIDIA A100-SXM4-80GB",
          "serial_number": "G123458",
          "size": 80,
          "size_unit": "GB",
          "driver_version": "550.54.14",
          "pcie_id": "0000:8d:00.0"
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

## 推送命令

```bash
curl -X POST http://<host>:8080/api/v1/devices \
  -H "Content-Type: application/json" \
  -d @tests/data/collector_example_full.json
```

## 测试场景

1. **首次推送** → `created`(hostname 不存在)或 `diff_created`(已存在,硬件条目作为新增条目进裁决)
2. **字段变化再推**(如 DIMM_A1 换型号、CPU 换型号)→ `diff_created`,字段级 changed
3. **full_sync=true 少一块硬件**(如删掉 DIMM_B1 或一块硬盘)→ 进 diff 候删,裁决选 `new` 即删除
4. **重复推送相同数据** → `unchanged`
5. **裁决**:`POST /api/v1/pending-changes/{id}/resolve`,请求体逐条目选 `new` / `old`(默认 UI 全选新值);生效后写变更历史
