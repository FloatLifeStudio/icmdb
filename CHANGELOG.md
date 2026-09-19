# Changelog

> English version: [docs/en/CHANGELOG.md](docs/en/CHANGELOG.md)
格式参考 [Keep a Changelog](https://keepachangelog.com/),版本号遵循语义化版本。

## Unreleased

### 新增

- **用户管理**:admin / viewer 两级角色(viewer 只可查看,写操作 403);
  admin 可创建 / 删除用户、重置密码、变更角色,最后一个管理员保护
- **修改自己密码**:`POST /api/v1/auth/change-password`,所有角色可用,需验证原密码
- **`os.virt` 虚拟化类型**:推送 / 存储 / diff / 设备详情 / CSV 全链路
  (bare_metal/kvm/vmware/qemu/xen...);旧库自动迁移补列

### 对齐

- **iagent 采集器实采语义**(`POST /api/v1/devices`):身份字段
  (slot / uuid / serial_number)可空,身份为 null 的条目自动丢弃;
  `mgmt` / `hardware` / `nics[].ips` 可为 null(未采集不清空库中数据);
  `agent.timestamp` 空串视为未采集,用服务器接收时间兜底

## v2.2.0 - 2026-09-13

### 新增

- **推送格式重设计**:`agent` / `os` / `mgmt` / `hardware` 四段结构
  (`agent`: version/source/timestamp/full_sync;`hardware`: chassis_serial_number +
  各硬件类别);仅含顶层 hostname 的旧格式服务端自动归一化兼容
- **GPU 支持**:新 GPU 表(`uuid` 为身份:名称/SN/显存/驱动版本/PCIe),
  推送、diff 裁决、存储、展示全链路覆盖;diff 条目补全整体 old/new
- **用户登录**:单管理员账号(env 配置)保护 UI 及其调用的 API;
  前端登录页 + 路由守卫;`POST /devices` 推送接口不鉴权,采集器无需改造
- **备份脚本**:`scripts/backup_db.py` 用 `VACUUM INTO` 生成一致性快照,保留 14 份,可挂 cron

### 优化

- **多次推送以最新为准**:同设备未裁决时以最新一次推送重算 diff 整体替换,不累计
- **冲突裁决两列对比**:硬件条目改为主机字段一致的旧值(库中)/新值(推送)两列
- 内存容量改 `size` + `size_unit`(JSON 对齐),内部归一化 `size_gb` 列;旧库自动迁移
- 标签规范化为 device_tag 表;列表查询 N+1 修复;搜索防抖;CSV 导入修复
- 示例数据改为高性能双路八卡 GPU 服务器常用配置(2× Xeon Platinum、16× 32GB DDR5、8× A800-80GB)

## v2.1.0 - 2026-09-13

### 新增

- **待裁决计数提示**:侧边栏"冲突裁决"显示待处理数量,裁决提交后即时刷新
- **首页变更内容**:按大类汇总显示(如 内存,CPU),行可点击展开完整差异明细

### 优化

- 删除过时的 PLAN.md,设计决策并入 README;新增 CHANGELOG
- EXAMPLE.md 字段说明去重,改为指向 API.md
- 前端 vendor chunk 拆分,主包 1MB -> 5.6kB

## v2.0.0 - 2026-09-13

CMDB v2 首个正式发布。从零实现:采集推送、字段级 diff 冲突裁决、存储与展示。

### 新增

- **采集推送**:唯一数据写入入口;hostname 匹配三分支(created / unchanged / diff_created),
  冲突合并,`full_sync` 全量/增量标记
- **硬件信息**:网卡、内存(槽位级:厂商/型号/代数/容量/频率/SN)、CPU(槽位 + 型号)、
  硬盘(SSD/HDD、品牌/型号/容量/SN)、电源(品牌/型号/最大功率/SN)
- **冲突裁决**:字段级 diff 新旧对照,逐条目选 new/old,裁决生效写变更历史
- **设备管理**:分页/搜索/标签筛选、状态(active / suspected_offline)动态计算、
  手工删除、批量删除、标签编辑
- **仪表盘**:资产总数、活跃/疑似下线、待裁决数、最近变更
- **CSV 导入导出**:UTF-8 BOM,Excel 中文兼容,可直接回导
- **前端**:Vue 3 + TS + Element Plus,设备列表/详情、冲突裁决、仪表盘;
  构建产物由 FastAPI 托管,单服务单端口
- **部署**:无鉴权 REST API,时间戳统一 naive UTC
