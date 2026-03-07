import { useCallback, useEffect, useState } from 'react'

import { api } from '../lib/api'
import type { Memory } from '../types/api'

export function useMemory() {
  const [memories, setMemories] = useState<Memory[]>([])

  useEffect(() => {
    api.getMemories().then(setMemories).catch(() => {})
  }, [])

  const refreshMemories = useCallback(() => {
    api.getMemories().then(setMemories).catch(() => {})
  }, [])

  const addMemory = useCallback(async (content: string) => {
    const mem = await api.createMemory(content)
    setMemories((prev) => [...prev, mem])
  }, [])

  const removeMemory = useCallback(async (id: string) => {
    await api.deleteMemory(id)
    setMemories((prev) => prev.filter((m) => m.id !== id))
  }, [])

  return { memories, addMemory, removeMemory, refreshMemories }
}
