// Shared diff display utilities: field label mapping and value formatting
// Used by ConflictResolve / DiffEntry / DiffDetail

// Field path -> human-readable name (host fields use dotted paths, hardware entry fields are bare keys)
const FIELD_LABELS: Record<string, string> = {
  // Host fields
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
  // NIC entry fields
  name: '网卡',
  mac: 'MAC',
  ips: 'IP 列表',
  // Memory entry fields
  slot: '槽位',
  manufacturer: '厂商',
  part_number: '型号颗粒',
  type: '类型',
  size: '容量',
  size_unit: '容量单位',
  speed_mts: '频率',
  // CPU / disk / PSU entry fields
  model: '型号',
  max_power_w: '最大功率',
  // GPU entry fields
  uuid: 'UUID',
  driver_version: '驱动版本',
  pcie_id: 'PCIe',
}

export function fieldLabel(f: string): string {
  return FIELD_LABELS[f] ?? f
}

// IP list value: [{ip, prefix_length}] -> "10.0.0.1/24, 10.0.0.2"
function fmtIps(v: unknown): string {
  const list = (v as { ip: string; prefix_length: number | null }[] | null) || []
  return list.length
    ? list.map((i) => i.ip + (i.prefix_length ? '/' + i.prefix_length : '')).join(', ')
    : '无'
}

// Single value formatting: old/new value display for diff rows
export function fmtValue(field: string, v: unknown): string {
  if (v === null || v === undefined || v === '') return '-'
  if (field === 'ips') return fmtIps(v)
  return String(v)
}

// Full object of added/removed entries -> key-value rows (skip empty values, fold size_unit into size)
export function fullRows(obj: Record<string, unknown> | null): { key: string; label: string; value: string }[] {
  if (!obj) return []
  const rows: { key: string; label: string; value: string }[] = []
  for (const [k, v] of Object.entries(obj)) {
    if (v === null || v === undefined || v === '') continue
    if (k === 'size_unit') continue // folded into size display
    if (k === 'size') {
      rows.push({ key: k, label: fieldLabel(k), value: `${v}${obj.size_unit ?? ''}` })
      continue
    }
    if (Array.isArray(v) && !v.length) continue
    rows.push({ key: k, label: fieldLabel(k), value: fmtValue(k, v) })
  }
  return rows
}
