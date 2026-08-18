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
    let active = true
    api
      .getChatMessages(sessionId)
      .then((msgs) => {
        if (active) setMessages(msgs)
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
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
        const fresh = await api.getChatMessages(sessionId)
        // Локальные suggestions (продукты/подрядчики/аналоги) сервер не хранит —
        // сохраняем их поверх свежей истории, чтобы карточки не исчезали из чата.
        setMessages((prev) =>
          fresh.map((m) => {
            const local = prev.find((p) => p.id === m.id || (p.role === m.role && p.content === m.content))
            return local?.suggestions ? { ...m, suggestions: local.suggestions } : m
          }),
        )
      } finally {
        streamRef.current = false
        setStreaming(false)
      }
    },
    [sessionId],
  )

  const applyActions = useCallback(
    async (actions: ChatAction[]) => {
      if (!sessionId) return null
      const result = await api.applyActions(sessionId, actions)
      const appliedFields = new Set(result.applied.map((a) => a.field))
      setMessages((prev) =>
        prev.map((m) =>
          m.actions
            ? { ...m, actions: m.actions.map((a) => (actions.includes(a) && appliedFields.has(a.field ?? '') ? { ...a, applied: true } : a)) }
            : m,
        ),
      )
      return result
    },
    [sessionId],
  )

  return { messages, streaming, send, applyActions }
}
