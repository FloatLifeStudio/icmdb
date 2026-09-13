# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/),版本号遵循语义化版本。

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
