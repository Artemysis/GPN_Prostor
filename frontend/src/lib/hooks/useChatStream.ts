import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import type { ChatAction, ChatEvent, ChatMessage } from '@/lib/api'
import { uid } from '@/lib/utils'

export function useChatStream(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const streamRef = useRef(false)

  useEffect(() => {
    if (!sessionId) {
      setMessages([])
      return
    }
    setMessages(api.getChatMessages(sessionId))
  }, [sessionId])

  const send = useCallback(
    async (content: string) => {
      if (!sessionId || streamRef.current) return
      const trimmed = content.trim()
      if (!trimmed) return
      streamRef.current = true
      setStreaming(true)
      const assistantId = uid('m_stream_')
      setMessages((prev) => [
        ...prev,
        { id: uid('m_'), role: 'user', content: trimmed, actions: null, suggestions: null, created_at: new Date().toISOString() },
        { id: assistantId, role: 'assistant', content: '', actions: null, suggestions: null, created_at: new Date().toISOString() },
      ])

      const onEvent = (e: ChatEvent) => {
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== assistantId) return m
            switch (e.type) {
              case 'delta':
                return { ...m, content: m.content + e.content }
              case 'products':
                return { ...m, suggestions: { ...m.suggestions, products: e.items } }
              case 'contractors':
                return { ...m, suggestions: { ...m.suggestions, contractors: e.items } }
              case 'similar_requests':
                return { ...m, suggestions: { ...m.suggestions, similar_requests: e.items } }
              case 'actions':
                return { ...m, actions: e.actions }
              case 'done':
                return m
            }
          }),
        )
      }

      try {
        await api.streamChat(sessionId, trimmed, onEvent)
        setMessages(api.getChatMessages(sessionId))
      } finally {
        streamRef.current = false
        setStreaming(false)
      }
    },
    [sessionId],
  )

  const applyActions = useCallback(
    (actions: ChatAction[]) => {
      if (!sessionId) return []
      const applied = api.applyActions(sessionId, actions)
      setMessages(api.getChatMessages(sessionId))
      return applied
    },
    [sessionId],
  )

  return { messages, streaming, send, applyActions }
}
