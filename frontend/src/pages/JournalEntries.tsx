import { useEffect, useState } from 'react'
import { accountingApi, JournalEntry as JournalEntryType, ChartOfAccount } from '../services/api'
import { useTenant } from '../contexts/TenantContext'

export default function JournalEntries() {
  const { currentTenant } = useTenant()
  const [entries, setEntries] = useState<JournalEntryType[]>([])
  const [accounts, setAccounts] = useState<ChartOfAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [referenceTypeFilter, setReferenceTypeFilter] = useState('')

  useEffect(() => {
    setEntries([])
    setAccounts([])
    loadEntries()
    loadAccounts()
  }, [startDate, endDate, referenceTypeFilter, currentTenant?.id])

  const loadEntries = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await accountingApi.getJournalEntries(
        startDate || undefined,
        endDate || undefined,
        referenceTypeFilter || undefined
      )
      setEntries(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load journal entries')
    } finally {
      setLoading(false)
    }
  }

  const loadAccounts = async () => {
    try {
      const response = await accountingApi.getChartOfAccounts()
      setAccounts(response.data)
    } catch (err) {
      // Ignore errors loading accounts
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(amount)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const getAccountName = (accountId: number) => {
    const account = accounts.find((a) => a.id === accountId)
    return account ? `${account.code} - ${account.name}` : `Account ${accountId}`
  }

  if (loading && entries.length === 0) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading journal entries...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Journal Entries</h1>
      </div>

      <div className="bg-white p-4 rounded-lg shadow space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Reference Type
            </label>
            <select
              value={referenceTypeFilter}
              onChange={(e) => setReferenceTypeFilter(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="">All Types</option>
              <option value="settlement">Settlement</option>
              <option value="repair">Repair</option>
              <option value="manual">Manual</option>
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={() => {
                setStartDate('')
                setEndDate('')
                setReferenceTypeFilter('')
              }}
              className="w-full px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 text-sm"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {entries.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-500">No journal entries found.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {entries.map((entry) => {
            const totalDebits = entry.lines.reduce((sum, line) => sum + line.debit, 0)
            const totalCredits = entry.lines.reduce((sum, line) => sum + line.credit, 0)

            return (
              <div key={entry.id} className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-6 py-4 bg-gray-50 border-b">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">
                        Entry #{entry.id}
                      </h3>
                      <p className="text-sm text-gray-500">
                        Date: {formatDate(entry.entry_date)}
                        {entry.reference_type && (
                          <span className="ml-4">
                            {entry.reference_type} #{entry.reference_id}
                          </span>
                        )}
                      </p>
                      {entry.description && (
                        <p className="text-sm text-gray-600 mt-1">{entry.description}</p>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-gray-500">Total Debits</div>
                      <div className="text-lg font-semibold text-green-600">
                        {formatCurrency(totalDebits)}
                      </div>
                      <div className="text-sm text-gray-500 mt-2">Total Credits</div>
                      <div className="text-lg font-semibold text-red-600">
                        {formatCurrency(totalCredits)}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Account
                        </th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Debit
                        </th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Credit
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Description
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {entry.lines.map((line) => (
                        <tr key={line.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {getAccountName(line.account_id)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">
                            {line.debit > 0 ? formatCurrency(line.debit) : '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">
                            {line.credit > 0 ? formatCurrency(line.credit) : '-'}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-500">
                            {line.description || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

