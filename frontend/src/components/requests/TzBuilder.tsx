import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { RequestTz } from '@/lib/api'
import { TzBlockCard } from './TzBlockCard'
import { TzStageEditor } from './TzStageEditor'

export function TzBuilder({ requestId, tz }: { requestId: string; tz: RequestTz }) {
  const { data: template } = useQuery({
    queryKey: ['template', tz.template_id],
    queryFn: () => api.getTemplate(tz.template_id),
    staleTime: Infinity,
  })

  if (!template) return null

  return (
    <div className="space-y-4">
      {tz.blocks
        .slice()
        .sort((a, b) => {
          const sa = template.blocks_schema.blocks.find((x) => x.code === a.block_code)?.order ?? 99
          const sb = template.blocks_schema.blocks.find((x) => x.code === b.block_code)?.order ?? 99
          return sa - sb
        })
        .map((block) => {
          const schema = template.blocks_schema.blocks.find((x) => x.code === block.block_code)
          if (!schema) return null
          if (schema.is_stages_block) {
            return <TzStageEditor key={block.block_code} requestId={requestId} tz={tz.stages} template={template} />
          }
          return <TzBlockCard key={block.block_code} block={block} schema={schema} requestId={requestId} />
        })}
    </div>
  )
}
