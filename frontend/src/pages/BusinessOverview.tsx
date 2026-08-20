import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { tenantsApi, Tenant, BankAccount } from '../services/api'
import { useTenant } from '../contexts/TenantContext'
import Toast from '../components/Toast'

const BUSINESS_TYPE_LABELS: Record<string, string> = {
  logistics: 'Logistics (Transportation)',
  tech: 'Tech (IT Services/Consulting)',
  real_estate: 'Real Estate (Rentals)',
}

async function copyToClipboard(value: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value)
      return true
    }
  } catch {
    // fall through to legacy path below
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = value
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}

interface CopyFieldProps {
  label: string
  value?: string | null
  /** Value placed on the clipboard when it differs from what is displayed */
  copyValue?: string
  /** Render as a masked secret with a show/hide toggle */
  sensitive?: boolean
  href?: string
  mono?: boolean
  onCopied: (label: string, ok: boolean) => void
}

function CopyField({ label, value, copyValue, sensitive, href, mono, onCopied }: CopyFieldProps) {
  const [revealed, setRevealed] = useState(false)
  const [justCopied, setJustCopied] = useState(false)

  const hasValue = !!value && value.trim().length > 0
  const clipboardValue = copyValue ?? value ?? ''

  const masked = hasValue && sensitive && !revealed
    ? `${'•'.repeat(Math.max(0, value!.length - 4))}${value!.slice(-4)}`
    : value

  const handleCopy = async () => {
    const ok = await copyToClipboard(clipboardValue)
    if (ok) {
      setJustCopied(true)
      setTimeout(() => setJustCopied(false), 1500)
    }
    onCopied(label, ok)
  }

  return (
    <div className="py-3 border-b border-gray-100 last:border-b-0">
      <dt className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{label}</dt>
      <dd className="mt-1 flex items-start gap-2">
        {hasValue ? (
          <>
            <span
              className={`flex-1 text-sm text-gray-900 break-words ${mono || sensitive ? 'font-mono' : ''}`}
            >
              {href && !sensitive ? (
                <a href={href} className="text-blue-600 hover:text-blue-800 hover:underline">
                  {masked}
                </a>
              ) : (
                masked
              )}
            </span>
            {sensitive && (
              <button
                type="button"
                onClick={() => setRevealed(!revealed)}
                className="flex-shrink-0 text-xs font-medium text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
              >
                {revealed ? 'Hide' : 'Show'}
              </button>
            )}
            <button
              type="button"
              onClick={handleCopy}
              title={`Copy ${label}`}
              aria-label={`Copy ${label}`}
              className={`flex-shrink-0 inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded border transition-colors ${
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
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy
                </>
              )}
            </button>
          </>
        ) : (
          <span className="text-sm text-gray-400 italic">Not set</span>
        )}
      </dd>
    </div>
  )
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 sm:p-6">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
      <dl className="mt-2">{children}</dl>
    </div>
  )
}

export default function BusinessOverview() {
  const { currentTenant, loading: tenantLoading } = useTenant()
  const [business, setBusiness] = useState<Tenant | null>(currentTenant)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error'; isVisible: boolean }>({
    message: '',
    type: 'success',
    isVisible: false,
  })

  useEffect(() => {
    if (!currentTenant) return

    // Show what the switcher already knows, then refresh from the API
    setBusiness(currentTenant)
    let cancelled = false

    const refresh = async () => {
      try {
        setLoading(true)
        const response = await tenantsApi.getTenant(currentTenant.id)
        if (!cancelled) {
          setBusiness(response.data)
          setError(null)
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'Could not refresh business details')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    refresh()
    return () => {
      cancelled = true
    }
  }, [currentTenant?.id])

  const handleCopied = (label: string, ok: boolean) => {
    setToast({
      message: ok ? `${label} copied to clipboard` : `Could not copy ${label}`,
      type: ok ? 'success' : 'error',
      isVisible: true,
    })
  }

  if (tenantLoading && !business) {
    return <div className="text-center py-12 text-gray-500">Loading business details...</div>
  }

  if (!business) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
        <p className="text-gray-600">No business selected.</p>
        <Link to="/businesses" className="mt-3 inline-block text-blue-600 hover:text-blue-800 font-medium">
          Manage businesses
        </Link>
      </div>
    )
  }

  const cityStateZip = [business.city, business.state].filter(Boolean).join(', ')
  const cityStateZipLine = [cityStateZip, business.zip_code].filter(Boolean).join(' ')
  const fullAddress = [business.address, cityStateZipLine].filter(Boolean).join(', ')
  const bankAccounts: BankAccount[] = business.bank_accounts || []

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Overview</h1>
          <p className="text-sm text-gray-500 mt-1">
            Business details for {business.name}. Click Copy on any field to put it on your clipboard.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {loading && <span className="text-xs text-gray-400">Refreshing...</span>}
          <Link
            to="/businesses"
            className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Edit details
          </Link>
        </div>
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 text-sm rounded-md px-4 py-3">
          {error}. Showing the most recently loaded details.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        <Section title="Business Identity">
          <CopyField label="Business Name" value={business.name} onCopied={handleCopied} />
          <CopyField label="Legal Name" value={business.legal_name} onCopied={handleCopied} />
          <CopyField
            label="EIN"
            value={business.ein}
            mono
            onCopied={handleCopied}
          />
          <CopyField
            label="Business Type"
            value={BUSINESS_TYPE_LABELS[business.business_type] || business.business_type}
            onCopied={handleCopied}
          />
          <div className="py-3 border-b border-gray-100 last:border-b-0">
            <dt className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</dt>
            <dd className="mt-1">
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  business.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                }`}
              >
                {business.is_active ? 'Active' : 'Inactive'}
              </span>
            </dd>
          </div>
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
      </div>

      <Section
        title="Bank Accounts"
        subtitle={
          bankAccounts.length > 0
            ? 'Account and routing numbers are hidden until you choose Show. Copy works either way.'
            : undefined
        }
      >
        {bankAccounts.length === 0 ? (
          <p className="py-3 text-sm text-gray-500">
            No bank accounts on file.{' '}
            <Link to="/businesses" className="text-blue-600 hover:text-blue-800">
              Add one
            </Link>
            .
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
            {bankAccounts.map((account, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <h3 className="text-sm font-semibold text-gray-900 truncate">
                      {account.bank_name || `Account ${index + 1}`}
                    </h3>
                    {account.bank_name && (
                      <button
                        type="button"
                        onClick={async () => handleCopied('Bank Name', await copyToClipboard(account.bank_name))}
                        title="Copy Bank Name"
                        aria-label="Copy Bank Name"
                        className="flex-shrink-0 text-gray-400 hover:text-gray-700 p-1 rounded hover:bg-gray-100"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
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
                  <CopyField label="Account Number" value={account.account_number} sensitive onCopied={handleCopied} />
                  <CopyField label="Routing Number" value={account.routing_number} sensitive onCopied={handleCopied} />
                </dl>
              </div>
            ))}
          </div>
        )}
      </Section>

      {business.notes && (
        <Section title="Notes">
          <div className="py-3">
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{business.notes}</p>
          </div>
        </Section>
      )}

      <Toast
        message={toast.message}
        type={toast.type}
        isVisible={toast.isVisible}
        onClose={() => setToast({ ...toast, isVisible: false })}
      />
    </div>
  )
}
