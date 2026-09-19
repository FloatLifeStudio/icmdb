// diff 展示共享工具:字段中文映射、值格式化
// 被 ConflictResolve / DiffEntry / DiffDetail 使用

// 字段路径 -> 人类可读名称(主机字段带路径,硬件条目字段为裸键)
const FIELD_LABELS: Record<string, string> = {
  // 主机字段
  hostname: '主机名',
  'hardware.chassis_serial_number': '序列号',
  serial_number: '序列号',
  'os.type': 'OS 类型',
  'os.version': 'OS 版本',
  'os.kernel': '内核',
  'os.virt': '虚拟化',
  'mgmt.mac': '管理 MAC',
  'mgmt.ip': '管理 IP',
  'mgmt.prefix_length': '子网前缀',
  // 网卡条目
  name: '网卡',
  mac: 'MAC',
  ips: 'IP 列表',
  // 内存条目
  slot: '槽位',
  manufacturer: '厂商',
  part_number: '型号颗粒',
  type: '类型',
  size: '容量',
  size_unit: '容量单位',
  speed_mts: '频率',
  // CPU / 硬盘 / 电源条目
  model: '型号',
  max_power_w: '最大功率',
  // GPU 条目
  uuid: 'UUID',
  driver_version: '驱动版本',
  pcie_id: 'PCIe',
}

export function fieldLabel(f: string): string {
  return FIELD_LABELS[f] ?? f
}

// IP 列表值: [{ip, prefix_length}] -> "10.0.0.1/24, 10.0.0.2"
function fmtIps(v: unknown): string {
  const list = (v as { ip: string; prefix_length: number | null }[] | null) || []
  return list.length
    ? list.map((i) => i.ip + (i.prefix_length ? '/' + i.prefix_length : '')).join(', ')
    : '无'
}

// 单值格式化:diff 行的旧值/新值展示
export function fmtValue(field: string, v: unknown): string {
  if (v === null || v === undefined || v === '') return '-'
  if (field === 'ips') return fmtIps(v)
  return String(v)
}

// added/removed 条目的完整对象 -> 键值行(跳过空值,size_unit 并入 size)
export function fullRows(obj: Record<string, unknown> | null): { key: string; label: string; value: string }[] {
  if (!obj) return []
  const rows: { key: string; label: string; value: string }[] = []
  for (const [k, v] of Object.entries(obj)) {
    if (v === null || v === undefined || v === '') continue
    if (k === 'size_unit') continue // 并入容量展示
    if (k === 'size') {
      rows.push({ key: k, label: fieldLabel(k), value: `${v}${obj.size_unit ?? ''}` })
      continue
    }
    if (Array.isArray(v) && !v.length) continue
    rows.push({ key: k, label: fieldLabel(k), value: fmtValue(k, v) })
  }
  return rows
}
