import { useCallback, useEffect, useState } from 'react'

import { api } from '../lib/api'
import type { Session, UserMessage } from '../types/api'

export interface UseSessionResult {
  sessions: Session[]
  currentSession: Session | null
  messages: UserMessage[]
  switchSession: (id: string) => Promise<void>
  createSession: () => Promise<void>
  addMessage: (msg: UserMessage) => void
  setCurrentSessionFromChat: (sessionId: string) => void
  refreshSessions: () => Promise<void>
}

export function useSession(): UseSessionResult {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSession, setCurrentSession] = useState<Session | null>(null)
  const [messages, setMessages] = useState<UserMessage[]>([])

  useEffect(() => {
    api.getSessions().then(setSessions).catch(() => {})
  }, [])

  const switchSession = useCallback(async (id: string) => {
    const detail = await api.getSession(id)
    setCurrentSession(detail)
    setMessages(detail.messages)
  }, [])

  const createSession = useCallback(async () => {
    const sess = await api.createSession()
    setSessions((prev) => [sess, ...prev])
    setCurrentSession(sess)
    setMessages([])
  }, [])

  const addMessage = useCallback((msg: UserMessage) => {
    setMessages((prev) => [...prev, msg])
    if (msg.role === 'reader') {
      api.getSessions().then(setSessions).catch(() => {})
    }
  }, [])

  const setCurrentSessionFromChat = useCallback((sessionId: string) => {
    const pseudo: Session = {
      id: sessionId,
      title: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    setCurrentSession(pseudo)
    setSessions((prev) => {
      if (prev.find((s) => s.id === sessionId)) return prev
      return [pseudo, ...prev]
    })
  }, [])

  const refreshSessions = useCallback(async () => {
    const list = await api.getSessions()
    setSessions(list)
    setCurrentSession((prev) => {
      if (!prev) return prev
      return list.find((s) => s.id === prev.id) ?? prev
    })
  }, [])

  return {
    sessions,
    currentSession,
    messages,
    switchSession,
    createSession,
    addMessage,
    setCurrentSessionFromChat,
    refreshSessions,
  }
}
