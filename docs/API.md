# CMDB API 使用文档

> Base URL: `http://<host>:8080/api/v1`
> 响应格式:REST 风格,HTTP 状态码 + JSON body
> 采集推送(POST /devices)是唯一的数据写入入口,**且不要求登录**(采集器无需改造)
> 其余 API 要求登录(会话 cookie),登录接口见[用户登录](#8-用户登录)
> 权限:admin 可操作(裁决/删除/标签/CSV 导入/用户管理),viewer 只可查看,写操作返回 403
> 时间戳:响应中的时间统一为 naive UTC(无时区后缀),客户端应按 UTC 解析后
> 转换为查看者本地时区显示,如 JS:`new Date(ts + 'Z')`
> 完整推送示例见 [EXAMPLE.md](./EXAMPLE.md)

## 目录

- [采集推送](#1-采集推送)——采集器唯一需要对接的接口
- [设备列表 / 详情 / 删除](#2-设备)
- [待裁决](#3-冲突待裁决)
- [变更历史](#4-变更历史)
- [仪表盘](#5-仪表盘)
- [设备扩展接口](#6-设备扩展接口)
- [错误码](#7-错误码)
- [用户登录](#8-用户登录)
- [用户管理](#9-用户管理)

---

## 1. 采集推送

### `POST /api/v1/devices`

采集器推送设备数据。按 hostname 匹配,三种结果:

| result | 含义 | 后续行为 |
|---|---|---|
| `created` | 库中无该 hostname | 创建设备 + 网卡 + IP |
| `unchanged` | 库中有且字段级无差异 | 仅刷新 last_pushed_at |
| `diff_created` | 库中有且有差异 | 差异进待裁决,**不动现有数据** |

**请求体**(v2.2 起:`agent` / `os` / `mgmt` / `hardware` 四段结构):

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
    "kernel": "5.15.0-91-generic",
    "virt": "bare_metal"
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
        }
      ]
    },
    "cpus": [
      {"slot": "CPU0", "model": "Intel(R) Xeon(R) Gold 6448Y"},
      {"slot": "CPU1", "model": "Intel(R) Xeon(R) Gold 6448Y"}
    ],
    "disks": [
      {"serial_number": "123123123", "type": "SSD", "manufacturer": "Samsung",
       "model": "990EVO", "size": 8, "size_unit": "TB"},
      {"serial_number": "123456", "type": "HDD", "manufacturer": "HGST",
       "model": "HUH728080ALE604", "size": 8, "size_unit": "TB"}
    ],
    "psus": [
      {"serial_number": "2P0123123132", "manufacturer": "GreatWall",
       "model": "CRPS2700D2", "max_power_w": 2700}
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
        }
      ]
    }
  }
}
```

**字段说明**:

| 字段 | 必填 | 说明 |
|---|---|---|
| `agent` | ❌ | 采集器信息,默认全缺省 |
| `agent.version` | ❌ | 采集器版本,写入设备详情 |
| `agent.source` | ❌ | 来源标识,写入待裁决记录与变更历史 |
| `agent.timestamp` | ❌ | 采集时间 ISO 8601(带时区,会归一化为 UTC);缺省用服务器接收时间 |
| `agent.full_sync` | ❌ | 默认 **true**。**true = 全量同步**:库中多出的硬件条目进 diff 候删;false = 增量:库中多出的保持不动 |
| `os.hostname` | ✅ | 设备唯一匹配键;主机改名 = 新设备 |
| `os.type` / `os.version` / `os.kernel` / `os.virt` | ❌ | OS 类型 / 版本 / 内核 / 虚拟化类型(bare_metal/kvm/vmware/qemu/xen...);未采集(None)不清空库中已有值 |
| `mgmt` | ❌ | 管理口信息:mac / ip / prefix_length |
| `hardware.chassis_serial_number` | ❌ | 机箱序列号;未采集不清空库中已有值 |
| `hardware.nics` | ❌ | 网卡数组,推多少收多少;`name` 是网卡身份 |
| `hardware.memory` | ❌ | 内存信息:`slots` 数组,`slot` 是身份;字段含 manufacturer / part_number / type(代数)/ size + size_unit(理论容量,GB 或 TB)/ speed_mts(MT/s)/ serial_number |
| `hardware.cpus` | ❌ | CPU 数组,`slot` 是身份;字段含 model(型号) |
| `hardware.disks` | ❌ | 硬盘数组,`serial_number` 是身份;字段含 type(SSD/HDD)/ manufacturer / model / size + size_unit(理论容量) |
| `hardware.psus` | ❌ | 电源数组,`serial_number` 是身份;字段含 manufacturer / model / max_power_w(最大功率 W) |
| `hardware.gpu` | ❌ | GPU 信息:`slots` 数组,`uuid` 是身份;字段含 name / serial_number / size + size_unit(显存)/ driver_version / pcie_id |

**对齐 iagent 采集器实采语义**(v2.3 起):

- 身份字段(网卡 `name` 之外的 slot / uuid / serial_number)可为 null:单字段采集
  失败置 null,**身份为 null 的整条条目自动丢弃**,不进 diff 与存储,不影响整包接收
- `mgmt` / `hardware` 可为 null:视为未采集,不清空库中已有数据
- `nics[].ips` 可为 null:无 IP 网卡不发 IP
- `agent.timestamp` 空串视为未采集,用服务器接收时间兜底

**兼容旧格式**:仅含顶层 `hostname` 的旧版推送体仍可接收,服务端自动归一化为
新结构(旧 `serial_number` → `hardware.chassis_serial_number`,旧顶层
`timestamp` / `full_sync` / `source` → `agent.*`,旧内存 `size_gb` →
`size` + `GB`)。新采集器一律推新格式。

**curl 示例**:

```bash
curl -X POST http://192.168.201.18:8080/api/v1/devices \
  -H "Content-Type: application/json" \
  -d @collector.json
```

**响应**:

```json
{"result": "created", "device_id": 1, "pending_change_id": null}
```

`diff_created` 时 `pending_change_id` 为待裁决记录 id,可据此在 UI 或通过 API 裁决。

**冲突合并**:同一设备已有一条待裁决、还没处理,又来一次冲突推送时,以**最新一次
推送为准**整体重算 diff 并替换进同一条,不与旧差异累计;不会堆积多条。

---

## 2. 设备

### `GET /api/v1/devices` — 设备列表

**查询参数**:

| 参数 | 默认 | 说明 |
|---|---|---|
| `page` | 1 | 页码 |
| `page_size` | 20 | 每页数量 |
| `search` | - | 模糊搜索,覆盖 hostname / serial_number / mgmt_ip / 网卡业务 IP(反查) |
| `status` | - | `active` / `suspected_offline`,按推送阈值在 SQL 层筛选 |
| `tag` | - | 按标签精确匹配 |
| `sort_by` | - | 排序字段,白名单:`hostname` / `serial_number` / `mgmt_ip` / `last_pushed_at` |
| `sort_order` | `asc` | `asc` / `desc` |

```bash
curl "http://192.168.201.18:8080/api/v1/devices?page=1&search=S1A&status=active"
```

**响应**:

```json
{
  "total": 1,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 1,
      "hostname": "S1A01DC-VL101",
      "serial_number": "PF4ABC123456",
      "mgmt_mac": "AA:BB:CC:DD:EE:01",
      "mgmt_ip": "192.168.10.101",
      "mgmt_prefix_length": 24,
      "last_pushed_at": "2026-09-11T08:43:39",
      "created_at": "2026-09-11T08:43:39",
      "updated_at": "2026-09-11T08:43:39",
      "status": "active",
      "nics": [
        {
          "id": 1,
          "name": "eth0",
          "mac": "AA:BB:CC:DD:EE:02",
          "ips": [{"id": 1, "ip": "10.10.1.101", "prefix_length": 24}]
        }
      ]
    }
  ]
}
```

`status` 动态计算:超阈值(默认 3 天,`CMDB_OFFLINE_THRESHOLD_DAYS` 可配)未推送
标记 `suspected_offline`,数据不自动删。

### `GET /api/v1/devices/{id}` — 设备详情

响应结构同列表项。设备不存在返回 404。

### `DELETE /api/v1/devices/{id}` — 手工删除

硬删设备与网卡、内存、CPU、硬盘、电源、GPU 数据(待裁决记录连带删除);**变更历史保留**。成功返回 204。

```bash
curl -X DELETE http://192.168.201.18:8080/api/v1/devices/1
```

---

## 3. 冲突待裁决

### `GET /api/v1/pending-changes` — 待裁决列表

**查询参数**:`status` 默认 `pending`;`all` 可看含已处理(applied / discarded)的全量。

```bash
curl "http://192.168.201.18:8080/api/v1/pending-changes"
```

**响应**(`diff` 为字段级差异清单):

```json
{
  "items": [
    {
      "id": 1,
      "device_id": 1,
      "source": "collector",
      "payload": {"...": "推送原始 JSON,结构同 POST /devices 请求体"},
      "diff": {
        "fields": [
          {"field": "mgmt.ip", "old": "192.168.10.101", "new": "192.168.10.200"}
        ],
        "nics": [
          {
            "name": "eth1",
            "kind": "removed",
            "changes": [],
            "old": {"name": "eth1", "mac": "AA:BB:CC:DD:EE:03",
                    "ips": [{"ip": "10.10.2.101", "prefix_length": 24}]},
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

`nics` 条目的 `kind`:

| kind | 含义 |
|---|---|
| `added` | 推送里有、库里没有(新网卡) |
| `removed` | full_sync=true 时库里多出的(候删) |
| `changed` | 同名网卡的 mac 或 ips 有变化,`changes` 数组逐条列出 |

`memory` / `cpus` 条目结构同上(`slot` 为身份),`kind` 含义一致。`disks` / `psus` 条目结构同上(`serial_number` 为身份),`gpus` 条目结构同上(`uuid` 为身份)。

### `GET /api/v1/pending-changes/{id}` — diff 详情

返回单条记录(payload + diff)。

### `POST /api/v1/pending-changes/{id}/resolve` — 裁决

逐条目选择 `new`(采用新数据)或 `old`(保留现状)。对 `removed` 网卡,
`new` 即删除该网卡。

**请求体**:

```json
{
  "field_choices": {"mgmt.ip": "new"},
  "nic_choices": {"eth1": "new", "eth2": "old"},
  "memory_choices": {"DIMM_A1": "new"},
  "cpu_choices": {"CPU0": "new"},
  "disk_choices": {"123123123": "new"},
  "psu_choices": {"2P0123123132": "new"},
  "gpu_choices": {"GPU-3f2a1b9c": "new"}
}
```

| 字段 | 说明 |
|---|---|
| `field_choices` | 主机字段:字段路径 -> `new` / `old` |
| `nic_choices` | 网卡条目:网卡名 -> `new` / `old` |
| `memory_choices` | 内存槽位条目:槽位名 -> `new` / `old` |
| `cpu_choices` | CPU 槽位条目:槽位名 -> `new` / `old` |
| `disk_choices` | 硬盘条目:SN -> `new` / `old` |
| `psu_choices` | 电源条目:SN -> `new` / `old` |
| `gpu_choices` | GPU 条目:UUID -> `new` / `old` |

**响应**:

```json
{
  "applied": ["mgmt.ip: 192.168.10.101 -> 192.168.10.200", "网卡 eth1 删除"],
  "pending_id": 1,
  "status": "applied"
}
```

裁决生效后写变更历史;全部选 `old` 时无实际改动,仅标记 applied。
已处理的记录重复裁决返回 409。

---

## 4. 变更历史

### `GET /api/v1/change-history`

**查询参数**:`device_id` 可选,按设备过滤。设备硬删后其历史仍可查。

```bash
curl "http://192.168.201.18:8080/api/v1/change-history?device_id=1"
```

**响应**:

```json
{
  "items": [
    {
      "id": 1,
      "device_id": 1,
      "summary": "mgmt.ip: 192.168.10.101 -> 192.168.10.200; 网卡 eth1 删除",
      "source": "collector",
      "diff": {"...": "裁决时的完整差异清单,结构同待裁决 diff"},
      "created_at": "2026-09-11T08:43:57"
    }
  ]
}
```

### `GET /api/v1/change-history/{id}` — 变更详情

含裁决时的完整 diff。

---

## 5. 仪表盘

### `GET /api/v1/dashboard`

资产概览统计:总数、活跃/疑似下线、待裁决数、最近 10 条变更。

```bash
curl "http://192.168.201.18:8080/api/v1/dashboard"
```

```json
{
  "total_devices": 150,
  "active": 61,
  "suspected_offline": 89,
  "pending_changes": 1,
  "recent_changes": ["...最近 10 条变更,条目结构同变更历史(含 summary / diff)..."]
}
```

---

## 6. 设备扩展接口

### `GET /api/v1/devices/export/csv` — 导出 CSV

导出全部设备,UTF-8 BOM(Excel 中文兼容)。`Content-Disposition: attachment`。

### `POST /api/v1/devices/import/csv` — CSV 导入

`multipart/form-data` 上传,字段名 `file`,行格式与导出一致(可直接回导)。

```bash
curl -X POST http://192.168.201.18:8080/api/v1/devices/import/csv \
  -F "file=@devices.csv"
```

**行为**:逐行走与推送相同的清洗逻辑(hostname 匹配、diff 进待裁决),
`source` 标记为 `csv_import`;标签随导入设置;不触碰 `last_pushed_at`
(回导不会倒退最后推送时间)。

```json
{"created": 1, "unchanged": 0, "diff_created": 0, "errors": []}
```

`errors` 为解析失败(缺 hostname 等)的行说明,不影响其余行导入。

### `PUT /api/v1/devices/{id}/tags` — 更新标签

```json
{"tags": ["生产", "web"]}
```

全量替换;标签为 CMDB 元数据,不属于采集数据。

### `POST /api/v1/devices/batch-delete` — 批量删除

```json
{"ids": [1, 2, 3]}
```

行为同单个删除(硬删,历史保留);返回 `{"deleted": [实际删除的 id]}`。

**列表搜索增强**:`search` 同时覆盖 hostname / serial_number / mgmt_ip /
网卡业务 IP(按 IP 反查设备);`tag` 参数按标签精确匹配。

---

## 7. 错误码

| 状态码 | 场景 |
|---|---|
| 401 | 未登录或密码错误(推送接口除外) |
| 404 | 设备 / 待裁决记录不存在 |
| 409 | 待裁决记录已被处理过,重复裁决 |
| 422 | 请求体校验失败(如缺 hostname) |

错误响应:`{"detail": "..."}`(FastAPI 校验错误为 `{"detail": [...]}`)。

## 8. 用户登录

用户账号存 users 表(PBKDF2 哈希),首个 admin 账号由 `CMDB_ADMIN_USER` /
`CMDB_ADMIN_PASSWORD`(默认 `admin` / `admin`)在首次启动时种子创建。
登录后签发 HttpOnly 会话 cookie(HMAC 签名,默认 7 天,
`CMDB_SESSION_EXPIRE_DAYS` 可配),后续请求自动携带。

**登录范围**:仅 UI 及其调用的 API;`POST /api/v1/devices`(采集推送)保持开放。

### `POST /api/v1/auth/login`

```json
{"username": "admin", "password": "admin"}
```

成功返回 `{"username": "admin"}` 并设置会话 cookie;失败返回 401。

### `POST /api/v1/auth/logout`

清除会话 cookie,返回 `{"ok": true}`。

### `POST /api/v1/auth/change-password`

当前登录用户修改自己的密码(需验证原密码),所有角色可用:

```json
{"old_password": "原密码", "new_password": "新密码"}
```

原密码错误返回 401。

### `GET /api/v1/auth/me`

返回当前登录用户与角色 `{"username": "admin", "role": "admin"}`;未登录返回 401
(UI 用它判断会话状态)。

## 9. 用户管理

仅 admin 可访问(其他用户返回 403)。角色两级:`admin`(可操作)与 `viewer`(只可查看)。
首个 admin 账号由 `CMDB_ADMIN_USER` / `CMDB_ADMIN_PASSWORD` 在首次启动时种子创建;
角色变更即时生效(无需重新登录)。

### `GET /api/v1/users`

返回全部用户:`{"items": [{"id": 1, "username": "admin", "role": "admin", "created_at": "..."}]}`

### `POST /api/v1/users`

```json
{"username": "ops1", "password": "初始密码", "role": "viewer"}
```

`role` 只能是 `admin` / `viewer`(默认 viewer);用户名重复返回 409。

### `PUT /api/v1/users/{id}` — 重置密码 / 修改角色

```json
{"password": "新密码"}
```

`password` 与 `role` 均可选,传哪个改哪个;不能降级最后一个管理员(409)。

### `DELETE /api/v1/users/{id}` — 删除用户

不能删除自己与最后一个管理员(409)。

**权限矩阵**:

| 操作 | admin | viewer |
|---|---|---|
| 采集推送(POST /devices,无需登录) | ✅ | ✅ |
| 查看列表 / 详情 / 历史 / 仪表盘 | ✅ | ✅ |
| 裁决 / 删除设备 / 批量删除 | ✅ | ❌ 403 |
| 编辑标签 / CSV 导入 | ✅ | ❌ |
| 用户管理 | ✅ | ❌ |

## 附:配置项(环境变量)

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `CMDB_DB_PATH` | `cmdb.db` | SQLite 数据库文件路径 |
| `CMDB_OFFLINE_THRESHOLD_DAYS` | `3` | 疑似下线阈值(天) |
| `CMDB_STATIC_DIR` | `src/cmdb/static` | 前端构建产物目录 |
| `CMDB_ADMIN_USER` | `admin` | 登录用户名 |
| `CMDB_ADMIN_PASSWORD` | `admin` | 登录密码 |
| `CMDB_SECRET_KEY` | `cmdb-session-secret` | 会话 cookie 签名密钥 |
| `CMDB_SESSION_EXPIRE_DAYS` | `7` | 会话有效期(天) |
