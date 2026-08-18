import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../msw/server'
import { useJobPolling } from '@/lib/hooks/useJobPolling'
import { JOB_ID } from '../utils/fixtures'

const pendingJob = { id: JOB_ID, type: 'fill_ai', status: 'pending', result: null, error: null }
const doneJob = { id: JOB_ID, type: 'fill_ai', status: 'done', result: { block_code: 'goals' }, error: null }

describe('useJobPolling', () => {
  it('поллит, пока job не завершится, затем вызывает onDone', async () => {
    // Arrange
    let calls = 0
    const onDone = vi.fn()
    server.use(
      http.get(`*/api/v1/jobs/${JOB_ID}`, () => {
        calls += 1
        return HttpResponse.json(calls >= 3 ? doneJob : pendingJob)
      }),
    )

    // Act
    const { result } = renderHook(() => useJobPolling(JOB_ID, onDone))
    await vi.waitFor(() => expect(result.current.polling).toBe(false), { timeout: 5000 })

    // Assert
    expect(calls).toBeGreaterThanOrEqual(3)
    expect(result.current.job?.status).toBe('done')
    expect(result.current.job?.result).toEqual({ block_code: 'goals' })
    expect(onDone).toHaveBeenCalledTimes(1)
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ status: 'done' }))
  })

  it('останавливается на failed и отдаёт ошибку', async () => {
    // Arrange
    const failedJob = { id: JOB_ID, type: 'fill_ai', status: 'failed', result: null, error: 'LLM недоступен' }
    server.use(http.get(`*/api/v1/jobs/${JOB_ID}`, () => HttpResponse.json(failedJob)))

    // Act
    const { result } = renderHook(() => useJobPolling(JOB_ID))
    await vi.waitFor(() => expect(result.current.polling).toBe(false), { timeout: 5000 })

    // Assert
    expect(result.current.job?.status).toBe('failed')
    expect(result.current.job?.error).toBe('LLM недоступен')
  })

  it('без jobId не опрашивает ничего', async () => {
    // Arrange
    const spy = vi.fn()
    server.use(http.get('*/api/v1/jobs/*', () => spy() as unknown as Response))

    // Act
    const { result } = renderHook(() => useJobPolling(null))

    // Assert
    expect(result.current.job).toBeNull()
    expect(result.current.polling).toBe(false)
    expect(spy).not.toHaveBeenCalled()
  })
})
