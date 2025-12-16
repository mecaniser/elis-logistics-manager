import { useEffect, useState } from 'react'
import { accountingApi, BalanceSheet as BalanceSheetType, trucksApi, Truck } from '../services/api'
import { useTenant } from '../contexts/TenantContext'
import InfoPanel from '../components/InfoPanel'

export default function BalanceSheet() {
  const { currentTenant } = useTenant()
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheetType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split('T')[0])
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [selectedTruckId, setSelectedTruckId] = useState<number | null>(null)
  
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
    setBalanceSheet(null)
    loadBalanceSheet()
  }, [asOfDate, selectedTruckId, currentTenant?.id])

  const loadBalanceSheet = async () => {
    try {
      setLoading(true)
      setError(null)
      // For LS Logistics, truck_id is required
      const isLSLogistics = currentTenant?.name.toLowerCase() === 'ls logistics'
      if (isLSLogistics && !selectedTruckId) {
        setError('Please select a vehicle to view the balance sheet')
        setLoading(false)
        return
      }
      const truckId = isLSLogistics ? selectedTruckId : undefined
      const response = await accountingApi.getBalanceSheet(asOfDate, truckId)
      setBalanceSheet(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load balance sheet')
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

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading balance sheet...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Balance Sheet</h1>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      </div>
    )
  }

  if (!balanceSheet) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Balance Sheet</h1>
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-500">No balance sheet data available.</p>
        </div>
      </div>
    )
  }

  const isLSLogistics = currentTenant?.name.toLowerCase() === 'ls logistics'

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-2xl font-bold text-gray-900">
          Balance Sheet
          {selectedTruckId && trucks.find(t => t.id === selectedTruckId) && (
            <span className="text-lg font-normal text-gray-600 ml-2">
              - {trucks.find(t => t.id === selectedTruckId)?.name}
            </span>
          )}
        </h1>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          {/* Vehicle Selector (LS Logistics only) */}
          {isLSLogistics && trucks.length > 0 && (
            <div>
              <label className="text-sm font-medium text-gray-700 mr-2">
                Vehicle:
              </label>
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
            </div>
          )}
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-gray-700">
              As of Date:
            </label>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
        </div>
      </div>

      <InfoPanel
        title="What is a Balance Sheet?"
        content={
          <div className="space-y-3">
            <p>
              A <strong>Balance Sheet</strong> is a snapshot of your business's financial position at a specific point in time. It shows what you own, what you owe, and what you're worth.
            </p>
            <div>
              <p className="font-semibold mb-2">The Fundamental Equation:</p>
              <p className="text-lg font-bold mb-2">Assets = Liabilities + Equity</p>
              <p className="mb-2">This equation must always balance, which is why it's called a "balance sheet."</p>
            </div>
            <div>
              <p className="font-semibold mb-2">Three Main Sections:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><strong>Assets:</strong> Everything your business owns that has value (Cash, Vehicles, Equipment, Accounts Receivable). These are resources that can generate income.</li>
                <li><strong>Liabilities:</strong> Everything your business owes (Loans, Accounts Payable, Credit Cards). These are obligations you must pay.</li>
                <li><strong>Equity:</strong> Your ownership stake in the business. It's what's left after subtracting liabilities from assets. Includes Owner Equity and Retained Earnings (profits kept in the business).</li>
              </ul>
            </div>
            <div>
              <p className="font-semibold mb-2">Example:</p>
              <p className="mb-1">If you have:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>$50,000 in assets (cash, vehicles, etc.)</li>
                <li>$20,000 in liabilities (loans, payables)</li>
                <li>Then your equity = $30,000 (what you actually own)</li>
              </ul>
            </div>
            <p>
              <strong>Why it matters:</strong> The balance sheet helps you understand your business's financial health, see if you can pay your debts, and track how your equity changes over time. Investors and lenders use it to assess your business's value and creditworthiness.
            </p>
            {isLSLogistics && (
              <p className="mt-2 pt-2 border-t border-blue-300">
                <strong>Note:</strong> For LS Logistics, each truck and trailer has its own separate balance sheet. Select a vehicle above to view its financial position.
              </p>
            )}
          </div>
        }
      />

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            Balance Sheet as of {new Date(balanceSheet.as_of_date).toLocaleDateString()}
          </h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Assets */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Assets</h3>
              <div className="space-y-2">
                <div className="flex justify-between py-2 border-b">
                  <span className="text-gray-700">Cash</span>
                  <span className="font-medium">{formatCurrency(balanceSheet.assets.cash)}</span>
                </div>
                <div className="flex justify-between py-2 border-b">
                  <span className="text-gray-700">Accounts Receivable</span>
                  <span className="font-medium">
                    {formatCurrency(balanceSheet.assets.accounts_receivable)}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b">
                  <span className="text-gray-700">Vehicles</span>
                  <span className="font-medium">
                    {formatCurrency(balanceSheet.assets.vehicles)}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b">
                  <span className="text-gray-700">Less: Accumulated Depreciation</span>
                  <span className="font-medium text-red-600">
                    ({formatCurrency(balanceSheet.assets.accumulated_depreciation)})
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b-2 border-gray-400">
                  <span className="text-gray-700">Net Vehicles</span>
                  <span className="font-medium">
                    {formatCurrency(balanceSheet.assets.net_vehicles)}
                  </span>
                </div>
                <div className="flex justify-between py-2 mt-4 border-t-2 border-gray-400">
                  <span className="text-lg font-semibold text-gray-900">Total Assets</span>
                  <span className="text-lg font-semibold text-gray-900">
                    {formatCurrency(balanceSheet.assets.total)}
                  </span>
                </div>
              </div>
            </div>

            {/* Liabilities & Equity */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Liabilities</h3>
              <div className="space-y-2 mb-6">
                <div className="flex justify-between py-2 border-b">
                  <span className="text-gray-700">Accounts Payable</span>
                  <span className="font-medium">
                    {formatCurrency(balanceSheet.liabilities.accounts_payable)}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b-2 border-gray-400">
                  <span className="text-gray-700">Loans Payable</span>
                  <span className="font-medium">
                    {formatCurrency(balanceSheet.liabilities.loans_payable)}
                  </span>
                </div>
                <div className="flex justify-between py-2 mt-4 border-t-2 border-gray-400">
                  <span className="text-lg font-semibold text-gray-900">Total Liabilities</span>
                  <span className="text-lg font-semibold text-gray-900">
                    {formatCurrency(balanceSheet.liabilities.total)}
                  </span>
                </div>
              </div>

              <h3 className="text-lg font-semibold text-gray-900 mb-4">Equity</h3>
              <div className="space-y-2">
                <div className="flex justify-between py-2 border-b">
                  <span className="text-gray-700">Owner Equity</span>
                  <span className="font-medium">
                    {formatCurrency(balanceSheet.equity.owner_equity)}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b-2 border-gray-400">
                  <span className="text-gray-700">Retained Earnings</span>
                  <span className="font-medium">
                    {formatCurrency(balanceSheet.equity.retained_earnings)}
                  </span>
                </div>
                <div className="flex justify-between py-2 mt-4 border-t-2 border-gray-400">
                  <span className="text-lg font-semibold text-gray-900">Total Equity</span>
                  <span className="text-lg font-semibold text-gray-900">
                    {formatCurrency(balanceSheet.equity.total)}
                  </span>
                </div>
                <div className="flex justify-between py-2 mt-6 border-t-4 border-gray-600">
                  <span className="text-xl font-bold text-gray-900">
                    Total Liabilities & Equity
                  </span>
                  <span className="text-xl font-bold text-gray-900">
                    {formatCurrency(balanceSheet.total_liabilities_and_equity)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

