# CMDB v2

CMDB(CMDB v2)—— 采集推送、字段级 diff 冲突裁决、存储与展示。

链路:采集(外部 shell)→ JSON → CMDB API → CMDB 存储 → UI 展示。系统只管存储和查询,不做采集。

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

## 测试

```bash
uv run pytest tests/ -v
```

## 文档

- API 使用文档:[docs/API.md](docs/API.md)
- 设计与实施计划:[docs/PLAN.md](docs/PLAN.md)
