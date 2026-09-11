# CMDB API 使用文档

> Base URL: `http://<host>:8080/api/v1`
> 响应格式:REST 风格,HTTP 状态码 + JSON body,无鉴权
> 采集推送(POST /devices)是唯一的数据写入入口
> 时间戳:响应中的时间统一为 naive UTC(无时区后缀),客户端应按 UTC 解析后
> 转换为查看者本地时区显示,如 JS:`new Date(ts + 'Z')`

## 目录

- [采集推送](#1-采集推送)——采集器唯一需要对接的接口
- [设备列表 / 详情 / 删除](#2-设备)
- [待裁决](#3-冲突待裁决)
- [变更历史](#4-变更历史)
- [错误码](#5-错误码)

---

## 1. 采集推送

### `POST /api/v1/devices`

采集器推送设备数据。按 hostname 匹配,三种结果:

| result | 含义 | 后续行为 |
|---|---|---|
| `created` | 库中无该 hostname | 创建设备 + 网卡 + IP |
| `unchanged` | 库中有且字段级无差异 | 仅刷新 last_pushed_at |
| `diff_created` | 库中有且有差异 | 差异进待裁决,**不动现有数据** |

**请求体**:

```json
{
  "hostname": "S1A01DC-VL101",
  "serial_number": "PF4ABC123456",
  "mgmt": {
    "mac": "AA:BB:CC:DD:EE:01",
    "ip": "192.168.10.101",
    "prefix_length": 24
  },
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
  "timestamp": "2026-09-11T15:30:00+08:00",
  "full_sync": true,
  "source": "collector"
}
```

**字段说明**:

| 字段 | 必填 | 说明 |
|---|---|---|
| `hostname` | ✅ | 设备唯一匹配键;主机改名 = 新设备 |
| `serial_number` | ❌ | 序列号;未采集(None)不清空库中已有值 |
| `mgmt` | ❌ | 管理口信息:mac / ip / prefix_length |
| `nics` | ❌ | 网卡数组,推多少收多少;`name` 是网卡身份 |
| `timestamp` | ❌ | 采集时间 ISO 8601(带时区,会归一化为 UTC);缺省用服务器接收时间 |
| `full_sync` | ❌ | 默认 false。**true = 全量同步**:库中多出的网卡进 diff 候删;false = 增量:库中多出的网卡保持不动 |
| `source` | ❌ | 来源标识,写入待裁决记录与变更历史 |

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

**冲突合并**:同一设备已有一条待裁决、还没处理,又来一次冲突推送时,新差异
**合并进同一条**(同字段以最新推送为准),不会堆积多条。

---

## 2. 设备

### `GET /api/v1/devices` — 设备列表

**查询参数**:

| 参数 | 默认 | 说明 |
|---|---|---|
| `page` | 1 | 页码 |
| `page_size` | 20 | 每页数量 |
| `search` | - | hostname 模糊搜索 |
| `status` | - | `active` / `suspected_offline`,按推送阈值在 SQL 层筛选 |

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

硬删设备与网卡数据(IP、待裁决记录连带删除);**变更历史保留**。成功返回 204。

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

### `GET /api/v1/pending-changes/{id}` — diff 详情

返回单条记录(payload + diff)。

### `POST /api/v1/pending-changes/{id}/resolve` — 裁决

逐条目选择 `new`(采用新数据)或 `old`(保留现状)。对 `removed` 网卡,
`new` 即删除该网卡。

**请求体**:

```json
{
  "field_choices": {"mgmt.ip": "new"},
  "nic_choices": {"eth1": "new", "eth2": "old"}
}
```

| 字段 | 说明 |
|---|---|
| `field_choices` | 主机字段:字段路径 -> `new` / `old` |
| `nic_choices` | 网卡条目:网卡名 -> `new` / `old` |

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
      "created_at": "2026-09-11T08:43:57"
    }
  ]
}
```

---

## 5. 错误码

| 状态码 | 场景 |
|---|---|
| 422 | 请求体校验失败(如缺 hostname) |
| 404 | 设备 / 待裁决记录不存在 |
| 409 | 待裁决记录已被处理过,重复裁决 |

错误响应:`{"detail": "..."}`(FastAPI 校验错误为 `{"detail": [...]}`)。

## 附:配置项(环境变量)

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `CMDB_DB_PATH` | `cmdb.db` | SQLite 数据库文件路径 |
| `CMDB_OFFLINE_THRESHOLD_DAYS` | `3` | 疑似下线阈值(天) |
| `CMDB_STATIC_DIR` | `src/cmdb/static` | 前端构建产物目录 |
