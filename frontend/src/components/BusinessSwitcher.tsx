import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Tenant } from '../services/api'
import { tenantColor, businessTypeLabel } from '../utils/tenantAppearance'

interface BusinessSwitcherProps {
  currentTenant: Tenant
  tenants: Tenant[]
  onSelect: (tenant: Tenant) => void
  onOpenDetails: (tenant: Tenant) => void
}

const infoIcon = (
  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

/**
 * Business switcher: the product's core control, so it lives on the left,
 * anchored to the app identity, and holds one scope only — which business
 * am I in. Logout and cross-business CRUD live elsewhere.
 *
 * Details are reachable without switching: from the chip for the current
 * business, and from any row for the others. Looking up an EIN should never
 * require changing which business you are working in.
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

  /**
   * Up/Down move between businesses; Left/Right reach each row's details
   * button. Keeping the row actions off the vertical axis means switching
   * stays one keypress per business no matter how many businesses exist.
   */
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
        return
      }

      const active = document.activeElement as HTMLElement | null
      if (!active || !menuRef.current?.contains(active)) return

      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        const rows = Array.from(
          menuRef.current.querySelectorAll<HTMLElement>('[data-menu-row]')
        )
        if (rows.length === 0) return
        event.preventDefault()
        const currentRow = active.closest('[data-row-group]')
        const index = rows.findIndex((row) => row.closest('[data-row-group]') === currentRow)
        const next =
          event.key === 'ArrowDown'
            ? rows[(index + 1) % rows.length]
            : rows[(index - 1 + rows.length) % rows.length]
        next?.focus()
        return
      }

      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        const group = active.closest('[data-row-group]')
        if (!group) return
        const target = group.querySelector<HTMLElement>(
          event.key === 'ArrowRight' ? '[data-row-action]' : '[data-menu-row]'
        )
        if (target && target !== active) {
          event.preventDefault()
          target.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open])

  // Move focus into the menu when it opens
  useEffect(() => {
    if (!open) return
    menuRef.current?.querySelector<HTMLElement>('[data-menu-row]')?.focus()
  }, [open])

  const typeLabel = businessTypeLabel(currentTenant.business_type)

  return (
    <div className="relative min-w-0 flex-shrink" ref={containerRef}>
      {/* Split control: the name opens the switcher, the ⓘ opens details */}
      <div className="inline-flex items-stretch min-w-0 max-w-[60vw] sm:max-w-sm rounded-md border border-gray-600 bg-gray-700 overflow-hidden">
        <button
          ref={triggerRef}
          type="button"
          onClick={() => setOpen(!open)}
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls="business-switcher-menu"
          aria-label={`Current business: ${currentTenant.name}. Switch business`}
          className="inline-flex items-center gap-2 min-w-0 pl-2 pr-2 py-1.5 text-white hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white"
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

        <span aria-hidden="true" className="w-px bg-gray-600 flex-shrink-0" />

        <button
          type="button"
          onClick={() => {
            setOpen(false)
            onOpenDetails(currentTenant)
          }}
          aria-label={`Details for ${currentTenant.name}`}
          title={`Details for ${currentTenant.name}`}
          className="inline-flex items-center justify-center px-2.5 text-gray-300 hover:text-white hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white flex-shrink-0"
        >
          {infoIcon}
        </button>
      </div>

      {open && (
        <div
          ref={menuRef}
          id="business-switcher-menu"
          role="menu"
          aria-label="Switch business"
          className="absolute left-0 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-50 py-1"
        >
          <div className="px-3 py-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Switch business
          </div>

          {tenants.map((tenant) => {
            const isCurrent = tenant.id === currentTenant.id
            const label = businessTypeLabel(tenant.business_type)
            return (
              <div
                key={tenant.id}
                data-row-group
                role="none"
                className={`flex items-stretch ${isCurrent ? 'bg-blue-50' : 'hover:bg-gray-100'}`}
              >
                <button
                  type="button"
                  data-menu-row
                  role="menuitemradio"
                  aria-checked={isCurrent}
                  onClick={() => {
                    setOpen(false)
                    if (!isCurrent) onSelect(tenant)
                    else triggerRef.current?.focus()
                  }}
                  className="flex-1 flex items-center gap-2.5 px-3 min-h-[44px] py-2 text-left min-w-0 focus:outline-none focus:bg-gray-200"
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

                <button
                  type="button"
                  data-row-action
                  role="menuitem"
                  tabIndex={-1}
                  onClick={() => {
                    setOpen(false)
                    onOpenDetails(tenant)
                  }}
                  aria-label={`Details for ${tenant.name}`}
                  title={`Details for ${tenant.name}`}
                  className="inline-flex items-center justify-center w-11 flex-shrink-0 text-gray-400 hover:text-gray-700 hover:bg-gray-200 focus:outline-none focus:bg-gray-200 focus:text-gray-700"
                >
                  {infoIcon}
                </button>
              </div>
            )
          })}

          <div role="separator" className="border-t border-gray-200 mt-1" />

          <Link
            to="/businesses"
            data-menu-row
            role="menuitem"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 px-3 min-h-[44px] py-2 text-sm text-gray-700 hover:bg-gray-100 focus:outline-none focus:bg-gray-200"
          >
            <svg className="h-5 w-5 flex-shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            Manage businesses
          </Link>
        </div>
      )}
    </div>
  )
}
