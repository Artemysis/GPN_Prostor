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
    const tick = async () => {
      const current = api.getJob(jobId)
      if (!active) return
      setJob(current)
      if (current.status === 'done' || current.status === 'failed') {
        setPolling(false)
        onDoneRef.current?.(current)
        return
      }
      setTimeout(tick, 700)
    }
    tick()
    return () => {
      active = false
    }
  }, [jobId])

  return { job, polling }
}
