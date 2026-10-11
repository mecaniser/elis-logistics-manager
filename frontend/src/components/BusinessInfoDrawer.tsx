import { apiError } from '../utils/apiError'
import { useEffect, useRef, useState } from 'react'
import { tenantsApi, Tenant, BankAccount } from '../services/api'
import Toast from './Toast'
import { tenantColor } from '../utils/tenantAppearance'
import BusinessDetailsForm from './BusinessDetailsForm'
import { useTenant } from '../contexts/tenantState'
import BankNumberField from './BankNumberField'
import { copyText as copyToClipboard } from '../utils/copyText'

const BUSINESS_TYPE_LABELS: Record<string, string> = {
  logistics: 'Logistics (Transportation)',
  tech: 'Tech (IT Services/Consulting)',
  real_estate: 'Real Estate (Rentals)',
}

const copyIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
  </svg>
)

interface CopyFieldProps {
  label: string
  value?: string | null
  href?: string
  mono?: boolean
  onCopied: (label: string, ok: boolean) => void
}

function CopyField({ label, value, href, mono, onCopied }: CopyFieldProps) {
  const [justCopied, setJustCopied] = useState(false)

  const hasValue = !!value && value.trim().length > 0

  const handleCopy = async () => {
    const ok = await copyToClipboard(value ?? '')
    if (ok) {
      setJustCopied(true)
      setTimeout(() => setJustCopied(false), 1500)
    }
    onCopied(label, ok)
  }

  return (
    <div className="py-2.5 border-b border-gray-100 last:border-b-0">
      <dt className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{label}</dt>
      <dd className="mt-0.5 flex items-start gap-2">
        {hasValue ? (
          <>
            <span className={`flex-1 text-sm text-gray-900 break-words ${mono ? 'font-mono' : ''}`}>
              {href ? (
                <a href={href} className="text-blue-600 hover:text-blue-800 hover:underline">
                  {value}
                </a>
              ) : (
                value
              )}
            </span>
            <button
              type="button"
              onClick={handleCopy}
              title={`Copy ${label}`}
              aria-label={`Copy ${label}`}
              className={`flex-shrink-0 inline-flex items-center gap-1 text-xs font-medium px-1.5 py-1 rounded border transition-colors ${
                justCopied
                  ? 'border-green-300 bg-green-50 text-green-700'
                  : 'border-gray-300 bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              {justCopied ? (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Copied
                </>
              ) : (
                <>
                  {copyIcon}
                  Copy
                </>
              )}
            </button>
          </>
        ) : (
          <span className="text-sm text-gray-500 italic">Not set</span>
        )}
      </dd>
    </div>
  )
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="px-4 sm:px-6 py-4 border-b border-gray-200 last:border-b-0">
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      <dl className="mt-1">{children}</dl>
    </div>
  )
}

interface BusinessInfoDrawerProps {
  isOpen: boolean
  onClose: () => void
  tenant: Tenant | null
}

export default function BusinessInfoDrawer({ isOpen, onClose, tenant }: BusinessInfoDrawerProps) {
  // Unmount sensitive state and cancel pending reads on close or business change.
  if (!isOpen || !tenant) return null
  return <BusinessInfoDrawerContent key={tenant.id} onClose={onClose} tenant={tenant} />
}

function BusinessInfoDrawerContent({ onClose, tenant }: { onClose: () => void; tenant: Tenant }) {
  const { loadTenants } = useTenant()
  const [editBankAccounts, setEditBankAccounts] = useState<BankAccount[] | null>(null)
  const editing = editBankAccounts !== null
  const [loadingEdit, setLoadingEdit] = useState(false)
  const editRequest = useRef<AbortController | null>(null)
  useEffect(() => () => editRequest.current?.abort(), [])
  const [formActions, setFormActions] = useState<{
    saving: boolean
    onSave: () => void
    onCancel: () => void
  } | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const [business, setBusiness] = useState<Tenant | null>(tenant)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error'; isVisible: boolean }>({
    message: '',
    type: 'success',
    isVisible: false,
  })

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    closeButtonRef.current?.focus()
    return () => opener?.focus()
  }, [])

  // Lock body scroll while the drawer is open, matching Modal's behavior
  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [])

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  // Show what the tenant switcher already knows, then refresh from the API
  useEffect(() => {
    setBusiness(tenant)
    let cancelled = false

    const refresh = async () => {
      try {
        const response = await tenantsApi.getTenant(tenant.id)
        if (!cancelled) {
          setBusiness(response.data)
          setError(null)
        }
      } catch (caught: unknown) {
        const err = apiError(caught)
        if (!cancelled) {
          setError(err.response?.data?.detail || 'Could not refresh business details')
        }
      }
    }

    refresh()
    return () => {
      cancelled = true
    }
  }, [tenant])

  const handleCopied = (label: string, ok: boolean) => {
    setToast({
      message: ok ? `${label} copied to clipboard` : `Could not copy ${label}`,
      type: ok ? 'success' : 'error',
      isVisible: true,
    })
  }

  const startEdit = async () => {
    if (editRequest.current) return
    const controller = new AbortController()
    editRequest.current = controller
    setLoadingEdit(true)
    try {
      const response = await tenantsApi.getBankAccountsForEdit(tenant.id, controller.signal)
      if (!controller.signal.aborted) setEditBankAccounts(response.data.bank_accounts)
    } catch {
      if (!controller.signal.aborted) {
        setToast({ message: 'Could not access bank details for editing. Try again.', type: 'error', isVisible: true })
      }
    } finally {
      if (!controller.signal.aborted) {
        editRequest.current = null
        setLoadingEdit(false)
      }
    }
  }

  if (!business) return null

  const cityStateZip = [business.city, business.state].filter(Boolean).join(', ')
  const cityStateZipLine = [cityStateZip, business.zip_code].filter(Boolean).join(' ')
  const fullAddress = [business.address, cityStateZipLine].filter(Boolean).join(', ')
  const bankAccounts = business.bank_accounts || []

  return (
    <>
      <div className="fixed inset-0 z-[60]">
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
          onClick={onClose}
        />
        <div
          className="fixed inset-y-0 right-0 w-full max-w-md bg-white shadow-xl flex flex-col animate-slide-in"
          role="dialog"
          aria-modal="true"
          aria-label="Business details"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-3 px-4 sm:px-6 py-4 border-b border-gray-200 flex-shrink-0">
            <div className="flex items-start gap-2.5 min-w-0">
              <span
                aria-hidden="true"
                className="h-5 w-5 rounded flex-shrink-0 mt-0.5"
                style={{ backgroundColor: tenantColor(business.id) }}
              />
              <div className="min-w-0">
                <h2 className="text-base font-semibold text-gray-900 truncate">{business.name}</h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  {BUSINESS_TYPE_LABELS[business.business_type] || business.business_type}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                  business.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                }`}
              >
                {business.is_active ? 'Active' : 'Inactive'}
              </span>
              <button
                ref={closeButtonRef}
                onClick={onClose}
                className="inline-flex items-center justify-center h-11 w-11 -mr-2 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <span className="sr-only">Close</span>
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {error && (
            <div className="bg-yellow-50 border-b border-yellow-200 text-yellow-800 text-xs px-4 sm:px-6 py-2 flex-shrink-0">
              {error}. Showing the most recently loaded details.
            </div>
          )}

          {/* Body */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {editing ? (
              <BusinessDetailsForm
                business={business}
                initialBankAccounts={editBankAccounts}
                onSaved={async (updated) => {
                  setBusiness(updated)
                  setEditBankAccounts(null)
                  setToast({ message: 'Business details saved', type: 'success', isVisible: true })
                  // Refresh the switcher so a renamed or retyped business updates there too
                  await loadTenants()
                }}
                onCancel={() => setEditBankAccounts(null)}
                onError={(message) => setToast({ message, type: 'error', isVisible: true })}
                renderActions={setFormActions}
              />
            ) : (
            <>
            <Section title="Business Identity">
              <CopyField label="Business Name" value={business.name} onCopied={handleCopied} />
              <CopyField label="Legal Name" value={business.legal_name} onCopied={handleCopied} />
              <CopyField label="EIN" value={business.ein} mono onCopied={handleCopied} />
            </Section>

            <Section title="Contact">
              <CopyField
                label="Email"
                value={business.email}
                href={business.email ? `mailto:${business.email}` : undefined}
                onCopied={handleCopied}
              />
              <CopyField
                label="Phone"
                value={business.phone}
                href={business.phone ? `tel:${business.phone}` : undefined}
                onCopied={handleCopied}
              />
              <CopyField label="Street Address" value={business.address} onCopied={handleCopied} />
              <CopyField label="City / State / ZIP" value={cityStateZipLine} onCopied={handleCopied} />
              <CopyField label="Full Address" value={fullAddress} onCopied={handleCopied} />
            </Section>

            <Section
              title="Bank Accounts"
              subtitle={
                bankAccounts.length > 0
                  ? 'Account and routing numbers are hidden until you choose Show. Copy works either way.'
                  : undefined
              }
            >
              {bankAccounts.length === 0 ? (
                <p className="py-2.5 text-sm text-gray-500">No bank accounts on file.</p>
              ) : (
                <div className="space-y-3 mt-2">
                  {bankAccounts.map((account, index) => (
                    <div key={`${business.id}:${index}:${business.updated_at}`} className="border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <h4 className="text-sm font-semibold text-gray-900 truncate">
                            {account.bank_name || `Account ${index + 1}`}
                          </h4>
                          {account.bank_name && (
                            <button
                              type="button"
                              onClick={async () => handleCopied('Bank Name', await copyToClipboard(account.bank_name))}
                              title="Copy Bank Name"
                              aria-label="Copy Bank Name"
                              className="flex-shrink-0 text-gray-400 hover:text-gray-700 p-1 rounded hover:bg-gray-100"
                            >
                              {copyIcon}
                            </button>
                          )}
                        </div>
                        {account.account_type && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 capitalize flex-shrink-0">
                            {account.account_type}
                          </span>
                        )}
                      </div>
                      <dl className="mt-1">
                        <BankNumberField tenantId={business.id} accountIndex={index} field="account_number" label="Account Number" maskedValue={account.account_number_masked} onCopied={handleCopied} />
                        <BankNumberField tenantId={business.id} accountIndex={index} field="routing_number" label="Routing Number" maskedValue={account.routing_number_masked} onCopied={handleCopied} />
                      </dl>
                    </div>
                  ))}
                </div>
              )}
            </Section>

            {business.notes && (
              <Section title="Notes">
                <p className="py-2.5 text-sm text-gray-700 whitespace-pre-wrap">{business.notes}</p>
              </Section>
            )}
            </>
            )}
          </div>

          {/* Footer */}
          <div className="bg-gray-50 px-4 sm:px-6 py-3 border-t border-gray-200 flex-shrink-0">
            {editing ? (
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => formActions?.onCancel()}
                  disabled={formActions?.saving}
                  className="flex-1 inline-flex items-center justify-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => formActions?.onSave()}
                  disabled={formActions?.saving}
                  className="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
                >
                  {formActions?.saving ? 'Saving...' : 'Save changes'}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => void startEdit()}
                disabled={loadingEdit}
                className="inline-flex items-center justify-center w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                {loadingEdit ? 'Loading…' : 'Edit details'}
              </button>
            )}
          </div>
        </div>
      </div>

      <Toast
        message={toast.message}
        type={toast.type}
        isVisible={toast.isVisible}
        onClose={() => setToast({ ...toast, isVisible: false })}
      />
    </>
  )
}
