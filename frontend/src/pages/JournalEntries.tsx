import { useEffect, useState } from 'react'
import { accountingApi, JournalEntry as JournalEntryType, ChartOfAccount, trucksApi, Truck } from '../services/api'
import { useTenant } from '../contexts/TenantContext'
import InfoPanel from '../components/InfoPanel'
import AccountingTooltip from '../components/AccountingTooltip'

export default function JournalEntries() {
  const { currentTenant } = useTenant()
  const [entries, setEntries] = useState<JournalEntryType[]>([])
  const [accounts, setAccounts] = useState<ChartOfAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [referenceTypeFilter, setReferenceTypeFilter] = useState('')
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [selectedTruckId, setSelectedTruckId] = useState<number | null>(null)
  
  const isLSLogistics = currentTenant?.name.toLowerCase() === 'ls logistics'
  
  // Load trucks for logistics businesses
  useEffect(() => {
    if (currentTenant?.business_type === 'logistics') {
      loadTrucks()
    } else {
      setTrucks([])
      setSelectedTruckId(null)
    }
  }, [currentTenant?.id, currentTenant?.business_type])
  
  const loadTrucks = async () => {
    try {
      const response = await trucksApi.getAll()
      setTrucks(response.data)
    } catch (err) {
      console.error('Failed to load trucks:', err)
    }
  }

  useEffect(() => {
    setEntries([])
    setAccounts([])
    loadEntries()
    loadAccounts()
  }, [startDate, endDate, referenceTypeFilter, selectedTruckId, currentTenant?.id])

  const loadEntries = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await accountingApi.getJournalEntries(
        startDate || undefined,
        endDate || undefined,
        referenceTypeFilter || undefined,
        undefined,
        selectedTruckId || undefined
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
      const response = await accountingApi.getChartOfAccounts(undefined, undefined, selectedTruckId || undefined)
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
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-2xl font-bold text-gray-900">
          Journal Entries
          {selectedTruckId && trucks.find(t => t.id === selectedTruckId) && (
            <span className="text-lg font-normal text-gray-600 ml-2">
              - {trucks.find(t => t.id === selectedTruckId)?.name}
            </span>
          )}
        </h1>
      </div>

      <InfoPanel
        title="What are Journal Entries?"
        content={
          <div className="space-y-3">
            <p>
              <strong>Journal Entries</strong> are the foundation of double-entry bookkeeping. Every financial transaction is recorded as a journal entry with at least two parts: a debit and a credit.
            </p>
            <div>
              <p className="font-semibold mb-2">The Golden Rule:</p>
              <p className="mb-2">For every transaction, <strong>total debits must equal total credits</strong>. This keeps your books balanced.</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><strong>Debit (Dr):</strong> Increases assets and expenses; decreases liabilities, equity, and revenue</li>
                <li><strong>Credit (Cr):</strong> Increases liabilities, equity, and revenue; decreases assets and expenses</li>
              </ul>
            </div>
            <div>
              <p className="font-semibold mb-2">Example:</p>
              <p className="mb-1">When you receive payment for a settlement:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Debit: Accounts Receivable (money owed to you)</li>
                <li>Credit: Operating Revenue (money earned)</li>
              </ul>
            </div>
            <p>
              <strong>Why it matters:</strong> Journal entries create an audit trail of every transaction, making it easy to track where money came from and where it went. They automatically generate when you create settlements or repairs, but you can also create manual entries for other transactions.
            </p>
          </div>
        }
      />

      <div className="bg-white p-4 rounded-lg shadow space-y-4">
        <div className={`grid grid-cols-1 ${isLSLogistics && trucks.length > 0 ? 'sm:grid-cols-2 lg:grid-cols-5' : 'sm:grid-cols-2 lg:grid-cols-4'} gap-4`}>
          {/* Vehicle Selector (LS Logistics only) */}
          {isLSLogistics && trucks.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Vehicle
              </label>
              <select
                value={selectedTruckId || ''}
                onChange={(e) => setSelectedTruckId(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="">Select Vehicle</option>
                {trucks.map((truck) => (
                  <option key={truck.id} value={truck.id}>
                    {truck.name} ({truck.vehicle_type})
                  </option>
                ))}
              </select>
            </div>
          )}
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
                <div className="px-4 sm:px-6 py-4 bg-gray-50 border-b">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-gray-900">
                        Entry #{entry.id}
                      </h3>
                      <p className="text-sm text-gray-500 break-words">
                        Date: {formatDate(entry.entry_date)}
                        {entry.reference_type && (
                          <span className="ml-2 sm:ml-4">
                            {entry.reference_type} #{entry.reference_id}
                          </span>
                        )}
                      </p>
                      {entry.description && (
                        <p className="text-sm text-gray-600 mt-1 break-words">{entry.description}</p>
                      )}
                    </div>
                    <div className="text-left sm:text-right flex-shrink-0">
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
                <div className="overflow-x-auto -mx-4 sm:mx-0">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Account
                        </th>
                        <th className="px-3 sm:px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                          <span className="flex items-center justify-end">
                            <AccountingTooltip
                              term="Debit"
                              description="Increases assets and expenses, decreases liabilities and equity. Think: money going IN to assets or expenses."
                            >
                              Debit
                            </AccountingTooltip>
                          </span>
                        </th>
                        <th className="px-3 sm:px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                          <span className="flex items-center justify-end">
                            <AccountingTooltip
                              term="Credit"
                              description="Increases liabilities, equity, and revenue, decreases assets and expenses. Think: money coming FROM revenue or going OUT to pay liabilities."
                            >
                              Credit
                            </AccountingTooltip>
                          </span>
                        </th>
                        <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Description
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {entry.lines.map((line) => (
                        <tr key={line.id} className="hover:bg-gray-50">
                          <td className="px-3 sm:px-6 py-4 text-sm text-gray-900">
                            <span className="truncate block">{getAccountName(line.account_id)}</span>
                          </td>
                          <td className="px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">
                            {line.debit > 0 ? formatCurrency(line.debit) : '-'}
                          </td>
                          <td className="px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">
                            {line.credit > 0 ? formatCurrency(line.credit) : '-'}
                          </td>
                          <td className="px-3 sm:px-6 py-4 text-sm text-gray-500">
                            <span className="truncate block">{line.description || '-'}</span>
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

