# CMDB 数据与接口全景文档

> English version: [en/OVERVIEW.md](en/OVERVIEW.md)

本文档是 CMDB v2 的全景介绍:推送 JSON、数据库每张表、API 每个接口、每个字段的作用与对应关系,以及设计理由与合理性评审。日常操作速查见 [API.md](API.md),采集示例见 [EXAMPLE.md](EXAMPLE.md)。

---

## 目录

- [1. 总体架构与数据流](#1-总体架构与数据流)
- [2. 推送 JSON(采集端对接)](#2-推送-json采集端对接)
- [3. 数据库表](#3-数据库表)
- [4. API 接口](#4-api-接口)
- [5. 字段对应关系总表](#5-字段对应关系总表)
- [6. 设计理由汇总](#6-设计理由汇总)
- [7. 设计合理性评审](#7-设计合理性评审)

---

## 1. 总体架构与数据流

```
采集器(iagent / 旧采集器 / curl)
        │  POST /api/v1/devices(开放,无需登录)
        ▼
┌───────────────────────────────────────────────────┐
│ FastAPI(cmdb.main)                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────────────┐   │
│  │schemas  │→ │services │→ │ models(SQLModel)│   │
│  │校验/归一 │  │diff/    │  │ 14 张表          │   │
│  │         │  │ingest/  │  │                 │   │
│  │         │  │resolve  │  │                 │   │
│  └─────────┘  └─────────┘  └─────────────────┘   │
│  中间件:会话 cookie + 角色(admin/viewer)拦截    │
└───────────────────────────────────────────────────┘
        │
        ▼
Vue 3 前端(构建产物由 FastAPI 托管,单服务单端口 8080)
```

**核心数据流(一次推送的三种结局)**:

```
推送 → hostname 匹配库中设备
  ├─ 不存在            → created       直接创建设备 + 全部硬件
  ├─ 存在且 diff 为空   → unchanged     仅刷新 last_pushed_at
  └─ 存在且有差异       → diff_created  差异进 pending_change,现有数据不动,等人工裁决
```

**关键设计原则**:推送 API 是唯一的数据写入入口。人工裁决(adopt new data)、CSV 导入、UI 编辑都是围绕这个入口的辅助通道;所有变更都在可追溯、可回滚(裁决选 old)的框架内发生。

---

## 2. 推送 JSON(采集端对接)

### 2.1 新格式(四段结构)

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

### 2.2 逐字段说明

**agent — 采集器信息**

| 字段 | 类型 | 作用 | 对应存储 |
|---|---|---|---|
| `version` | string,可空 | 采集器版本号 | `device.agent_version` |
| `source` | string,可空 | 来源标识(`iagent` / `csv_import` 等),进待裁决记录 | `pending_change.source` |
| `timestamp` | datetime,可空 | 采集时间;**空串视为未采集**;缺省时服务器接收时间兜底 | `device.last_pushed_at` |
| `full_sync` | bool,默认 true | 全量同步标记:库中多出的硬件条目进 diff 候删;false = 增量(只存推送的) | 不落库,影响 diff 行为 |

**os — 操作系统**

| 字段 | 类型 | 作用 | 对应存储 |
|---|---|---|---|
| `hostname` | string,**必填** | 设备唯一匹配键,缺 hostname 整包 422 | `device.hostname` |
| `type` | string,可空 | OS 类型(Linux / Windows...) | `device.os_type` |
| `version` | string,可空 | OS 版本(Ubuntu 22.04...) | `device.os_version` |
| `kernel` | string,可空 | 内核版本 | `device.kernel` |
| `virt` | string,可空 | 虚拟化类型(bare_metal / kvm / ...) | `device.os_virt` |

**mgmt — 管理口**(整段可为 null,视为未采集)

| 字段 | 类型 | 作用 | 对应存储 |
|---|---|---|---|
| `mac` | string,可空 | 管理口 MAC | `device.mgmt_mac` |
| `ip` | string,可空 | 管理口 IP | `device.mgmt_ip` |
| `prefix_length` | int,可空 | 子网前缀长度 | `device.mgmt_prefix_length` |

**hardware — 硬件**(整段可为 null)

| 字段 | 类型 | 作用 | 对应存储 |
|---|---|---|---|
| `chassis_serial_number` | string,可空 | 整机序列号 | `device.serial_number` |
| `nics[]` | list | 网卡,`name` 为身份 | `nic` + `nic_ip` 表 |
| `nics[].name` | string,**必填** | 网卡名(eth0...),device 内唯一 | `nic.name` |
| `nics[].mac` | string,可空 | MAC 地址 | `nic.mac` |
| `nics[].ips[]` | list,可空 | IP 列表,无 IP 网卡置 null | `nic_ip` 表 |
| `nics[].ips[].ip` | string,必填 | IP 地址 | `nic_ip.ip` |
| `nics[].ips[].prefix_length` | int,可空 | 子网前缀 | `nic_ip.prefix_length` |
| `memory.slots[]` | list | 内存,`slot` 为身份 | `memoryslot` 表 |
| `memory.slots[].slot` | string,可空 | �位号(DIMM_A1),null 自动丢弃 | `memoryslot.slot` |
| `...manufacturer` / `part_number` | string,可空 | 厂商 / 型号颗粒 | 同表同名列 |
| `...type` | string,可空 | 内存类型(DDR4/DDR5...) | 同表同名列 |
| `...size` / `size_unit` | int + string,可空 | 标称容量(32 GB / 64 GB) | 同表同名列 + `size_gb` 归一化列 |
| `...speed_mts` | int,可空 | 频率(MT/s) | `memoryslot.speed_mts` |
| `...serial_number` | string,可空 | 内存条 SN(可与同 SN 硬盘区分,作用域在表内) | 同表同名列 |
| `cpus[]` | list | CPU,`slot` 为身份(CPU0) | `cpu` 表 |
| `cpus[].slot` | string,可空 | 槽位号,null 自动丢弃 | `cpu.slot` |
| `cpus[].model` | string,可空 | CPU 型号 | `cpu.model` |
| `disks[]` | list | 硬盘,`serial_number` 为身份 | `disk` 表 |
| `disks[].serial_number` | string,可空 | 盘 SN(自然身份:换盘 = 旧删新增),null 自动丢弃 | `disk.serial_number` |
| `...type` | string,可空 | SSD / HDD | `disk.type` |
| `...manufacturer` / `model` | string,可空 | 品牌 / 型号 | 同表同名列 |
| `...size` / `size_unit` | int + string,可空 | 标称容量 | 同表同名列 + `size_gb` |
| `psus[]` | list | 电源模块,`serial_number` 为身份 | `psu` 表 |
| `psus[].serial_number` | string,可空 | 电源 SN,null 自动丢弃 | `psu.serial_number` |
| `...manufacturer` / `model` | string,可空 | 品牌 / 型号 | 同表同名列 |
| `...max_power_w` | int,可空 | 最大功率(瓦) | `psu.max_power_w` |
| `gpu.slots[]` | list | GPU,`uuid` 为身份(nvidia-smi 的 UUID,稳定且全局唯一) | `gpu` 表 |
| `gpu.slots[].uuid` | string,可空 | UUID,null 自动丢弃 | `gpu.uuid` |
| `...name` / `serial_number` | string,可空 | 型号 / SN | 同表同名列 |
| `...size` / `size_unit` | int + string,可空 | 显存 | 同表同名列 + `size_gb` |
| `...driver_version` | string,可空 | 驱动版本 | `gpu.driver_version` |
| `...pcie_id` | string,可空 | PCIe 地址 | `gpu.pcie_id` |

### 2.3 容错语义(对齐 iagent 采集器)

| 情况 | 处理 | 理由 |
|---|---|---|
| 身份字段(slot / uuid / serial_number)为 null | **整条自动丢弃**,不进 diff 与存储 | 采集失败的槽位没有身份,存了也无法比对;不影响整包接收 |
| 标量字段为 null | 视为"未采集",**不清空**库中已有数据 | 部分采集失败不应抹掉上次采集到的值 |
| `mgmt` / `hardware` / `nics[].ips` 为 null | 视为未采集 / 无 IP | 采集器对无数据字段发 null |
| `agent.timestamp` 为空串 | 视为未采集,服务器接收时间兜底 | 采集器未取到时间时发空串 |
| 缺 `hostname` | 整包 422 | 无匹配键无法入库 |

### 2.4 旧格式自动兼容

仅含顶层 `hostname` / `serial_number` / `nics` 等扁平结构的旧采集器推送,服务端自动归一化(`normalise_legacy`)为新格式;旧格式内存的 `size_gb` 转为 `size + size_unit`。旧格式默认 `full_sync=false`(增量语义)。

---

## 3. 数据库表

SQLite(WAL 模式,外键约束开启),SQLModel 建表,共 **14 张表**。所有子表通过 `device_id` 外键关联 `device`,并建索引。

### 3.1 `device` — 主机主表

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | 自增主键 |
| `hostname` | string,唯一+索引 | 设备唯一匹配键 |
| `serial_number` | string | 整机序列号(来自 `hardware.chassis_serial_number`) |
| `mgmt_mac` / `mgmt_ip` / `mgmt_prefix_length` | string × 2 / int | 管理口三元组 |
| `os_type` / `os_version` / `os_virt` / `kernel` | string | OS 四要素(type/version/virt 来自 `os.*`) |
| `agent_version` | string | 采集器版本 |
| `purpose` | string | **CMDB 元数据**:用途。UI 内联编辑(仅 admin)、CSV 导入导出,**推送不改**;location/owner 接口保留但已从界面与 CSV 移除 |
| `last_pushed_at` | datetime | 最后一次推送时间(naive UTC),疑似下线判定的依据 |
| `created_at` / `updated_at` | datetime | 创建 / 最后更新时间 |

### 3.2 `nic` / `nic_ip` — 网卡与 IP

`nic`:id、`device_id`(FK+索引)、`name`(身份,唯一约束 device_id+name)、`mac`。
`nic_ip`:id、`nic_id`(FK+索引)、`ip`(唯一约束 nic_id+ip)、`prefix_length`。

IP 单独一张表:一台网卡可有多个 IP(IPv4/IPv6、多地址),一对多必须拆表。

### 3.3 `memoryslot` — 内存槽位

id、`device_id`(FK+索引)、`slot`(身份,唯一约束 device_id+slot)、`manufacturer`、`part_number`、`type`(内存类型,DDR4/DDR5)、`size` + `size_unit`(标称原始值)、`size_gb`(归一化列,TB×1024,便于排序统计)、`speed_mts`、`serial_number`。

### 3.4 `cpu` — CPU 槽位

id、`device_id`(FK+索引)、`slot`(身份,唯一约束 device_id+slot)、`model`。CPU 采集到的就型号一项,刻意保持最简。

### 3.5 `disk` — 硬盘

id、`device_id`(FK+索引)、`serial_number`(身份,唯一约束 device_id+serial_number)、`type`(SSD/HDD)、`manufacturer`、`model`、`size` + `size_unit` + `size_gb`(归一化)。SN 是硬盘的自然身份:同 SN 数据变化 = changed,新 SN = added,换盘 = 旧盘删 + 新盘增。

### 3.6 `psu` — 电源模块

id、`device_id`(FK+索引)、`serial_number`(身份,唯一约束 device_id+serial_number)、`manufacturer`、`model`、`max_power_w`。

### 3.7 `gpu` — GPU

id、`device_id`(FK+索引)、`uuid`(身份,唯一约束 device_id+uuid)、`name`、`serial_number`、`size` + `size_unit` + `size_gb`、`driver_version`、`pcie_id`。

### 3.8 `device_tag` — 设备标签

id、`device_id`(FK+索引)、`name`(索引),唯一约束 device_id+name。一行一个 device-tag 对。**CMDB 元数据**(不属于采集数据),替代旧版的逗号分隔 TEXT 列——拆表后可以精确匹配筛选、加唯一约束。表保留,标签功能已从界面与 CSV 移除。

### 3.9 `pending_change` — 冲突待裁决

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | 自增主键 |
| `device_id` | int,FK+索引 | 关联设备 |
| `source` | string | 推送来源(agent.source) |
| `payload` | JSON | 推送原始 JSON(裁决时可回看完整上下文) |
| `diff` | JSON | 字段级差异清单,结构见 §5.2 |
| `status` | string,索引 | pending / applied / discarded |
| `created_at` / `resolved_at` | datetime | 创建 / 裁决时间 |

**同一设备仅一条 pending**:新推送重算 diff 整体替换,不累计——裁决人始终面对最新视角。

### 3.10 `changehistory` — 变更流水

id、`device_id`(索引,**不设外键**)、`summary`(摘要,如"硬盘 DISK-SN-001 新增")、`source`、`diff`(JSON,裁决时的完整差异清单)、`created_at`(索引)。

`device_id` 不设外键是刻意的:设备硬删后历史记录保留,追溯价值独立于设备存活。

### 3.11 `user` — 用户

id、`username`(唯一+索引)、`password_hash`(PBKDF2-SHA256,存 salt:digest)、`role`(admin / viewer,索引)、`created_at`。

### 3.12 `systemsetting` — 系统设置

id、`key`(唯一+索引)、`value`、`updated_at`。键值存储;当前唯一在用键 `offline_threshold_hours`(疑似下线阈值,小时),环境变量 `CMDB_OFFLINE_THRESHOLD_DAYS` 仅作初始默认值。

### 3.13 `auditlog` — 操作审计

id、`username`(索引)、`action`(索引,如"删除设备")、`detail`(详情,如 hostname)、`created_at`(索引)。管理操作随操作同一事务写入;仅 admin 可查。

### 3.14 轻量迁移机制

`database.py` 的 `migrate()` 对既有表做幂等补列(SQLite ALTER TABLE)+ 旧数据回填(tags TEXT 拆表、disk/memory 容量归一化、存量表补索引);新库由 `create_all` 直接建出。没有引入 Alembic——表结构变化低频、SQLite 单文件场景下够用。

---

## 4. API 接口

全部接口挂在 `/api/v1` 下。鉴权由中间件统一处理:**除登录/会话检查外均要求登录**;写操作(裁决/删除/标签/元数据/用户管理/设置)仅 admin。角色从库中实时查询,变更即时生效。系统设置 `api_key_enabled` 开启后,`POST /devices` 必须携带有效 API 密钥(请求头 `X-API-Key`,见 API.md §12);带密钥的请求也可只读 GET,其余写操作返回 403。

### 4.1 采集推送

| 接口 | 鉴权 | 说明 |
|---|---|---|
| `POST /devices` | **开放** | 唯一数据写入入口。请求体见 §2;旧格式自动转换。返回 `{"result": "created\|unchanged\|diff_created", "device_id": N, "pending_change_id": N|null}` |

**为什么开放**:采集器分布广泛且无用户体系,要求登录会阻碍接入;推送只创建设备与进待裁决,真正的数据变更(裁决)有人工把关,伪造推送的破坏面可控。

### 4.2 设备

| 接口 | 鉴权 | 说明 |
|---|---|---|
| `GET /devices` | 登录 | 分页(`page`/`page_size`,默认 1/20)。`search` 模糊匹配 hostname / serial_number / mgmt_ip + **网卡业务 IP 反查**;`status=active\|suspected_offline` 按阈值在 SQL 层筛选;`tag` �确匹配;`sort_by` 白名单(hostname/serial_number/mgmt_ip/last_pushed_at)+ `sort_order`。返回 `{total, page, page_size, items: [DeviceOut]}` |
| `GET /devices/{id}` | 登录 | 设备详情,完整 DeviceOut(含全部子表数据与动态 status) |
| `DELETE /devices/{id}` | admin | 硬删设备与全部子表数据;change_history 保留。204 |
| `POST /devices/batch-delete` | admin | `{"ids": [1,2,3]}`,行为同单个删除;返回 `{"deleted": [id]}` |
| `PUT /devices/{id}/tags` | admin | `{"tags": ["生产","web"]}` 全量替换 |
| `PUT /devices/{id}/metadata` | admin | 更新 location/owner/purpose;字段可选,None=不改、空串=清空 |
| `GET /devices/export/csv` | 登录 | 导出全部设备 CSV(UTF-8 BOM,Excel 兼容),含 purpose 元数据列 |
| `POST /devices/import/csv` | admin | multipart 上传,行格式与导出一致(可回导);逐行走推送清洗逻辑,`source=csv_import`,不触碰 `last_pushed_at` |

**DeviceOut 结构**(列表与详情共用):id、hostname、serial_number、os_type/version/virt、kernel、agent_version、location/owner/purpose、mgmt_mac/ip/prefix_length、last_pushed_at、created_at/updated_at、**status(动态计算:active / suspected_offline,不入库)**、tags、nics(含 ips)、memory、cpus、disks、psus、gpus。

**status 为什么不入库**:疑似下线是"现在距上次推送多久"的相对判断,阈值可改,入库就要全量刷新;查询时动态计算永远与当前设置一致。

### 4.3 冲突待裁决

| 接口 | 鉴权 | 说明 |
|---|---|---|
| `GET /pending-changes` | 登录 | `status=pending`(默认)/ `all`;按创建时间排序 |
| `GET /pending-changes/{id}` | 登录 | diff 详情:payload + 字段级差异清单 |
| `POST /pending-changes/{id}/resolve` | admin | 裁决,请求体见下;重复裁决 409 |

裁决请求体——每条 diff 条目选 `new`(采用新数据)/ `old`(保留现状);对 removed 条目选 `new` 即删除:

```json
{
  "field_choices": {"mgmt.ip": "new"},
  "nic_choices": {"eth3": "new", "eth1": "old"},
  "memory_choices": {}, "cpu_choices": {},
  "disk_choices": {}, "psu_choices": {}, "gpu_choices": {}
}
```

裁决生效后写 change_history,pending 置 applied(全部选 old 且无实际改动则 discarded)。应用逻辑幂等:added 已存在跳过、removed 不存在跳过。

**为什么要人工裁决**:采集数据可能有误(采集器 bug、临时状态如插拔内存),自动覆盖会丢失正确现状;字段级二选一让管理员看清每一处差异再决定,且全程留痕。

### 4.4 变更历史(只读)

| 接口 | 鉴权 | 说明 |
|---|---|---|
| `GET /change-history` | 登录 | `device_id` 可选过滤;新在前;设备硬删后仍可查 |
| `GET /change-history/{id}` | 登录 | 含裁决时的完整 diff |

### 4.5 仪表盘(只读)

| 接口 | 鉴权 | 说明 |
|---|---|---|
| `GET /dashboard` | 登录 | `total_devices`、`active` / `suspected_offline`(按当前阈值动态算)、`pending_changes`、`recent_changes`(最近 10 条变更) |

### 4.6 用户登录 / 用户管理

| 接口 | 鉴权 | 说明 |
|---|---|---|
| `POST /auth/login` | 开放 | 校验 users 表,签发 HttpOnly 会话 cookie(HMAC 签名,默认 7 天) |
| `POST /auth/logout` | 登录 | 清除 cookie |
| `POST /auth/change-password` | 登录 | 改自己密码,需验原密码,所有角色可用 |
| `GET /auth/me` | 开放* | 返回当前用户与角色;未登录 401。前端用它判断会话状态与 admin 权限 |
| `GET /users` | admin | 用户列表 |
| `POST /users` | admin | 新增用户(role=admin/viewer,默认 viewer);重复 409 |
| `PUT /users/{id}` | admin | 重置密码 / 修改角色,传哪个改哪个;不能降级最后一个管理员 409 |
| `DELETE /users/{id}` | admin | 不能删自己与最后一个管理员 409 |

### 4.7 系统设置 / 操作审计

| 接口 | 鉴权 | 说明 |
|---|---|---|
| `GET /settings/system` | 登录 | `{"offline_threshold_hours": 24}` |
| `PUT /settings/system` | admin | 修改阈值(1~8760 小时),设备状态按新阈值即时计算 |
| `GET /audit-logs` | admin | 审计日志,`username` 过滤、`limit`(默认 100,最大 1000),新在前 |

---

## 5. 字段对应关系总表

### 5.1 推送 JSON → 数据库 → API 响应

| 推送字段 | 数据库 | 响应字段(DeviceOut) |
|---|---|---|
| `os.hostname` | `device.hostname` | `hostname` |
| `hardware.chassis_serial_number` | `device.serial_number` | `serial_number` |
| `os.type` / `os.version` / `os.kernel` / `os.virt` | `device.os_type` / `os_version` / `kernel` / `os_virt` | 同名 |
| `mgmt.mac` / `mgmt.ip` / `mgmt.prefix_length` | `device.mgmt_mac` / `mgmt_ip` / `mgmt_prefix_length` | 同名 |
| `agent.version` | `device.agent_version` | `agent_version` |
| `agent.timestamp`(或接收时间) | `device.last_pushed_at` | `last_pushed_at` + 动态 `status` |
| —(非采集数据) | `device.location` / `owner` / `purpose` | 同名 |
| —(非采集数据) | `devicetag` 表 | `tags` |
| `hardware.nics[].name` / `.mac` | `nic.name` / `nic.mac` | `nics[].name` / `.mac` |
| `hardware.nics[].ips[]` | `nic_ip` 表 | `nics[].ips[]` |
| `hardware.memory.slots[]` | `memoryslot` 表 | `memory[]`(响应字段名不带 slots) |
| `hardware.cpus[]` | `cpu` 表 | `cpus[]` |
| `hardware.disks[]` | `disk` 表 | `disks[]` |
| `hardware.psus[]` | `psu` 表 | `psus[]` |
| `hardware.gpu.slots[]` | `gpu` 表 | `gpus[]`(响应字段名不带 slots) |

注意两处命名差异:推送体里内存是 `memory.slots[]`、GPU 是 `gpu.slots[]`(对齐采集器 JSON 结构);响应里是平铺的 `memory[]` / `gpus[]`(每个条目带数据库 `id`)。

### 5.2 diff 清单结构(pending_change.diff / changehistory.diff)

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

- 硬件条目 `kind` 三态:added / removed / changed;changed 的 `changes` 是逐字段差异
- `removed` 仅在 `agent.full_sync=true` 时产生(库中多出的条目候删)
- `old` / `new` 存完整条目,裁决详情可完整回看

### 5.3 身份键总表

| 数据 | 身份键 | 理由 |
|---|---|---|
| 设备 | `hostname` | OS 层面唯一;主机改名 = 新设备 + 旧设备残留(需手工删旧) |
| 网卡 | `name` | device 内唯一(eth0...),改名视为换卡 |
| 内存 / CPU | `slot` | 槽位物理固定(DIMM_A1 / CPU0),插拔同一槽可比对 |
| 硬盘 / 电源 | `serial_number` | 无稳定槽位,SN 是自然身份;换盘 = 旧删新增 |
| GPU | `uuid` | nvidia-smi UUID,稳定且跨机唯一 |

---

## 6. 设计理由汇总

| 决策 | 为什么 |
|---|---|
| 推送是唯一写入入口 | 数据来源单一,变更全部可追溯;人工操作(裁决/导入/UI 编辑)是辅助通道 |
| diff + 人工裁决而非自动覆盖 | 采集数据可能有误;字段级二选一 + 完整留痕,错误可回退(选 old) |
| 同设备一条 pending,新推送整体替换 | 避免同一设备 pending 堆积;裁决人始终面对最新视角,不处理过时差异 |
| 疑似下线动态计算不入库 | 阈值可在线改,动态计算永远一致;数据不自动删,恢复推送即恢复 active |
| `full_sync` 显式标记全量/增量 | 采集器可能只推部分硬件(采集失败/部分对接);由采集器声明语义,服务端不猜 |
| null 标量不清空库中数据 | 部分采集失败不应抹掉上次的有效值 |
| 身份为 null 的条目自动丢弃 | 没有身份的条目无法比对,存了是噪音 |
| CMDB 元数据与采集数据分离 | purpose 是人的录入,推送永不覆盖,两个来源互不踩 |
| 容量归一化列 `size_gb` | 原始值(size + unit)保真展示,归一化列便于排序、统计 |
| change_history 不设外键 | 设备硬删后历史保留,追溯独立于设备存活 |
| SQLite + WAL 单文件 | 内网运维场景设备量级小(百级),零运维、备份即拷文件;备份脚本已装 cron |
| 轻量迁移(ALTER TABLE)而非 Alembic | 表结构变化低频,SQLite 单文件场景下 Alembic 是过度设计 |
| 会话用 HMAC 签名 cookie 而非服务端 session | 无状态、无额外表;改密钥即全员下线;角色实时查库,变更即时生效 |

---

## 7. 设计合理性评审

### 7.1 合理的部分

1. **推送容错语义与真实采集器对齐**:null 身份丢弃、null 标量不清空、时间戳兜底——这些不是拍脑袋定的,是对着 iagent 的实际输出逐条确认的,联调零意外。
2. **三分支推送结果(created/unchanged/diff_created)**:采集器能感知推送效果,职责边界清晰。
3. **裁决幂等 + 全程留痕**:added/removed 幂等跳过、pending→applied/discarded 状态机、diff 存裁决时快照——重放、误操作都安全。
4. **身份键的选择贴合硬件物理现实**:内存/CPU 用槽位、硬盘/电源用 SN、GPU 用 UUID,各自的"同身份变化 = changed"语义都站得住。
5. **性能意识到位**:列表子表每类一次 IN 查询(避免 N+1)、count 用聚合、status 在 SQL 层筛选、排序字段白名单防注入、hostname 唯一索引。
6. **鉴权模型简单够用**:两级角色 + 实时查库,推送开放但有裁决把关兜底。

### 7.2 潜在问题与改进方向(按影响排序)

1. **伪造推送无门槛(中等,安全)**:POST /devices 默认开放意味着内网任何人可向 CMDB 灌假设备、伪造 diff。裁决虽有人工把关,但假设备会污染列表与统计。**已改进**:v2.3 引入 API 密钥(`X-API-Key` + 系统设置开关),开启后推送必须带有效密钥,密钥 = 推送 + 只读,泄露破坏面可控;默认关闭保证零破坏。
2. **SQLite 单写者,推送并发受限(低,当前量级无感)**:WAL 缓解了读写互斥,但写仍串行。数百台设备每几分钟推一次,绰绰有余;上千台高频推送时需要换 PostgreSQL(架构上 SQLModel 迁移成本可控,但 JSON 列查询、迁移脚本都要重写)。
3. **主机改名产生孤儿设备(低,已有兜底)**:hostname 是匹配键,改名 = 新设备 + 旧设备残留(疑似下线会暴露它),需手工删旧。自动合并有误判风险(两台设备恰好前后接同一 hostname),当前"暴露 + 手工删"是务实选择;改进方向是 UI 上一键"合并到新设备"。
4. **pending 无分页(低)**:`GET /pending-changes` 全量返回;设备量级小 + 同设备只一条 pending,列表不会爆炸,但极端情况(大量设备同时变更)可加分页。
5. **CSV 导入与推送存在竞态(极低)**:导入是逐行处理非原子(每行独立 ingest),与并发推送可能交错;单管理员操作场景几乎不会遇到。
6. **审计日志不可变但无导出(低)**:仅 admin 可查、limit 最大 1000;如需合规留存可加导出或写入外部日志。
7. **仪表盘全量加载设备(极低)**:统计在 Python 层逐台算 status;百级设备无感,量大后应在 SQL 层聚合。

### 7.3 结论

当前设计在"内网运维、百级设备、单人/少量管理员"的目标场景下是**合理且自洽**的:每一处取舍(动态 status、一条 pending、轻量迁移、SQLite)都与场景匹配,没有明显的过度设计;容错语义与采集器的对齐是这套系统联调顺畅的关键。最值得投入的一项改进——**采集 token**——已于 v2.3 以 API 密钥的形式落地(低成本堵住伪造推送),其余问题在量级上升前都可以不动。
