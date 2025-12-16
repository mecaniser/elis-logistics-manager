import { useEffect, useState } from 'react'
import { accountingApi, ChartOfAccount as ChartOfAccountType, trucksApi, Truck } from '../services/api'
import { useTenant } from '../contexts/TenantContext'
import ConfirmModal from '../components/ConfirmModal'
import InfoPanel from '../components/InfoPanel'
import AccountingTooltip from '../components/AccountingTooltip'

// Helper function to get account descriptions
const getAccountDescription = (accountName: string, accountType: string): string => {
  const nameLower = accountName.toLowerCase()
  
  // Asset accounts
  if (accountType === 'Asset') {
    if (nameLower.includes('cash')) return 'Money in bank accounts and on hand. Most liquid asset.'
    if (nameLower.includes('receivable')) return 'Money customers owe you for completed work.'
    if (nameLower.includes('vehicle')) return 'The purchase cost of your trucks and trailers.'
    if (nameLower.includes('depreciation')) return 'Total decrease in vehicle value over time due to wear and use.'
  }
  
  // Liability accounts
  if (accountType === 'Liability') {
    if (nameLower.includes('payable')) return 'Money you owe to vendors, suppliers, or contractors.'
    if (nameLower.includes('loan')) return 'Outstanding balance on loans you\'ve taken out.'
  }
  
  // Equity accounts
  if (accountType === 'Equity') {
    if (nameLower.includes('owner')) return 'Your initial investment and capital contributions to the business.'
    if (nameLower.includes('retained')) return 'Cumulative profits kept in the business instead of distributed.'
  }
  
  // Revenue accounts
  if (accountType === 'Revenue') {
    return 'Money earned from business operations (e.g., settlements from completed loads).'
  }
  
  // Expense accounts
  if (accountType === 'Expense') {
    if (nameLower.includes('fuel')) return 'Cost of diesel/gasoline for vehicles.'
    if (nameLower.includes('driver') || nameLower.includes('payroll')) return 'Wages and fees related to driver compensation.'
    if (nameLower.includes('insurance')) return 'Vehicle and business insurance premiums.'
    if (nameLower.includes('maintenance') || nameLower.includes('repair') || nameLower.includes('service')) return 'Vehicle maintenance and repair costs.'
    if (nameLower.includes('interest')) return 'Interest payments on loans.'
    if (nameLower.includes('dispatch')) return 'Fees paid to dispatch services or brokers.'
    return 'Operating expense for business operations.'
  }
  
  return `${accountType} account used to categorize financial transactions.`
}

export default function ChartOfAccounts() {
  const { currentTenant } = useTenant()
  const [accounts, setAccounts] = useState<ChartOfAccountType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [accountTypeFilter, setAccountTypeFilter] = useState<string>('')
  const [showResetModal, setShowResetModal] = useState(false)
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
    setAccounts([])
    loadAccounts()
  }, [accountTypeFilter, selectedTruckId, currentTenant?.id])

  const loadAccounts = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await accountingApi.getChartOfAccounts(
        accountTypeFilter || undefined,
        true,
        selectedTruckId || undefined
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

  const resetAccounts = async () => {
    try {
      setLoading(true)
      setError(null)
      await accountingApi.resetChartOfAccounts()
      await loadAccounts()
      setShowResetModal(false)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset chart of accounts')
    } finally {
      setLoading(false)
    }
  }

  const accountTypes = ['Asset', 'Liability', 'Equity', 'Revenue', 'Expense']

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
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-2xl font-bold text-gray-900">
          Chart of Accounts
          {selectedTruckId && trucks.find(t => t.id === selectedTruckId) && (
            <span className="text-lg font-normal text-gray-600 ml-2">
              - {trucks.find(t => t.id === selectedTruckId)?.name}
            </span>
          )}
        </h1>
        <div className="flex flex-col sm:flex-row gap-2">
          {/* Vehicle Selector (LS Logistics only) */}
          {isLSLogistics && trucks.length > 0 && (
            <select
              value={selectedTruckId || ''}
              onChange={(e) => setSelectedTruckId(e.target.value ? parseInt(e.target.value) : null)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="">Select Vehicle</option>
              {trucks.map((truck) => (
                <option key={truck.id} value={truck.id}>
                  {truck.name} ({truck.vehicle_type})
                </option>
              ))}
            </select>
          )}
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
          {accounts.length > 0 && (
            <button
              onClick={() => setShowResetModal(true)}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
            >
              Reset Accounts
            </button>
          )}
          <button
            onClick={initializeAccounts}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
          >
            {accounts.length > 0 ? 'Re-initialize Accounts' : 'Initialize Accounts'}
          </button>
        </div>
      </div>

      <ConfirmModal
        isOpen={showResetModal}
        onClose={() => setShowResetModal(false)}
        onConfirm={resetAccounts}
        title="Reset Chart of Accounts"
        message={`Are you sure you want to reset all accounts for ${currentTenant?.name}? This will delete all accounts and any associated journal entries. This action cannot be undone.`}
        confirmText="Reset All Accounts"
        cancelText="Cancel"
        type="danger"
      />

      <InfoPanel
        title="What is a Chart of Accounts?"
        content={
          <div className="space-y-3">
            <p>
              A <strong>Chart of Accounts</strong> is a complete list of all accounts used by your business to organize and categorize financial transactions. Think of it as a filing system for your money.
            </p>
            <div>
              <p className="font-semibold mb-2">Account Types:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><strong>Assets:</strong> What you own (Cash, Vehicles, Equipment, Accounts Receivable)</li>
                <li><strong>Liabilities:</strong> What you owe (Loans, Accounts Payable, Credit Cards)</li>
                <li><strong>Equity:</strong> Your ownership stake (Owner Equity, Retained Earnings)</li>
                <li><strong>Revenue:</strong> Money coming in (Operating Revenue, Sales)</li>
                <li><strong>Expenses:</strong> Money going out (Fuel, Repairs, Salaries, Rent)</li>
              </ul>
            </div>
            <p>
              <strong>Why it matters:</strong> Properly categorized accounts help you understand where your money comes from and where it goes, making it easier to track profitability, prepare taxes, and make business decisions.
            </p>
          </div>
        }
      />

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
                <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                  <AccountingTooltip
                    term={`${type}s`}
                    description={
                      type === 'Asset' ? 'What you own (Cash, Vehicles, Equipment). Resources that have value.'
                      : type === 'Liability' ? 'What you owe (Loans, Accounts Payable). Debts and obligations.'
                      : type === 'Equity' ? 'Your ownership stake in the business. What\'s left after subtracting liabilities from assets.'
                      : type === 'Revenue' ? 'Money coming into your business from operations. Income earned.'
                      : type === 'Expense' ? 'Money going out of your business. Costs of operations.'
                      : `${type} accounts used to categorize transactions.`
                    }
                  >
                    {type}s
                  </AccountingTooltip>
                </h2>
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
                          <span className="flex items-center">
                            <AccountingTooltip
                              term={account.name}
                              description={getAccountDescription(account.name, account.account_type)}
                            >
                              {account.name}
                            </AccountingTooltip>
                          </span>
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

