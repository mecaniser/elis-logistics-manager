import { createContext, useContext } from 'react'
import type { Tenant } from '../services/api'

interface TenantContextType {
  currentTenant: Tenant | null
  tenants: Tenant[]
  setCurrentTenant: (tenant: Tenant) => void
  loadTenants: () => Promise<void>
  loading: boolean
}

export const TenantContext = createContext<TenantContextType | undefined>(undefined)

export function useTenant() {
  const context = useContext(TenantContext)
  if (context === undefined) {
    throw new Error('useTenant must be used within a TenantProvider')
  }
  return context
}

