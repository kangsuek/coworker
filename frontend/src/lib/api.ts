import type {
  AgentMessagesResponse,
  AppSettingsResponse,
  ChatRequest,
  ChatResponse,
  Memory,
  RunStatus,
  Session,
  SessionDetail,
  UploadResponse,
} from '../types/api'

const API_BASE = '/api'
const MAX_RETRIES = 1
const RETRY_DELAY_MS = 1000

// 네트워크 단절 시 1회 재시도 (HTTP 에러는 재시도 불필요)
async function fetchWithRetry(input: string, init?: RequestInit): Promise<Response> {
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await fetch(input, init)
    } catch (err) {
      if (attempt === MAX_RETRIES) throw err
      await new Promise<void>((resolve) => setTimeout(resolve, RETRY_DELAY_MS))
    }
  }
  throw new Error('Unreachable')
}

async function get<T>(path: string): Promise<T> {
  const res = await fetchWithRetry(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`)
  return res.json()
}

async function del(path: string): Promise<void> {
  const res = await fetchWithRetry(`${API_BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`)
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchWithRetry(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  chat: (req: ChatRequest) => post<ChatResponse>('/chat', req),
  getRunStatus: (runId: string) => get<RunStatus>(`/runs/${runId}`),
  getAgentMessages: (runId: string) =>
    get<AgentMessagesResponse>(`/runs/${runId}/agent-messages`),
  cancelRun: (runId: string) => post<void>(`/runs/${runId}/cancel`),
  getSessions: () => get<Session[]>('/sessions'),
  createSession: () => post<Session>('/sessions'),
  getSession: (id: string) => get<SessionDetail>(`/sessions/${id}`),
  updateSession: (id: string, title: string) => patch<Session>(`/sessions/${id}`, { title }),
  deleteSession: (id: string) => del(`/sessions/${id}`),
  getMemories: () => get<Memory[]>('/memories'),
  createMemory: (content: string) => post<Memory>('/memories', { content }),
  deleteMemory: (id: string) => del(`/memories/${id}`),
  getCliStatus: () => get<{ active_cli_count: number }>('/cli/status'),
  getSettings: () => get<AppSettingsResponse>('/settings'),
  updateSettings: (settings: Record<string, string>) =>
    put<AppSettingsResponse>('/settings', { settings }),
  resetSettings: () => del('/settings'),
  uploadFiles: async (files: File[]): Promise<UploadResponse> => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    const res = await fetchWithRetry('/api/upload', { method: 'POST', body: form })
    if (!res.ok) throw new Error(`POST /upload failed: ${res.status}`)
    return res.json()
  },
}
