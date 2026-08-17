import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Send, Sparkles } from 'lucide-react'
import { api } from '@/lib/api'
import type { ChatAction } from '@/lib/api'
import { useChatStream } from '@/lib/hooks/useChatStream'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/controls'
import { ChatMessageView } from './ChatMessage'
import { useUiStore } from '@/lib/stores/uiStore'
import { cn } from '@/lib/utils'

interface AiChatProps {
  requestId: string
  onApplied?: () => void
  onCreateTz?: (templateId: string) => void
  pendingQuestion?: { text: string; nonce: number } | null
  className?: string
}

export function AiChat({ requestId, onApplied, onCreateTz, pendingQuestion, className }: AiChatProps) {
  const { data: session } = useQuery({
    queryKey: ['chatSession', requestId],
    queryFn: () => api.createChatSession(requestId),
    staleTime: Infinity,
  })
  const { messages, streaming, send, applyActions } = useChatStream(session?.id ?? null)
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const toast = useUiStore((s) => s.toast)

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  useEffect(() => {
    if (pendingQuestion && pendingQuestion.nonce > 0) {
      void send(pendingQuestion.text)
    }
  }, [pendingQuestion?.nonce, pendingQuestion, send])

  const handleApply = (actions: ChatAction[]) => {
    void applyActions(actions).then((applied) => {
      if (applied.length > 0) {
        toast(`Применено предложений: ${applied.length}`, 'success')
        onApplied?.()
      }
    })
  }

  const submit = () => {
    if (!input.trim() || streaming) return
    void send(input)
    setInput('')
  }

  return (
    <div className={cn('flex min-h-0 flex-col rounded-xl border border-slate-200 bg-white shadow-card', className)}>
      <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-800 text-white">
          <Sparkles className="h-3.5 w-3.5" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-800">ИИ-консультант</p>
          <p className="text-[11px] text-slate-400">Предлагает варианты — решение всегда за вами</p>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="rounded-xl border border-dashed border-brand-200 bg-brand-50/50 p-4 text-sm text-brand-900/80">
            Опишите задачу — например: <span className="font-medium">«Нужно оценить запасы по объекту и построить 3D-геомодель»</span>.
            ИИ подберет продукты, подрядчиков и порекомендует шаблон ТЗ. Можно заполнять форму и без чата.
          </div>
        )}
        {messages.map((m, i) => (
          <ChatMessageView
            key={m.id}
            message={m}
            streaming={streaming && i === messages.length - 1 && m.role === 'assistant'}
            onApply={handleApply}
            onCreateTz={(templateId) => onCreateTz?.(templateId)}
          />
        ))}
      </div>

      <div className="border-t border-slate-100 p-3">
        <div className="flex items-end gap-2">
          <Textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            placeholder="Спросите ИИ или опишите задачу…"
            className="min-h-[44px]"
          />
          <Button size="icon" onClick={submit} loading={streaming} disabled={!input.trim() && !streaming}>
            {streaming ? undefined : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  )
}
