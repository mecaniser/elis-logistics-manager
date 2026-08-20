import { useEffect, useRef, useState } from 'react'
import { Tenant } from '../services/api'
import { tenantColor, businessTypeLabel } from '../utils/tenantAppearance'

interface BusinessSwitcherProps {
  currentTenant: Tenant
  tenants: Tenant[]
  onSelect: (tenant: Tenant) => void
  onOpenDetails: () => void
}

/**
 * Business switcher: the product's core control, so it lives on the left,
 * anchored to the app identity, and holds one scope only — which business
 * am I in. Logout and cross-business CRUD live elsewhere.
 */
export default function BusinessSwitcher({
  currentTenant,
  tenants,
  onSelect,
  onOpenDetails,
}: BusinessSwitcherProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const close = (returnFocus = true) => {
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }

  // Pointer outside dismisses without stealing focus back
  useEffect(() => {
    if (!open) return
    const handlePointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [open])

  // Escape closes and returns focus; arrows move through the menu
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
        return
      }
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return

      const items = Array.from(
        menuRef.current?.querySelectorAll<HTMLElement>('[data-menu-item]') || []
      )
      if (items.length === 0) return
      event.preventDefault()
      const index = items.indexOf(document.activeElement as HTMLElement)
      const next =
        event.key === 'ArrowDown'
          ? items[(index + 1) % items.length]
          : items[(index - 1 + items.length) % items.length]
      next?.focus()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open])

  // Move focus into the menu when it opens
  useEffect(() => {
    if (!open) return
    const first = menuRef.current?.querySelector<HTMLElement>('[data-menu-item]')
    first?.focus()
  }, [open])

  const typeLabel = businessTypeLabel(currentTenant.business_type)

  return (
    <div className="relative min-w-0" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="business-switcher-menu"
        aria-label={`Current business: ${currentTenant.name}. Switch business`}
        className="inline-flex items-center gap-2 min-w-0 max-w-[60vw] sm:max-w-sm pl-2 pr-2 py-1.5 rounded-md border border-gray-600 bg-gray-700 text-white hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-white"
      >
        <span
          aria-hidden="true"
          className="h-5 w-5 rounded flex-shrink-0"
          style={{ backgroundColor: tenantColor(currentTenant.id) }}
        />
        <span className="flex flex-col items-start min-w-0 leading-tight">
          <span className="text-sm font-medium truncate max-w-full">{currentTenant.name}</span>
          {typeLabel && (
            <span className="text-[11px] text-gray-300 truncate max-w-full">{typeLabel}</span>
          )}
        </span>
        <svg className="h-4 w-4 flex-shrink-0 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div
          ref={menuRef}
          id="business-switcher-menu"
          role="menu"
          aria-label="Switch business"
          className="absolute left-0 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-50 py-1"
        >
          <div className="px-3 py-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Switch business
          </div>

          {tenants.map((tenant) => {
            const isCurrent = tenant.id === currentTenant.id
            const label = businessTypeLabel(tenant.business_type)
            return (
              <button
                key={tenant.id}
                type="button"
                data-menu-item
                role="menuitemradio"
                aria-checked={isCurrent}
                onClick={() => {
                  setOpen(false)
                  if (!isCurrent) onSelect(tenant)
                  else triggerRef.current?.focus()
                }}
                className={`w-full flex items-center gap-2.5 px-3 min-h-[44px] py-2 text-left focus:outline-none focus:bg-gray-100 ${
                  isCurrent ? 'bg-blue-50' : 'hover:bg-gray-100'
                }`}
              >
                <span
                  aria-hidden="true"
                  className="h-5 w-5 rounded flex-shrink-0"
                  style={{ backgroundColor: tenantColor(tenant.id) }}
                />
                <span className="flex flex-col min-w-0 flex-1">
                  <span
                    className={`text-sm truncate ${
                      isCurrent ? 'text-blue-700 font-medium' : 'text-gray-700'
                    }`}
                  >
                    {tenant.name}
                  </span>
                  {label && <span className="text-xs text-gray-500 truncate">{label}</span>}
                </span>
                {isCurrent && (
                  <svg className="h-4 w-4 flex-shrink-0 text-blue-700" fill="currentColor" viewBox="0 0 20 20">
                    <title>Current business</title>
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            )
          })}

          <div role="separator" className="border-t border-gray-200 my-1" />

          <button
            type="button"
            data-menu-item
            role="menuitem"
            onClick={() => {
              setOpen(false)
              onOpenDetails()
            }}
            className="w-full flex items-center gap-2 px-3 min-h-[44px] py-2 text-left text-sm text-gray-700 hover:bg-gray-100 focus:outline-none focus:bg-gray-100"
          >
            <svg className="h-4 w-4 flex-shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Details for this business
          </button>
        </div>
      )}
    </div>
  )
}
