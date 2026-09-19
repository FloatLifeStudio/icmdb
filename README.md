# CMDB v2

CMDB(CMDB v2)—— 采集推送、字段级 diff 冲突裁决、存储与展示。

链路:采集(外部 shell)→ JSON → CMDB API → CMDB 存储 → UI 展示。系统只管存储和查询,不做采集。

## 设计决策

已逐项确认的核心取舍:

- **设备标识**:hostname(唯一匹配键;主机改名 = 新设备 + 旧设备残留,需手工删旧)
- **推送格式**:`agent` / `os` / `mgmt` / `hardware` 四段结构(v2.2);对齐 iagent 采集器实采语义(v2.3):身份字段可空、身份为 null 的条目自动丢弃、`mgmt` / `hardware` / `ips` 可为 null;仅含顶层 hostname 的旧格式自动归一化兼容
- **nics 语义**:推送体显式标记全量(`agent.full_sync=true`,库中多出的进 diff 候删)/ 增量(只存推送的)
- **冲突裁决**:字段级 diff;同设备已有 pending 时以最新一次推送重算 diff 整体替换(不累计);裁决生效后写 change_history
- **硬件扩展**:网卡(`name` 为身份)、内存/CPU(`slot` 为身份)、硬盘/电源(`serial_number` 为身份)、GPU(`uuid` 为身份);OS 含虚拟化类型 `os.virt`;字段可选,不推不更新对应类别
- **疑似下线**:查询时动态计算,默认 1 天(24 小时)阈值,系统设置页可在线修改(`CMDB_OFFLINE_THRESHOLD_DAYS` 仅作初始默认值),数据不自动删
- **写入权限**:推送 API 为唯一数据写入入口;UI 支持裁决、删除、标签、CSV 导入等管理操作
- **设备元数据**:位置/负责人/用途为 CMDB 元数据(UI 编辑、CSV 导入导出、推送不改)
- **操作审计**:删除/裁决/标签/元数据/用户管理/系统设置等管理操作自动记录审计日志,UI 仅 admin 可查
- **用户与角色**:admin(可操作)/ viewer(只可查看)两级角色,admin 可管理用户、重置密码;所有用户可改自己密码;推送接口默认不鉴权,采集器无需改造
- **API 密钥**:命名密钥(`cmdb_` 前缀,可随时查看/复制/吊销),admin 管理;系统设置开启后推送必须带密钥(请求头 `X-API-Key`),密钥 = 推送 + 只读,堵住伪造推送
- **删除语义**:DELETE 硬删设备与网卡、内存、CPU、硬盘、电源、GPU 数据,change_history 保留(追溯价值)

## 技术栈

- 后端:Python FastAPI + SQLite(SQLModel ORM)
- 前端:Vue 3 + TS + Element Plus(构建产物由 FastAPI 托管,单服务单端口)

## 快速开始

```bash
# 后端(首次先 uv sync 装依赖)
uv sync
uv run uvicorn cmdb.main:app --port 8080

# 前端 dev(另开终端,/api 代理到 8080)
cd web/frontend && npm install && npm run dev
```

生产部署:前端 `npm run build` 后产物输出到 `src/cmdb/static`,由 FastAPI 托管,
只需启动后端一个服务。

数据库备份:`scripts/backup_db.py` 用 `VACUUM INTO` 生成一致性快照到 `backups/`,
保留最近 14 份,可挂 cron 每日执行:

```cron
40 2 * * * /usr/bin/python3 /home/fs/icmdb/backup_db.py >> /home/fs/icmdb/backups/backup.log 2>&1
```

## 测试

```bash
uv run pytest tests/ -v
```

## 配置项(环境变量)

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `CMDB_DB_PATH` | `cmdb.db` | SQLite 数据库文件路径 |
| `CMDB_OFFLINE_THRESHOLD_DAYS` | `1` | 疑似下线阈值(天),仅作系统设置的初始默认值 |
| `CMDB_STATIC_DIR` | `src/cmdb/static` | 前端构建产物目录 |
| `CMDB_ADMIN_USER` | `admin` | 登录用户名 |
| `CMDB_ADMIN_PASSWORD` | `admin` | 登录密码 |
| `CMDB_SECRET_KEY` | `cmdb-session-secret` | 会话 cookie 签名密钥 |
| `CMDB_SESSION_EXPIRE_DAYS` | `7` | 会话有效期(天) |

## 文档

- English documentation: [README.en.md](README.en.md) / [docs/en/](docs/en/)
- 全景文档(数据库/接口/推送 JSON 详解与设计评审):[docs/OVERVIEW.md](docs/OVERVIEW.md)
- API 使用文档:[docs/API.md](docs/API.md)
- 示例数据文档:[docs/EXAMPLE.md](docs/EXAMPLE.md)
- 更新日志:[CHANGELOG.md](CHANGELOG.md)
