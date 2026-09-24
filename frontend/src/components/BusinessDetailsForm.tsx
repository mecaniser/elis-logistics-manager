import { useEffect, useState } from 'react'
import { tenantsApi, Tenant, BankAccount } from '../services/api'

const BUSINESS_TYPES = [
  { value: 'logistics', label: 'Logistics (Transportation)' },
  { value: 'tech', label: 'Tech (IT Services/Consulting)' },
  { value: 'real_estate', label: 'Real Estate (Rentals)' },
]

interface BusinessDetailsFormProps {
  business: Tenant
  onSaved: (updated: Tenant) => void
  onCancel: () => void
  onError: (message: string) => void
  /** Rendered into the drawer footer so the actions stay pinned. */
  renderActions: (actions: { saving: boolean; onSave: () => void; onCancel: () => void }) => void
}

const inputClass =
  'w-full rounded-md border border-gray-300 px-2.5 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
const labelClass = 'block text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-1'

function emptyToUndefined(value: string): string | undefined {
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

/**
 * Editing a business's details lives with viewing them, per business, so the
 * same information is never spread across two separate places.
 */
export default function BusinessDetailsForm({
  business,
  onSaved,
  onCancel,
  onError,
  renderActions,
}: BusinessDetailsFormProps) {
  const [form, setForm] = useState({
    name: business.name || '',
    legal_name: business.legal_name || '',
    business_type: business.business_type || 'logistics',
    ein: business.ein || '',
    is_active: business.is_active,
    email: business.email || '',
    phone: business.phone || '',
    address: business.address || '',
    city: business.city || '',
    state: business.state || '',
    zip_code: business.zip_code || '',
    notes: business.notes || '',
  })
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>(business.bank_accounts || [])
  const [saving, setSaving] = useState(false)

  const set = (field: keyof typeof form, value: string | boolean) =>
    setForm((prev) => ({ ...prev, [field]: value }))

  const updateAccount = (index: number, field: keyof BankAccount, value: string) =>
    setBankAccounts((prev) =>
      prev.map((account, i) => (i === index ? { ...account, [field]: value } : account))
    )

  const handleSave = async () => {
    if (!form.name.trim()) {
      onError('Business name is required')
      return
    }
    try {
      setSaving(true)
      const cleanedAccounts = bankAccounts.filter(
        (a) => a.bank_name?.trim() || a.account_number?.trim() || a.routing_number?.trim()
      )
      const response = await tenantsApi.updateTenant(business.id, {
        name: form.name.trim(),
        legal_name: emptyToUndefined(form.legal_name),
        business_type: form.business_type,
        ein: emptyToUndefined(form.ein),
        is_active: form.is_active,
        email: emptyToUndefined(form.email),
        phone: emptyToUndefined(form.phone),
        address: emptyToUndefined(form.address),
        city: emptyToUndefined(form.city),
        state: emptyToUndefined(form.state),
        zip_code: emptyToUndefined(form.zip_code),
        notes: emptyToUndefined(form.notes),
        bank_accounts: cleanedAccounts.length > 0 ? cleanedAccounts : undefined,
      })
      onSaved(response.data)
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Could not save changes')
    } finally {
      setSaving(false)
    }
  }

  // Keep the pinned footer actions in sync with save state
  useEffect(() => {
    renderActions({ saving, onSave: handleSave, onCancel })
  }, [saving, form, bankAccounts])

  return (
    <div className="px-4 sm:px-6 py-4 space-y-5">
      <section>
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Business Identity</h3>
        <div className="space-y-3">
          <div>
            <label className={labelClass} htmlFor="bd-name">Business Name</label>
            <input id="bd-name" className={inputClass} value={form.name}
              onChange={(e) => set('name', e.target.value)} />
          </div>
          <div>
            <label className={labelClass} htmlFor="bd-legal">Legal Name</label>
            <input id="bd-legal" className={inputClass} value={form.legal_name}
              onChange={(e) => set('legal_name', e.target.value)} />
          </div>
          <div>
            <label className={labelClass} htmlFor="bd-ein">EIN</label>
            <input id="bd-ein" className={`${inputClass} font-mono`} value={form.ein}
              placeholder="12-3456789" onChange={(e) => set('ein', e.target.value)} />
          </div>
          <div>
            <label className={labelClass} htmlFor="bd-type">Business Type</label>
            <select id="bd-type" className={inputClass} value={form.business_type}
              onChange={(e) => set('business_type', e.target.value)}>
              {BUSINESS_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={form.is_active}
              onChange={(e) => set('is_active', e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            Active
          </label>
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Contact</h3>
        <div className="space-y-3">
          <div>
            <label className={labelClass} htmlFor="bd-email">Email</label>
            <input id="bd-email" type="email" className={inputClass} value={form.email}
              onChange={(e) => set('email', e.target.value)} />
          </div>
          <div>
            <label className={labelClass} htmlFor="bd-phone">Phone</label>
            <input id="bd-phone" className={inputClass} value={form.phone}
              onChange={(e) => set('phone', e.target.value)} />
          </div>
          <div>
            <label className={labelClass} htmlFor="bd-address">Street Address</label>
            <input id="bd-address" className={inputClass} value={form.address}
              onChange={(e) => set('address', e.target.value)} />
          </div>
          <div className="grid grid-cols-6 gap-2">
            <div className="col-span-3">
              <label className={labelClass} htmlFor="bd-city">City</label>
              <input id="bd-city" className={inputClass} value={form.city}
                onChange={(e) => set('city', e.target.value)} />
            </div>
            <div className="col-span-1">
              <label className={labelClass} htmlFor="bd-state">State</label>
              <input id="bd-state" className={inputClass} value={form.state}
                onChange={(e) => set('state', e.target.value)} />
            </div>
            <div className="col-span-2">
              <label className={labelClass} htmlFor="bd-zip">ZIP</label>
              <input id="bd-zip" className={inputClass} value={form.zip_code}
                onChange={(e) => set('zip_code', e.target.value)} />
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900">Bank Accounts</h3>
          <button type="button"
            onClick={() => setBankAccounts([...bankAccounts, { bank_name: '', account_number: '', routing_number: '', account_type: 'checking' }])}
            className="text-xs font-medium text-blue-600 hover:text-blue-800 px-2 py-1 rounded hover:bg-blue-50">
            + Add account
          </button>
        </div>
        {bankAccounts.length === 0 ? (
          <p className="text-sm text-gray-500">No bank accounts on file.</p>
        ) : (
          <div className="space-y-3">
            {bankAccounts.map((account, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Account {index + 1}
                  </span>
                  <button type="button"
                    onClick={() => setBankAccounts(bankAccounts.filter((_, i) => i !== index))}
                    className="text-xs font-medium text-red-600 hover:text-red-800 px-2 py-1 rounded hover:bg-red-50">
                    Remove
                  </button>
                </div>
                <input className={inputClass} placeholder="Bank name" value={account.bank_name || ''}
                  onChange={(e) => updateAccount(index, 'bank_name', e.target.value)} />
                <select className={inputClass} value={account.account_type || 'checking'}
                  onChange={(e) => updateAccount(index, 'account_type', e.target.value)}>
                  <option value="checking">Checking</option>
                  <option value="savings">Savings</option>
                </select>
                <input className={`${inputClass} font-mono`} placeholder="Account number"
                  value={account.account_number || ''}
                  onChange={(e) => updateAccount(index, 'account_number', e.target.value)} />
                <input className={`${inputClass} font-mono`} placeholder="Routing number"
                  value={account.routing_number || ''}
                  onChange={(e) => updateAccount(index, 'routing_number', e.target.value)} />
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <label className={labelClass} htmlFor="bd-notes">Notes</label>
        <textarea id="bd-notes" rows={3} className={inputClass} value={form.notes}
          onChange={(e) => set('notes', e.target.value)} />
      </section>
    </div>
  )
}
