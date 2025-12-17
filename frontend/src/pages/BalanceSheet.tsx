import { useEffect, useState } from 'react'
import { accountingApi, BalanceSheet as BalanceSheetType } from '../services/api'
import { useTenant } from '../contexts/TenantContext'
import InfoPanel from '../components/InfoPanel'
import AccountingTooltip from '../components/AccountingTooltip'

export default function BalanceSheet() {
  const { currentTenant } = useTenant()
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheetType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split('T')[0])

  useEffect(() => {
    setBalanceSheet(null)
    loadBalanceSheet()
  }, [asOfDate, currentTenant?.id])

  const loadBalanceSheet = async () => {
    try {
      setLoading(true)
      setError(null)
      // Always shows total for all business assets
      const response = await accountingApi.getBalanceSheet(asOfDate)
      setBalanceSheet(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load balance sheet')
    } finally {
      setLoading(false)
    }
  }

  const formatCurrency = (amount: number) => {
    const safeAmount = isNaN(amount) || amount === null || amount === undefined ? 0 : amount
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(safeAmount)
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
      <div className="flex flex-col gap-4">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Balance Sheet</h1>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
            <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
              As of Date:
            </label>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="flex-1 sm:flex-none px-3 py-2 border border-gray-300 rounded-md text-sm min-w-0"
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
          </div>
        }
      />

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            Balance Sheet as of {new Date(balanceSheet.as_of_date).toLocaleDateString()}
          </h2>
        </div>
        <div className="p-4 sm:p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
            {/* Assets */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Assets</h3>
              <div className="space-y-2">
                <div className="flex justify-between items-center py-2 border-b gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Cash"
                      description="Money in bank accounts and on hand. The most liquid asset - you can use it immediately."
                    >
                      <span className="truncate">Cash</span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium whitespace-nowrap flex-shrink-0">{formatCurrency(balanceSheet.assets.cash)}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Accounts Receivable"
                      description="Money customers owe you for work completed but not yet paid. It's an asset because you expect to receive payment."
                    >
                      <span className="truncate">Accounts Receivable</span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium whitespace-nowrap flex-shrink-0">
                    {formatCurrency(balanceSheet.assets.accounts_receivable)}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Vehicles"
                      description="The original purchase cost of your vehicles. This is what you paid for them, not their current value."
                    >
                      <span className="truncate">Vehicles</span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium whitespace-nowrap flex-shrink-0">
                    {formatCurrency(balanceSheet.assets.vehicles)}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Accumulated Depreciation"
                      description="Total amount your vehicles have decreased in value over time due to wear and use. This reduces the value of your vehicles on the balance sheet."
                    >
                      <span className="truncate">Less: Accumulated Depreciation</span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium text-red-600 whitespace-nowrap flex-shrink-0">
                    ({formatCurrency(balanceSheet.assets.accumulated_depreciation)})
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b-2 border-gray-400 gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Net Vehicles"
                      description="Vehicles minus accumulated depreciation. This is the current book value (what they're worth on paper) of your vehicles."
                    >
                      <span className="truncate">Net Vehicles</span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium whitespace-nowrap flex-shrink-0">
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
                <div className="flex justify-between items-center py-2 border-b gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Accounts Payable"
                      description="Money you owe to vendors, suppliers, or contractors for goods or services received but not yet paid. Short-term debts."
                    >
                      <span className="truncate">Accounts Payable</span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium whitespace-nowrap flex-shrink-0">
                    {formatCurrency(balanceSheet.liabilities.accounts_payable)}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b-2 border-gray-400 gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Loans Payable"
                      description="Outstanding balance on loans you've taken out (like vehicle loans). The principal amount you still owe, not including future interest."
                    >
                      <span className="truncate">Loans Payable</span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium whitespace-nowrap flex-shrink-0">
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
                <div className="flex justify-between items-center py-2 border-b gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Owner Equity"
                      description="Initial investment you put into the business plus any additional capital contributions. This is your ownership stake in the company."
                    >
                      <span className="truncate">Owner Equity</span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium whitespace-nowrap flex-shrink-0">
                    {formatCurrency(balanceSheet.equity.owner_equity)}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b-2 border-gray-400 gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Retained Earnings"
                      description="Cumulative profits (or losses) from all previous periods that you've kept in the business instead of taking as distributions. Increases with profits, decreases with losses."
                    >
                      <span className="truncate">Retained Earnings</span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium whitespace-nowrap flex-shrink-0">
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

