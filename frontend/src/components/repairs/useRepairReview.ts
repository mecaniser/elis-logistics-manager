import { useEffect, useState } from 'react'
import { financeApi, financeError } from '../../services/finance'
import type { RepairReviewReport } from './repairReview'

export function useRepairReview(tenantId: number | undefined, revision: unknown, asOf: string) {
  const [result, setResult] = useState<{tenantId: number; asOf: string; data?: RepairReviewReport; error?: string} | null>(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    setResult(null)
    if (tenantId) {
      financeApi.repairHistory(asOf).then(data => {
        if (active && data.tenant_id === tenantId) setResult({tenantId, asOf, data})
      }).catch(error => {
        if (active) setResult({tenantId, asOf, error: financeError(error)})
      })
    }
    return () => { active = false }
  }, [tenantId, revision, asOf, attempt])
  const current = result?.tenantId === tenantId && result?.asOf === asOf ? result : null
  return { data: current?.data, error: current?.error, loading: !current, retry: () => setAttempt(a => a + 1) }
}
