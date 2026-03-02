import type {
  AgentMessagesResponse,
  ChatRequest,
  ChatResponse,
  RunStatus,
  Session,
  SessionDetail,
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

async function del(path: string): Promise<void> {
  const res = await fetchWithRetry(`${API_BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`)
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
  deleteSession: (id: string) => del(`/sessions/${id}`),
}
