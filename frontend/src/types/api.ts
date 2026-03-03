export interface ChatRequest {
  session_id?: string
  message: string
}

export interface ChatResponse {
  run_id: string
  session_id: string
}

export interface AgentInfo {
  name: string
  role_preset: string
  status: string
}

export type RunStatusType =
  | 'queued'
  | 'thinking'
  | 'solo'
  | 'delegating'
  | 'working'
  | 'integrating'
  | 'done'
  | 'error'
  | 'cancelled'

export interface TimingInfo {
  queued_at: string | null
  thinking_started_at: string | null
  cli_started_at: string | null
  finished_at: string | null
}

export interface RunStatus {
  status: RunStatusType
  progress: string | null
  response: string | null
  mode: 'solo' | 'team' | null
  model: string | null
  agents: AgentInfo[] | null
  timing: TimingInfo | null
}

export interface AgentMessage {
  id: string
  sender: string
  role_preset: string
  content: string
  status: 'working' | 'done' | 'error' | 'cancelled'
  created_at: string
}

export interface AgentMessagesResponse {
  messages: AgentMessage[]
  has_more: boolean
}

export interface Session {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface UserMessage {
  id: string
  role: string
  content: string
  mode: string | null
  model?: string | null
  timing?: TimingInfo | null
  created_at: string
}

export interface SessionDetail extends Session {
  messages: UserMessage[]
}
