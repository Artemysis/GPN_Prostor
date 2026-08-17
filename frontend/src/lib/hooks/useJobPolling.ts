import { useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import type { Job } from '@/lib/api'

export function useJobPolling(jobId: string | null, onDone?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null)
  const [polling, setPolling] = useState(false)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    if (!jobId) {
      setJob(null)
      setPolling(false)
      return
    }
    setPolling(true)
    let active = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const tick = async () => {
      let current: Job
      try {
        current = await api.getJob(jobId)
      } catch {
        if (!active) return
        timer = setTimeout(tick, 1000)
        return
      }
      if (!active) return
      setJob(current)
      if (current.status === 'done' || current.status === 'failed') {
        setPolling(false)
        onDoneRef.current?.(current)
        return
      }
      timer = setTimeout(tick, 700)
    }
    tick()
    return () => {
      active = false
      if (timer) clearTimeout(timer)
    }
  }, [jobId])

  return { job, polling }
}
