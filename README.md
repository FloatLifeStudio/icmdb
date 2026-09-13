# CMDB v2

CMDB(CMDB v2)—— 采集推送、字段级 diff 冲突裁决、存储与展示。

链路:采集(外部 shell)→ JSON → CMDB API → CMDB 存储 → UI 展示。系统只管存储和查询,不做采集。

## 设计决策

已逐项确认的核心取舍:

- **设备标识**:hostname(唯一匹配键;主机改名 = 新设备 + 旧设备残留,需手工删旧)
- **nics 语义**:推送体显式标记全量(`full_sync=true`,库中多出的进 diff 候删)/ 增量(只存推送的)
- **冲突裁决**:字段级 diff;同设备已有 pending 时新推送合并进同一条;裁决生效后写 change_history
- **硬件扩展**:网卡(`name` 为身份)、内存/CPU(`slot` 为身份)、硬盘/电源(`serial_number` 为身份);字段可选,不推不更新对应类别
- **疑似下线**:查询时动态计算,默认 3 天阈值(`CMDB_OFFLINE_THRESHOLD_DAYS` 可配),数据不自动删
- **UI 写入权限**:推送 API 为唯一数据写入入口,UI 只读 + 裁决
- **删除语义**:DELETE 硬删设备与网卡数据,change_history 保留(追溯价值)

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
| `CMDB_OFFLINE_THRESHOLD_DAYS` | `3` | 疑似下线阈值(天) |
| `CMDB_STATIC_DIR` | `src/cmdb/static` | 前端构建产物目录 |

## 文档

- API 使用文档:[docs/API.md](docs/API.md)
- 示例数据文档:[docs/EXAMPLE.md](docs/EXAMPLE.md)
- 更新日志:[CHANGELOG.md](CHANGELOG.md)
