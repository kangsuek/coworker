import type {
  AgentMessagesResponse,
  ChatRequest,
  ChatResponse,
  RunStatus,
  Session,
  SessionDetail,
} from '../types/api'

const API_BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
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
}
