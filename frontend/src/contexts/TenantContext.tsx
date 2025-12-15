import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { tenantsApi, Tenant } from '../services/api'

interface TenantContextType {
  currentTenant: Tenant | null
  tenants: Tenant[]
  setCurrentTenant: (tenant: Tenant) => void
  loadTenants: () => Promise<void>
  loading: boolean
}

const TenantContext = createContext<TenantContextType | undefined>(undefined)

export function TenantProvider({ children }: { children: ReactNode }) {
  const [currentTenant, setCurrentTenantState] = useState<Tenant | null>(null)
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)

  // Load tenants from API
  const loadTenants = async () => {
    try {
      const response = await tenantsApi.getTenants()
      const data = response.data
      setTenants(data)
      
      // If no current tenant is set, try to load from localStorage or use first tenant
      const savedTenantId = localStorage.getItem('currentTenantId')
      if (savedTenantId) {
        const savedTenant = data.find((t: Tenant) => t.id === parseInt(savedTenantId))
        if (savedTenant) {
          setCurrentTenantState(savedTenant)
        } else if (data.length > 0) {
          // Saved tenant not found, use first available
          setCurrentTenantState(data[0])
          localStorage.setItem('currentTenantId', data[0].id.toString())
        }
      } else if (data.length > 0) {
        // No saved tenant, use first available
        setCurrentTenantState(data[0])
        localStorage.setItem('currentTenantId', data[0].id.toString())
      }
    } catch (error) {
      console.error('Failed to load tenants:', error)
    } finally {
      setLoading(false)
    }
  }

  // Set current tenant and save to localStorage
  const setCurrentTenant = (tenant: Tenant) => {
    setCurrentTenantState(tenant)
    localStorage.setItem('currentTenantId', tenant.id.toString())
  }

  // Load tenants on mount
  useEffect(() => {
    loadTenants()
  }, [])

  return (
    <TenantContext.Provider
      value={{
        currentTenant,
        tenants,
        setCurrentTenant,
        loadTenants,
        loading,
      }}
    >
      {children}
    </TenantContext.Provider>
  )
}

export function useTenant() {
  const context = useContext(TenantContext)
  if (context === undefined) {
    throw new Error('useTenant must be used within a TenantProvider')
  }
  return context
}

