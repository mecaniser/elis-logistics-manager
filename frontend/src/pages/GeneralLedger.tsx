import { useEffect, useState } from 'react'
import { accountingApi, ChartOfAccount, GeneralLedger } from '../services/api'
import { useTenant } from '../contexts/TenantContext'
import InfoPanel from '../components/InfoPanel'

export default function GeneralLedgerPage() {
  const { currentTenant } = useTenant()
  const [accounts, setAccounts] = useState<ChartOfAccount[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)
  const [generalLedger, setGeneralLedger] = useState<GeneralLedger | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  useEffect(() => {
    loadAccounts()
  }, [currentTenant?.id])

  useEffect(() => {
    if (selectedAccountId) {
      loadGeneralLedger()
    } else {
      setGeneralLedger(null)
    }
  }, [selectedAccountId, startDate, endDate, currentTenant?.id])

  const loadAccounts = async () => {
    try {
      const response = await accountingApi.getChartOfAccounts()
      setAccounts(response.data)
      if (response.data.length > 0 && !selectedAccountId) {
        setSelectedAccountId(response.data[0].id)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load accounts')
    }
  }

  const loadGeneralLedger = async () => {
    if (!selectedAccountId) return
    
    try {
      setLoading(true)
      setError(null)
      const response = await accountingApi.getGeneralLedger(
        selectedAccountId,
        startDate || undefined,
        endDate || undefined
      )
      setGeneralLedger(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load general ledger')
    } finally {
      setLoading(false)
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

  const handleExport = async (format: 'csv' | 'excel') => {
    if (!generalLedger) return
    
    try {
      const response = await accountingApi.exportGeneralLedger(
        selectedAccountId!,
        format,
        startDate || undefined,
        endDate || undefined
      )
      const blob = new Blob([response.data], { 
        type: format === 'excel' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : 'text/csv'
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `general_ledger_${generalLedger.account_code}_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : 'csv'}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err: any) {
      console.error('Export failed:', err)
      alert('Failed to export general ledger')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">General Ledger</h1>
        {generalLedger && (
          <div className="flex gap-2">
            <button
              onClick={() => handleExport('csv')}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 text-sm"
            >
              Export CSV
            </button>
            <button
              onClick={() => handleExport('excel')}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
            >
              Export Excel
            </button>
          </div>
        )}
      </div>

      <InfoPanel
        title="What is a General Ledger?"
        content={
          <div className="space-y-3">
            <p>
              A <strong>General Ledger</strong> is a complete record of all transactions for a specific account, showing the chronological history of debits, credits, and running balances.
            </p>
            <p>
              <strong>Use the General Ledger to:</strong>
            </p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>Review all transactions for a specific account</li>
              <li>Track account activity over time</li>
              <li>Verify account balances</li>
              <li>Audit transactions</li>
            </ul>
          </div>
        }
      />

      <div className="bg-white p-4 rounded-lg shadow space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Account
            </label>
            <select
              value={selectedAccountId || ''}
              onChange={(e) => setSelectedAccountId(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="">Select Account</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.code} - {account.name}
                </option>
              ))}
            </select>
          </div>
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
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-500">Loading general ledger...</div>
        </div>
      )}

      {generalLedger && !loading && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-4 sm:px-6 py-4 bg-gray-50 border-b">
            <h2 className="text-base sm:text-lg font-semibold text-gray-900">
              {generalLedger.account_code} - {generalLedger.account_name}
            </h2>
            <p className="text-xs sm:text-sm text-gray-500 mt-1">
              Account Type: {generalLedger.account_type}
            </p>
          </div>
          <div className="p-4 sm:p-6">
            <div className="mb-3 sm:mb-4 flex flex-col sm:flex-row sm:justify-between gap-2 sm:gap-0">
              <div>
                <span className="text-xs sm:text-sm text-gray-500">Starting Balance: </span>
                <span className="font-medium text-xs sm:text-sm text-gray-900">{formatCurrency(generalLedger.start_balance)}</span>
              </div>
              <div>
                <span className="text-xs sm:text-sm text-gray-500">Ending Balance: </span>
                <span className="font-medium text-xs sm:text-sm text-gray-900">{formatCurrency(generalLedger.end_balance)}</span>
              </div>
            </div>
            {/* Mobile/Tablet Card Layout */}
            <div className="lg:hidden divide-y divide-gray-200">
              {generalLedger.entries.map((entry, idx) => (
                <div key={idx} className="px-4 py-3 hover:bg-gray-50">
                  <div className="space-y-2">
                    <div className="flex justify-between items-start gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-gray-500 uppercase mb-1">Date</div>
                        <div className="text-sm text-gray-900">{formatDate(entry.entry_date)}</div>
                      </div>
                      <div className="flex-shrink-0">
                        <div className="text-xs font-medium text-gray-500 uppercase mb-1">Entry ID</div>
                        <div className="text-sm text-gray-500">#{entry.journal_entry_id}</div>
                      </div>
                    </div>
                    {entry.description && (
                      <div>
                        <div className="text-xs font-medium text-gray-500 uppercase mb-1">Description</div>
                        <div className="text-sm text-gray-500 break-words">{entry.description}</div>
                      </div>
                    )}
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <div className="text-xs font-medium text-gray-500 uppercase mb-1">Debit</div>
                        <div className="text-sm text-gray-900">
                          {entry.debit > 0 ? formatCurrency(entry.debit) : '-'}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs font-medium text-gray-500 uppercase mb-1">Credit</div>
                        <div className="text-sm text-gray-900">
                          {entry.credit > 0 ? formatCurrency(entry.credit) : '-'}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs font-medium text-gray-500 uppercase mb-1">Balance</div>
                        <div className="text-sm font-medium text-gray-900">
                          {formatCurrency(entry.running_balance)}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {/* Desktop Table Layout */}
            <div className="hidden lg:block">
              <table className="w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Entry ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Description
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Debit
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Credit
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Balance
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {generalLedger.entries.map((entry, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {formatDate(entry.entry_date)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        #{entry.journal_entry_id}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        <span className="break-words">{entry.description || '-'}</span>
                      </td>
                      <td className="px-6 py-4 text-sm text-right text-gray-900">
                        {entry.debit > 0 ? formatCurrency(entry.debit) : '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-right text-gray-900">
                        {entry.credit > 0 ? formatCurrency(entry.credit) : '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-right font-medium text-gray-900">
                        {formatCurrency(entry.running_balance)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

