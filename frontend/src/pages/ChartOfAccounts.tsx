import { useEffect, useState } from 'react'
import { accountingApi, ChartOfAccount as ChartOfAccountType } from '../services/api'

export default function ChartOfAccounts() {
  const [accounts, setAccounts] = useState<ChartOfAccountType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [accountTypeFilter, setAccountTypeFilter] = useState<string>('')

  useEffect(() => {
    loadAccounts()
  }, [accountTypeFilter])

  const loadAccounts = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await accountingApi.getChartOfAccounts(
        accountTypeFilter || undefined,
        true
      )
      setAccounts(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load chart of accounts')
    } finally {
      setLoading(false)
    }
  }

  const initializeAccounts = async () => {
    try {
      setLoading(true)
      setError(null)
      await accountingApi.initializeChartOfAccounts()
      await loadAccounts()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to initialize chart of accounts')
    } finally {
      setLoading(false)
    }
  }

  const accountTypes = ['Asset', 'Liability', 'Equity', 'Revenue', 'Expense']

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount)
  }

  const groupedAccounts = accounts.reduce((acc, account) => {
    if (!acc[account.account_type]) {
      acc[account.account_type] = []
    }
    acc[account.account_type].push(account)
    return acc
  }, {} as Record<string, ChartOfAccountType[]>)

  if (loading && accounts.length === 0) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading chart of accounts...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Chart of Accounts</h1>
        <div className="flex gap-2">
          <select
            value={accountTypeFilter}
            onChange={(e) => setAccountTypeFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">All Types</option>
            {accountTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <button
            onClick={initializeAccounts}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
          >
            Initialize Accounts
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {accounts.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-500 mb-4">No accounts found.</p>
          <button
            onClick={initializeAccounts}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Initialize Standard Accounts
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedAccounts).map(([type, typeAccounts]) => (
            <div key={type} className="bg-white rounded-lg shadow overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b">
                <h2 className="text-lg font-semibold text-gray-900">{type}s</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Code
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Name
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {typeAccounts.map((account) => (
                      <tr key={account.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">
                          {account.code}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {account.name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          {account.is_active ? (
                            <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                              Active
                            </span>
                          ) : (
                            <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                              Inactive
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

