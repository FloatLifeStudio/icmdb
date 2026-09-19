// API client wrapper: unified error handling, REST style
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
  size: number | null
  size_unit: string | null
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
  size_gb: number | null
}

export interface Psu {
  id: number
  serial_number: string
  manufacturer: string | null
  model: string | null
  max_power_w: number | null
}

export interface Gpu {
  id: number
  uuid: string
  name: string | null
  serial_number: string | null
  size: number | null
  size_unit: string | null
  size_gb: number | null
  driver_version: string | null
  pcie_id: string | null
}

export interface DeviceOut {
  id: number
  hostname: string
  serial_number: string | null
  os_type: string | null
  os_version: string | null
  os_virt: string | null
  kernel: string | null
  agent_version: string | null
  location: string | null
  owner: string | null
  purpose: string | null
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
  gpus: Gpu[]
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
  uuid?: string
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
    gpus?: SlotDiff[]
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
  gpu_choices?: Record<string, string>
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

export interface UserInfo {
  id: number
  username: string
  role: string
  created_at: string
}

export interface SystemSettings {
  offline_threshold_hours: number
  api_key_enabled: boolean
}

export interface ApiKey {
  id: number
  name: string
  key: string
  prefix: string
  created_at: string
  last_used_at: string | null
}

export interface AuditLogRow {
  id: number
  username: string | null
  action: string
  detail: string | null
  created_at: string
}

export interface MetadataIn {
  location?: string | null
  owner?: string | null
  purpose?: string | null
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    // Session expired: except for login/session check, any 401 redirects to the login page
    if (
      res.status === 401 &&
      !url.startsWith(`${BASE}/auth/`) &&
      !window.location.pathname.startsWith('/login')
    ) {
      window.location.href = '/login'
    }
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

  updateMetadata: (id: number, body: MetadataIn) =>
    request<{ device_id: number; location: string | null; owner: string | null; purpose: string | null }>(
      `${BASE}/devices/${id}/metadata`,
      json('PUT', body),
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

  login: (username: string, password: string) =>
    request<{ username: string; role: string }>(`${BASE}/auth/login`, json('POST', { username, password })),

  logout: () => request<{ ok: boolean }>(`${BASE}/auth/logout`, json('POST', {})),

  changePassword: (oldPassword: string, newPassword: string) =>
    request<{ ok: boolean }>(
      `${BASE}/auth/change-password`,
      json('POST', { old_password: oldPassword, new_password: newPassword }),
    ),

  me: () => request<{ username: string; role: string }>(`${BASE}/auth/me`),

  listUsers: () => request<{ items: UserInfo[] }>(`${BASE}/users`),

  createUser: (body: { username: string; password: string; role: string }) =>
    request<UserInfo>(`${BASE}/users`, json('POST', body)),

  updateUser: (id: number, body: { password?: string; role?: string }) =>
    request<UserInfo>(`${BASE}/users/${id}`, json('PUT', body)),

  deleteUser: (id: number) => request<{ ok: boolean }>(`${BASE}/users/${id}`, { method: 'DELETE' }),

  getSystemSettings: () => request<SystemSettings>(`${BASE}/settings/system`),

  updateSystemSettings: (body: SystemSettings) =>
    request<SystemSettings>(`${BASE}/settings/system`, json('PUT', body)),

  listAuditLogs: (username = '') => {
    const qs = username ? `?username=${encodeURIComponent(username)}` : ''
    return request<{ items: AuditLogRow[] }>(`${BASE}/audit-logs${qs}`)
  },

  listApiKeys: () => request<{ items: ApiKey[] }>(`${BASE}/api-keys`),

  createApiKey: (name: string) => request<ApiKey>(`${BASE}/api-keys`, json('POST', { name })),

  deleteApiKey: (id: number) => request<{ ok: boolean }>(`${BASE}/api-keys/${id}`, { method: 'DELETE' }),
}
