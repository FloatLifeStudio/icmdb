// API client 封装:统一错误处理,REST 风格
const BASE = '/api/v1'

export interface NicIPOut {
  id: number
  ip: string
  prefix_length: number | null
}

export interface NicOut {
  id: number
  name: string
  mac: string | null
  ips: NicIPOut[]
}

export interface MemorySlot {
  id: number
  slot: string
  manufacturer: string | null
  part_number: string | null
  type: string | null
  size_gb: number | null
  speed_mts: number | null
  serial_number: string | null
}

export interface CpuSlot {
  id: number
  slot: string
  model: string | null
}

export interface Disk {
  id: number
  serial_number: string
  type: string | null
  manufacturer: string | null
  model: string | null
  size: number | null
  size_unit: string | null
}

export interface Psu {
  id: number
  serial_number: string
  manufacturer: string | null
  model: string | null
  max_power_w: number | null
}

export interface DeviceOut {
  id: number
  hostname: string
  serial_number: string | null
  mgmt_mac: string | null
  mgmt_ip: string | null
  mgmt_prefix_length: number | null
  last_pushed_at: string | null
  created_at: string
  updated_at: string
  status: string
  tags: string[]
  nics: NicOut[]
  memory: MemorySlot[]
  cpus: CpuSlot[]
  disks: Disk[]
  psus: Psu[]
}

export interface DeviceListOut {
  total: number
  page: number
  page_size: number
  items: DeviceOut[]
}

export interface FieldDiff {
  field: string
  old: unknown
  new: unknown
}

export interface NicDiff {
  name: string
  kind: 'added' | 'removed' | 'changed'
  changes: { field: string; old: unknown; new: unknown }[]
  old: Record<string, unknown> | null
  new: Record<string, unknown> | null
}

export interface SlotDiff {
  slot?: string
  serial_number?: string
  kind: 'added' | 'removed' | 'changed'
  changes: { field: string; old: unknown; new: unknown }[]
  old: Record<string, unknown> | null
  new: Record<string, unknown> | null
}

export interface PendingChange {
  id: number
  device_id: number
  source: string | null
  payload: Record<string, unknown>
  diff: {
    fields: FieldDiff[]
    nics: NicDiff[]
    memory?: SlotDiff[]
    cpus?: SlotDiff[]
    disks?: SlotDiff[]
    psus?: SlotDiff[]
    has_changes: boolean
  }
  status: string
  created_at: string
  resolved_at: string | null
}

export interface PostResult {
  result: string
  device_id: number
  pending_change_id: number | null
}

export interface ResolveBody {
  field_choices: Record<string, string>
  nic_choices: Record<string, string>
  memory_choices?: Record<string, string>
  cpu_choices?: Record<string, string>
  disk_choices?: Record<string, string>
  psu_choices?: Record<string, string>
}

export interface DashboardOut {
  total_devices: number
  active: number
  suspected_offline: number
  pending_changes: number
  recent_changes: HistoryRow[]
}

export interface HistoryRow {
  id: number
  device_id: number
  summary: string
  source: string | null
  diff: Record<string, unknown> | null
  created_at: string
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const api = {
  pushDevice: (push: unknown) =>
    request<PostResult>(`${BASE}/devices`, json('POST', push)),

  listDevices: (params: {
    page?: number
    page_size?: number
    search?: string
    status?: string
    tag?: string
    sort_by?: string
    sort_order?: string
  }) => {
    const qs = new URLSearchParams()
    if (params.page) qs.set('page', String(params.page))
    if (params.page_size) qs.set('page_size', String(params.page_size))
    if (params.search) qs.set('search', params.search)
    if (params.status) qs.set('status', params.status)
    if (params.tag) qs.set('tag', params.tag)
    if (params.sort_by) qs.set('sort_by', params.sort_by)
    if (params.sort_order) qs.set('sort_order', params.sort_order)
    return request<DeviceListOut>(`${BASE}/devices?${qs}`)
  },

  getDevice: (id: number) => request<DeviceOut>(`${BASE}/devices/${id}`),

  deleteDevice: (id: number) => request<void>(`${BASE}/devices/${id}`, { method: 'DELETE' }),

  batchDelete: (ids: number[]) =>
    request<{ deleted: number[] }>(`${BASE}/devices/batch-delete`, json('POST', { ids })),

  updateTags: (id: number, tags: string[]) =>
    request<{ device_id: number; tags: string[] }>(
      `${BASE}/devices/${id}/tags`,
      json('PUT', { tags }),
    ),

  exportCsvUrl: () => `${BASE}/devices/export/csv`,

  importCsvUrl: () => `${BASE}/devices/import/csv`,

  dashboard: () => request<DashboardOut>(`${BASE}/dashboard`),

  getHistoryDetail: (id: number) => request<HistoryRow>(`${BASE}/change-history/${id}`),

  listPendingChanges: (status = 'pending') =>
    request<{ items: PendingChange[] }>(`${BASE}/pending-changes?status=${status}`),

  getPendingChange: (id: number) =>
    request<PendingChange>(`${BASE}/pending-changes/${id}`),

  resolve: (id: number, body: ResolveBody) =>
    request<{ applied: string[]; pending_id: number; status: string }>(
      `${BASE}/pending-changes/${id}/resolve`,
      json('POST', body),
    ),
}
