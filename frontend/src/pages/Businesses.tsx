import { useEffect, useState } from 'react'
import { tenantsApi, Tenant } from '../services/api'
import Toast from '../components/Toast'
import ConfirmModal from '../components/ConfirmModal'
import { useTenant } from '../contexts/TenantContext'

const BUSINESS_TYPES = [
  { value: 'logistics', label: 'Logistics (Transportation)' },
  { value: 'tech', label: 'Tech (IT Services/Consulting)' },
  { value: 'real_estate', label: 'Real Estate (Rentals)' },
]

export default function Businesses() {
  const { loadTenants } = useTenant()
  const [businesses, setBusinesses] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingBusiness, setEditingBusiness] = useState<Tenant | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    business_type: 'logistics',
    is_active: true,
    ein: '',
    legal_name: '',
    address: '',
    city: '',
    state: '',
    zip_code: '',
    phone: '',
    email: '',
    bank_accounts: [] as Array<{ bank_name: string; account_number: string; routing_number: string; account_type?: string }>,
    notes: '',
  })
  const [businessToDelete, setBusinessToDelete] = useState<number | null>(null)
  const [businessToDeleteName, setBusinessToDeleteName] = useState<string>('')
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean }>({
    message: '',
    type: 'info',
    isVisible: false,
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadBusinesses()
  }, [])

  const loadBusinesses = async () => {
    try {
      setLoading(true)
      const response = await tenantsApi.getTenants()
      setBusinesses(response.data)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load businesses')
      showToast('Failed to load businesses', 'error')
    } finally {
      setLoading(false)
    }
  }

  const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info') => {
    setToast({ message, type, isVisible: true })
  }

  const addBankAccount = () => {
    setFormData({
      ...formData,
      bank_accounts: [...formData.bank_accounts, { bank_name: '', account_number: '', routing_number: '', account_type: 'checking' }]
    })
  }

  const removeBankAccount = (index: number) => {
    setFormData({
      ...formData,
      bank_accounts: formData.bank_accounts.filter((_, i) => i !== index)
    })
  }

  const updateBankAccount = (index: number, field: string, value: string) => {
    const updated = [...formData.bank_accounts]
    updated[index] = { ...updated[index], [field]: value }
    setFormData({ ...formData, bank_accounts: updated })
  }

  const handleCreate = async () => {
    if (!formData.name.trim()) {
      showToast('Business name is required', 'error')
      return
    }

    try {
      setSaving(true)
      await tenantsApi.createTenant({
        name: formData.name.trim(),
        business_type: formData.business_type,
        is_active: formData.is_active,
        ein: formData.ein.trim() || undefined,
        legal_name: formData.legal_name.trim() || undefined,
        address: formData.address.trim() || undefined,
        city: formData.city.trim() || undefined,
        state: formData.state.trim() || undefined,
        zip_code: formData.zip_code.trim() || undefined,
        phone: formData.phone.trim() || undefined,
        email: formData.email.trim() || undefined,
        bank_accounts: formData.bank_accounts.length > 0 ? formData.bank_accounts : undefined,
        notes: formData.notes.trim() || undefined,
      })
      showToast('Business created successfully', 'success')
      setShowForm(false)
      resetForm()
      await loadBusinesses()
      await loadTenants() // Refresh the tenant context so new business appears in switcher
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to create business', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdate = async () => {
    if (!editingBusiness) return
    if (!formData.name.trim()) {
      showToast('Business name is required', 'error')
      return
    }

    try {
      setSaving(true)
      await tenantsApi.updateTenant(editingBusiness.id, {
        name: formData.name.trim(),
        business_type: formData.business_type,
        is_active: formData.is_active,
        ein: formData.ein.trim() || undefined,
        legal_name: formData.legal_name.trim() || undefined,
        address: formData.address.trim() || undefined,
        city: formData.city.trim() || undefined,
        state: formData.state.trim() || undefined,
        zip_code: formData.zip_code.trim() || undefined,
        phone: formData.phone.trim() || undefined,
        email: formData.email.trim() || undefined,
        bank_accounts: formData.bank_accounts.length > 0 ? formData.bank_accounts : undefined,
        notes: formData.notes.trim() || undefined,
      })
      showToast('Business updated successfully', 'success')
      setEditingBusiness(null)
      setShowForm(false)
      resetForm()
      await loadBusinesses()
      await loadTenants() // Refresh the tenant context
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to update business', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!businessToDelete) return

    try {
      await tenantsApi.deleteTenant(businessToDelete)
      showToast('Business deleted successfully', 'success')
      setBusinessToDelete(null)
      setBusinessToDeleteName('')
      await loadBusinesses()
      await loadTenants() // Refresh the tenant context
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to delete business', 'error')
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      business_type: 'logistics',
      is_active: true,
      ein: '',
      legal_name: '',
      address: '',
      city: '',
      state: '',
      zip_code: '',
      phone: '',
      email: '',
      bank_accounts: [],
      notes: '',
    })
    setEditingBusiness(null)
  }

  const startEdit = (business: Tenant) => {
    setEditingBusiness(business)
    setFormData({
      name: business.name,
      business_type: business.business_type,
      is_active: business.is_active,
      ein: business.ein || '',
      legal_name: business.legal_name || '',
      address: business.address || '',
      city: business.city || '',
      state: business.state || '',
      zip_code: business.zip_code || '',
      phone: business.phone || '',
      email: business.email || '',
      bank_accounts: business.bank_accounts || [],
      notes: business.notes || '',
    })
    setShowForm(true)
  }

  const cancelEdit = () => {
    setShowForm(false)
    resetForm()
  }

  if (loading) return <div className="text-center py-8">Loading businesses...</div>
  if (error) return <div className="text-center py-8 text-red-600">{error}</div>

  return (
    <div>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div className="flex items-baseline gap-2">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Businesses</h1>
          <span className="text-xl text-gray-500 font-medium">({businesses.length})</span>
        </div>
        {!showForm && (
          <button
            onClick={() => {
              resetForm()
              setShowForm(true)
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>Add Business</span>
          </button>
        )}
      </div>

      {showForm && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            {editingBusiness ? 'Edit Business' : 'Create New Business'}
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Business Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Elis Pro Tech, Elis Real Estate"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Business Type *
              </label>
              <div className="flex gap-2">
                <select
                  value={BUSINESS_TYPES.find(t => t.value === formData.business_type) ? formData.business_type : 'custom'}
                  onChange={(e) => {
                    if (e.target.value === 'custom') {
                      setFormData({ ...formData, business_type: '' })
                    } else {
                      setFormData({ ...formData, business_type: e.target.value })
                    }
                  }}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {BUSINESS_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                  <option value="custom">Other (Custom)</option>
                </select>
                {(!BUSINESS_TYPES.find(t => t.value === formData.business_type)) && (
                  <input
                    type="text"
                    value={formData.business_type}
                    onChange={(e) => setFormData({ ...formData, business_type: e.target.value })}
                    placeholder="Enter custom business type"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                )}
              </div>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="is_active" className="ml-2 block text-sm text-gray-700">
                Active
              </label>
            </div>

            {/* Business Details Section */}
            <div className="border-t border-gray-200 pt-4 mt-4">
              <h3 className="text-md font-semibold text-gray-900 mb-4">Business Details</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    EIN (Employer Identification Number)
                  </label>
                  <input
                    type="text"
                    value={formData.ein}
                    onChange={(e) => setFormData({ ...formData, ein: e.target.value })}
                    placeholder="12-3456789"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Legal Name
                  </label>
                  <input
                    type="text"
                    value={formData.legal_name}
                    onChange={(e) => setFormData({ ...formData, legal_name: e.target.value })}
                    placeholder="Legal business name"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Address
                  </label>
                  <input
                    type="text"
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    placeholder="Street address"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    City
                  </label>
                  <input
                    type="text"
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    placeholder="City"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    State
                  </label>
                  <input
                    type="text"
                    value={formData.state}
                    onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                    placeholder="State"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    ZIP Code
                  </label>
                  <input
                    type="text"
                    value={formData.zip_code}
                    onChange={(e) => setFormData({ ...formData, zip_code: e.target.value })}
                    placeholder="12345"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Phone
                  </label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    placeholder="(555) 123-4567"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email
                  </label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="business@example.com"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Bank Accounts Section */}
              <div className="mt-6">
                <div className="flex justify-between items-center mb-3">
                  <label className="block text-sm font-medium text-gray-700">
                    Bank Accounts
                  </label>
                  <button
                    type="button"
                    onClick={addBankAccount}
                    className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Add Bank Account
                  </button>
                </div>
                {formData.bank_accounts.map((account, index) => (
                  <div key={index} className="border border-gray-200 rounded-md p-4 mb-3">
                    <div className="flex justify-between items-center mb-3">
                      <h4 className="text-sm font-medium text-gray-700">Bank Account {index + 1}</h4>
                      <button
                        type="button"
                        onClick={() => removeBankAccount(index)}
                        className="text-red-600 hover:text-red-700"
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Bank Name</label>
                        <input
                          type="text"
                          value={account.bank_name}
                          onChange={(e) => updateBankAccount(index, 'bank_name', e.target.value)}
                          placeholder="Bank name"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Account Type</label>
                        <select
                          value={account.account_type || 'checking'}
                          onChange={(e) => updateBankAccount(index, 'account_type', e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                        >
                          <option value="checking">Checking</option>
                          <option value="savings">Savings</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Account Number</label>
                        <input
                          type="text"
                          value={account.account_number}
                          onChange={(e) => updateBankAccount(index, 'account_number', e.target.value)}
                          placeholder="Account number"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Routing Number</label>
                        <input
                          type="text"
                          value={account.routing_number}
                          onChange={(e) => updateBankAccount(index, 'routing_number', e.target.value)}
                          placeholder="Routing number"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                        />
                      </div>
                    </div>
                  </div>
                ))}
                {formData.bank_accounts.length === 0 && (
                  <p className="text-sm text-gray-500 italic">No bank accounts added. Click "Add Bank Account" to add one.</p>
                )}
              </div>

              {/* Notes Section */}
              <div className="mt-6">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notes
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  placeholder="Additional notes about this business..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex gap-2 pt-4 border-t border-gray-200">
              <button
                onClick={editingBusiness ? handleUpdate : handleCreate}
                disabled={saving}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : editingBusiness ? 'Update' : 'Create'}
              </button>
              <button
                onClick={cancelEdit}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white shadow rounded-lg overflow-hidden">
        {businesses.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <p className="mb-4">No businesses found.</p>
            <button
              onClick={() => {
                resetForm()
                setShowForm(true)
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Create Your First Business
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {businesses.map((business) => (
                  <tr key={business.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{business.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">
                        {BUSINESS_TYPES.find((t) => t.value === business.business_type)?.label || business.business_type}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          business.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {business.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(business.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => startEdit(business)}
                          className="text-blue-600 hover:text-blue-900"
                          title="Edit"
                        >
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => {
                            setBusinessToDelete(business.id)
                            setBusinessToDeleteName(business.name)
                          }}
                          className="text-red-600 hover:text-red-900"
                          title="Delete"
                        >
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmModal
        isOpen={businessToDelete !== null}
        title="Delete Business"
        message={`Are you sure you want to delete "${businessToDeleteName}"? This action cannot be undone.`}
        confirmText="Delete"
        cancelText="Cancel"
        onConfirm={handleDelete}
        onClose={() => {
          setBusinessToDelete(null)
          setBusinessToDeleteName('')
        }}
        type="danger"
      />

      <Toast
        message={toast.message}
        type={toast.type}
        isVisible={toast.isVisible}
        onClose={() => setToast({ ...toast, isVisible: false })}
      />
    </div>
  )
}

