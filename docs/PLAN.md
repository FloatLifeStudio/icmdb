# CMDB 实施计划

> 采集链路 外部客户端采集→ JSON → CMDB API → CMDB 存储 → UI 展示

## 1. 背景与目标

在 `/data/icmdb` 从零实现 CMDB v2。数据由外部采集程序推送 JSON 到 CMDB API,CMDB
负责数据清洗(字段级 diff 冲突裁决)、存储,UI 负责展示与裁决。系统只管存储和查询,
不做采集。

已逐项确认的设计决策:

- **技术栈**:Python FastAPI + SQLite(SQLModel ORM)+ Vue 3 + TS + Element Plus,
  前端构建产物由 FastAPI 托管,部署时单服务单端口;Python 环境用 uv(本机无 pip)
- **设备标识**:hostname(唯一匹配键;主机改名 = 新设备 + 旧设备残留,需手工删旧,
  已接受该取舍)
- **nics 语义**:推送体显式标记全量(`full_sync=true`,库中多出的网卡进 diff 候删)/
  增量(只存推送的)
- **冲突裁决**:字段级 diff;同设备已有 pending 时新推送**合并进同一条**;
  裁决生效后写 change_history
- **疑似下线**:查询时动态计算,超阈值(可配置,默认 3 天)未推送标记,数据不自动删
- **UI 写入权限**:推送 API 为唯一数据写入入口,UI 只读 + 裁决
- **删除语义**:DELETE 硬删设备与网卡数据,change_history 保留(追溯价值)

## 2. 数据模型(SQLite,5 张表)

```
devices            主机主表
├─ id, hostname(唯一), serial_number
├─ mgmt_mac, mgmt_ip, mgmt_prefix_length
├─ last_pushed_at(取推送体 timestamp,缺省用服务器接收时间)
└─ created_at, updated_at

nics               网卡表
├─ id, device_id(FK), name, mac
└─ 唯一约束 (device_id, name)

nic_ips            IP 表
├─ id, nic_id(FK), ip, prefix_length
└─ 唯一约束 (nic_id, ip)

pending_changes    冲突待裁决(同设备合并为一条)
├─ id, device_id(FK), source
├─ payload(推送原始 JSON), diff(字段级差异清单 JSON)
├─ status(pending / applied / discarded)
└─ created_at, resolved_at

change_history     变更流水(仅记录裁决生效的改动)
└─ id, device_id(FK), summary, source, created_at
```

## 3. 目录结构(标准 Python 项目布局)

```
/data/icmdb/
├── pyproject.toml              # uv 管理;依赖:fastapi, uvicorn, sqlmodel, pydantic;
│                               # dev 组:pytest, httpx
├── README.md
├── docs/
│   └── PLAN.md                 # 本文档
├── src/
│   └── cmdb/
│       ├── __init__.py
│       ├── main.py             # FastAPI app 工厂 + /api 路由挂载 + 前端静态托管
│       ├── config.py           # 配置:DB 路径、下线阈值(默认 3 天)等,环境变量可覆盖
│       ├── database.py         # SQLite 连接、建表(WAL 模式)
│       ├── models.py           # SQLModel 表模型(5 张表)
│       ├── schemas.py          # Pydantic 推送体/响应模型(对应采集 JSON 结构)
│       ├── services/
│       │   ├── ingest.py       # 推送处理:hostname 匹配、创建/unchanged/diff 分支
│       │   ├── diff.py         # 字段级 diff:主机字段、网卡、IP、候删项
│       │   └── resolve.py      # 裁决应用:按字段选择新旧、写 change_history
│       └── api/
│           ├── devices.py      # POST 推送、GET 列表/详情、DELETE
│           └── pending_changes.py  # GET 列表/详情、POST resolve
├── tests/
│   ├── conftest.py             # 临时 SQLite 库 fixture + TestClient
│   ├── test_diff.py
│   ├── test_ingest.py          # 含真实采集示例 JSON 的端到端推送用例
│   └── test_resolve.py
└── web/
    └── frontend/               # Vue 3 + TS + Element Plus + Vue Router(Vite)
        ├── package.json
        ├── vite.config.ts      # dev 时 /api 代理到后端
        └── src/
            ├── main.ts
            ├── App.vue
            ├── api/index.ts    # API client 封装
            └── views/
                ├── DeviceList.vue        # 列表:状态、上次推送时间、搜索筛选
                ├── DeviceDetail.vue      # nics/IP、变更历史
                └── ConflictResolve.vue   # diff 新旧对照、逐字段裁决
```

前端构建产物输出到 `src/cmdb/static/`(gitignore),由 FastAPI StaticFiles 托管,
部署时单服务单端口。

## 4. 核心业务逻辑

1. **推送**(POST /api/v1/devices):
   body = 采集 JSON + `timestamp`(ISO 8601,缺省用服务器接收时间)+ `full_sync`
   (全量/增量标记)+ `source`(可选来源)

2. **hostname 匹配三分支**:
   - 不存在 → 创建设备+网卡+IP,返回 `created`
   - 存在且字段级无差异 → 刷新 last_pushed_at,返回 `unchanged`
   - 存在有差异 → 字段级 diff → 合并进该设备已有 pending 记录,不改现有数据,
     返回 `diff_created`

3. **full_sync=true**:库中多出的网卡进 diff,类型为"候删"

4. **裁决**(POST /pending-changes/{id}/resolve):body 为逐字段的取值选择
   (新值/旧值/候删保留);应用后更新设备数据、写 change_history、pending 标记 applied

5. **疑似下线**:列表/详情响应中动态计算 `status`(active / suspected_offline),
   阈值从 config 读

## 5. API 一览

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | /api/v1/devices | 采集推送(唯一数据写入入口) |
| GET | /api/v1/devices | 列表(分页/搜索/状态筛选) |
| GET | /api/v1/devices/{id} | 详情 |
| DELETE | /api/v1/devices/{id} | 手工删除设备 |
| GET | /api/v1/pending-changes | 待裁决列表 |
| GET | /api/v1/pending-changes/{id} | diff 详情 |
| POST | /api/v1/pending-changes/{id}/resolve | 裁决(逐字段选择) |

## 6. 实施步骤(git commit 按 Angular 规范 + gitmoji)

| # | Commit | 内容 |
|---|---|---|
| 1 | `🎉 chore: initialize project with design plan and gitignore` | git init、目录骨架、PLAN.md、.gitignore |
| 2 | `✨ feat: add sqlite models and pydantic schemas` | pyproject.toml、README.md、uv 环境;models.py、schemas.py、database.py、config.py |
| 3 | `✨ feat: implement field-level diff service` | services/diff.py + tests/test_diff.py |
| 4 | `✨ feat: implement ingest service with hostname matching` | services/ingest.py + tests/test_ingest.py(含真实采集示例 JSON) |
| 5 | `✨ feat: implement conflict resolve service` | services/resolve.py + tests/test_resolve.py |
| 6 | `✨ feat: add devices and pending-changes api` | api/ 两套路由、main.py 挂载 |
| 7 | `✨ feat: add vue 3 frontend with device list, detail and conflict views` | web/frontend 全部前端代码 |
| 8 | `📝 docs: update plan to match implementation` | 核对并更新 docs/PLAN.md,与最终实现对齐 |

每个 commit 前跑 `uv run pytest`,测试通过才提交。

## 7. 验证

1. **单测**:`uv run pytest tests/ -v` — 覆盖 diff、ingest 三分支、裁决应用
2. **端到端手测**:
   - `uv run uvicorn cmdb.main:app --port 8080` 启动后端
   - 用真实采集示例 JSON `curl -X POST localhost:8080/api/v1/devices` 推送 → 验证 `created`
   - 改动 hostname 外的字段(如 mgmt.ip)再推 → 验证 `diff_created`,且 GET 设备数据未变
   - 前端 dev 或 build 后由 FastAPI 托管,在裁决页做字段级选择 → 验证生效 + change_history 生成
   - 推 `full_sync=true` 少一块网卡的版本 → 验证候删 diff 出现
3. **回归**:确认 hostname 相同重复推送返回 `unchanged`,不重复建设备

## 8. 推送体示例(采集器 → CMDB API)

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

nics 数量不定(有四个网口也有两个),推多少收多少;`full_sync=true` 时库中多出的
网卡进候删 diff。
