import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { api } from '@/lib/api'
import type { RequestRecord } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input, Label, Select, Textarea } from '@/components/ui/controls'
import { useUiStore } from '@/lib/stores/uiStore'

const schema = z
  .object({
    title: z.string().min(3, 'Укажите название (минимум 3 символа)'),
    description: z.string(),
    company_id: z.string(),
    contract_id: z.string(),
    product_id: z.string(),
    cost_total: z.string().refine((v) => !v || Number(v) > 0, 'Стоимость должна быть положительной'),
    date_start: z.string(),
    date_end: z.string(),
  })
  .refine((v) => !v.date_start || !v.date_end || v.date_start <= v.date_end, {
    message: 'Дата окончания раньше даты начала',
    path: ['date_end'],
  })

type FormValues = z.infer<typeof schema>

export function RequestHeaderForm({ request, onSaved }: { request: RequestRecord; onSaved?: () => void }) {
  const toast = useUiStore((s) => s.toast)

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: request.title ?? '',
      description: request.description ?? '',
      company_id: request.company_id ?? '',
      contract_id: request.contract_id ?? '',
      product_id: request.product_id ?? '',
      cost_total: request.cost_total != null ? String(request.cost_total) : '',
      date_start: request.date_start ?? '',
      date_end: request.date_end ?? '',
    },
  })

  const { data: companies = [] } = useQuery({ queryKey: ['companies'], queryFn: () => api.listCompanies(), staleTime: Infinity })
  const watchedCompanyId = watch('company_id')
  const watchedContractId = watch('contract_id')
  const { data: contracts = [] } = useQuery({
    queryKey: ['contracts', watchedCompanyId || null],
    queryFn: () => api.listContracts(watchedCompanyId || undefined),
  })
  const { data: products = [] } = useQuery({
    queryKey: ['products', watchedContractId || null],
    queryFn: () => api.listProducts(watchedContractId || undefined),
  })

  useEffect(() => {
    reset({
      title: request.title ?? '',
      description: request.description ?? '',
      company_id: request.company_id ?? '',
      contract_id: request.contract_id ?? '',
      product_id: request.product_id ?? '',
      cost_total: request.cost_total != null ? String(request.cost_total) : '',
      date_start: request.date_start ?? '',
      date_end: request.date_end ?? '',
    })
  }, [request.updated_at, request.id, reset, request])

  const submit = handleSubmit(async (values) => {
    await api.updateRequest(request.id, {
      title: values.title,
      description: values.description,
      company_id: values.company_id || null,
      contract_id: values.contract_id || null,
      product_id: values.product_id || null,
      cost_total: values.cost_total ? Number(values.cost_total) : null,
      date_start: values.date_start || null,
      date_end: values.date_end || null,
    })
    toast('Шапка заявки сохранена', 'success')
    onSaved?.()
  })

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <Label htmlFor="hf_title">Название заявки</Label>
        <Input id="hf_title" {...register('title')} placeholder="Например: Подсчет запасов и 3D геомодель" />
        {errors.title && <p className="mt-1 text-xs text-red-500">{errors.title.message}</p>}
      </div>

      <div>
        <Label htmlFor="hf_desc">Описание</Label>
        <Textarea id="hf_desc" rows={3} {...register('description')} placeholder="Краткое описание работ" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="hf_company">Подрядчик</Label>
          <Select
            id="hf_company"
            {...register('company_id')}
            onChange={(e) => {
              setValue('company_id', e.target.value, { shouldDirty: true })
              setValue('contract_id', '', { shouldDirty: true })
              setValue('product_id', '', { shouldDirty: true })
            }}
          >
            <option value="">Не выбран</option>
            {companies.map((c) => (
              <option key={c.company_id} value={c.company_id}>
                {c.name} — рейтинг {c.rating}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="hf_contract">Договор</Label>
          <Select id="hf_contract" {...register('contract_id')} disabled={!watchedCompanyId}>
            <option value="">Не выбран</option>
            {contracts.map((k) => (
              <option key={k.contract_id} value={k.contract_id}>
                {k.contract_number}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="hf_product">Продукт (услуга)</Label>
        <Select id="hf_product" {...register('product_id')} disabled={!watchedContractId}>
          <option value="">Не выбран</option>
          {products.map((p) => (
            <option key={p.product_id} value={p.product_id}>
              {p.product_name}
            </option>
          ))}
        </Select>
        {!watchedContractId && <p className="mt-1 text-xs text-slate-400">Сначала выберите договор — список продуктов фильтруется по нему</p>}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <Label htmlFor="hf_cost">Стоимость, ₽</Label>
          <Input id="hf_cost" type="number" min={0} {...register('cost_total')} placeholder="24 500 000" />
          {errors.cost_total && <p className="mt-1 text-xs text-red-500">{errors.cost_total.message}</p>}
        </div>
        <div>
          <Label htmlFor="hf_start">Начало работ</Label>
          <Input id="hf_start" type="date" {...register('date_start')} />
        </div>
        <div>
          <Label htmlFor="hf_end">Окончание работ</Label>
          <Input id="hf_end" type="date" {...register('date_end')} />
          {errors.date_end && <p className="mt-1 text-xs text-red-500">{errors.date_end.message}</p>}
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-4">
        <p className="mr-auto text-xs text-slate-400">Поля можно заполнить вручную или применить предложения ИИ из чата справа</p>
        <Button type="submit" disabled={!isDirty}>
          <Save className="h-4 w-4" />
          Сохранить
        </Button>
      </div>
    </form>
  )
}
