import { useEffect, useState } from 'react'
import { useTenant } from '../contexts/TenantContext'
import { financeApi } from '../services/finance'
import Dashboard from './Dashboard'
import Finance from './Finance'

/** Cutover is explicit, tenant-scoped, and blocked until a reconciled snapshot is accepted. */
export default function Home() {
  const { currentTenant } = useTenant()
  const [selection, setSelection] = useState<{tenant: number; enabled: boolean} | null>(null)
  useEffect(() => {
    let active = true
    if (!currentTenant) return
    const tenant = currentTenant.id
    financeApi.context().then(context => { if (active) setSelection({tenant, enabled: context.home_enabled}) }).catch(() => { if (active) setSelection({tenant, enabled: false}) })
    return () => { active = false }
  }, [currentTenant])
  if (!currentTenant || selection?.tenant !== currentTenant.id) return <p role="status">Loading business workspace…</p>
  return selection.enabled ? <Finance /> : <Dashboard />
}
