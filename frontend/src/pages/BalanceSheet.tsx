import { useEffect, useState } from 'react'
import { accountingApi, BalanceSheet as BalanceSheetType } from '../services/api'

export default function BalanceSheet() {
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheetType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split('T')[0])

  useEffect(() => {
    loadBalanceSheet()
  }, [asOfDate])

  const loadBalanceSheet = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await accountingApi.getBalanceSheet(asOfDate)
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

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Balance Sheet</h1>
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

