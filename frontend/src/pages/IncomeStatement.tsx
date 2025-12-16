import { useEffect, useState } from 'react'
import { accountingApi, IncomeStatement as IncomeStatementType, trucksApi, Truck } from '../services/api'
import { useTenant } from '../contexts/TenantContext'
import InfoPanel from '../components/InfoPanel'
import AccountingTooltip from '../components/AccountingTooltip'

// Helper function to get expense category descriptions
const getExpenseDescription = (category: string): string => {
  const descriptions: Record<string, string> = {
    fuel: 'Cost of diesel/gasoline for your vehicles. One of the largest variable expenses.',
    driver_pay: 'Wages paid to drivers for their work. This is compensation for their time and labor.',
    payroll_fee: 'Fees charged by payroll processing companies or services to handle driver payments.',
    insurance: 'Monthly premiums for vehicle insurance, liability coverage, and other business insurance policies.',
    safety: 'Safety-related expenses including safety training, equipment, and compliance costs.',
    prepass: 'Prepass or toll pass fees for electronic toll collection systems.',
    ifta: 'International Fuel Tax Agreement fees - taxes paid on fuel used across different states.',
    dispatch_fee: 'Fees paid to dispatch services or brokers for finding and coordinating loads.',
    loan_interest: 'Interest payments on vehicle loans or other business loans. Only the interest portion, not principal.',
    truck_parking: 'Costs for parking vehicles at truck stops, terminals, or storage facilities.',
    service_on_truck: 'Regular maintenance, oil changes, tire replacements, and routine vehicle servicing.',
    repairs: 'Unexpected repair costs for fixing vehicle breakdowns, accidents, or mechanical issues.',
    custom: 'Other miscellaneous expenses that don\'t fit into standard categories.',
  }
  return descriptions[category.toLowerCase()] || 'Operating expense for this category.'
}

export default function IncomeStatement() {
  const { currentTenant } = useTenant()
  const [incomeStatement, setIncomeStatement] = useState<IncomeStatementType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [selectedTruckId, setSelectedTruckId] = useState<number | null>(null)
  
  // Default to current month
  const today = new Date()
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1)
  const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0)
  
  const [startDate, setStartDate] = useState(firstDay.toISOString().split('T')[0])
  const [endDate, setEndDate] = useState(lastDay.toISOString().split('T')[0])
  
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
    if (startDate && endDate) {
      setIncomeStatement(null)
      loadIncomeStatement()
    }
  }, [startDate, endDate, selectedTruckId, currentTenant?.id])

  const loadIncomeStatement = async () => {
    if (!startDate || !endDate) return
    
    try {
      setLoading(true)
      setError(null)
      // For LS Logistics, truck_id is required
      const isLSLogistics = currentTenant?.name.toLowerCase() === 'ls logistics'
      if (isLSLogistics && !selectedTruckId) {
        setError('Please select a vehicle to view the income statement')
        setLoading(false)
        return
      }
      const truckId = isLSLogistics ? (selectedTruckId ?? undefined) : (selectedTruckId ?? undefined)
      const response = await accountingApi.getIncomeStatement(
        startDate, 
        endDate, 
        truckId
      )
      setIncomeStatement(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load income statement')
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

  const setDateRange = (range: '1month' | '3months' | '1year') => {
    const today = new Date()
    let start: Date
    let end: Date = new Date(today.getFullYear(), today.getMonth() + 1, 0) // Last day of current month

    switch (range) {
      case '1month':
        // Current month
        start = new Date(today.getFullYear(), today.getMonth(), 1)
        break
      case '3months':
        // Last 3 months (including current month)
        start = new Date(today.getFullYear(), today.getMonth() - 2, 1)
        break
      case '1year':
        // Last 12 months (including current month)
        start = new Date(today.getFullYear(), today.getMonth() - 11, 1)
        break
    }

    setStartDate(start.toISOString().split('T')[0])
    setEndDate(end.toISOString().split('T')[0])
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading income statement...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Income Statement</h1>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      </div>
    )
  }

  if (!incomeStatement) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Income Statement</h1>
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-500">No income statement data available.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">
          <span className="block sm:inline">Income Statement</span>
          {selectedTruckId && trucks.find(t => t.id === selectedTruckId) && (
            <span className="block sm:inline sm:ml-2 text-base sm:text-lg font-normal text-gray-600">
              - {trucks.find(t => t.id === selectedTruckId)?.name}
            </span>
          )}
        </h1>
        <div className="flex flex-col gap-3">
          {/* Vehicle Selector */}
          {currentTenant?.business_type === 'logistics' && trucks.length > 0 && (
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
                Vehicle:
              </label>
              <select
                value={selectedTruckId || ''}
                onChange={(e) => setSelectedTruckId(e.target.value ? parseInt(e.target.value) : null)}
                className="flex-1 sm:flex-none px-3 py-2 border border-gray-300 rounded-md text-sm min-w-0"
                required={isLSLogistics}
              >
                {!isLSLogistics && <option value="">All Vehicles</option>}
                {isLSLogistics && <option value="">Select Vehicle</option>}
                {trucks.map((truck) => (
                  <option key={truck.id} value={truck.id}>
                    {truck.name} ({truck.vehicle_type})
                  </option>
                ))}
              </select>
            </div>
          )}
          {/* Quick Date Selection Buttons */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setDateRange('1month')}
              className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors whitespace-nowrap"
            >
              1 Month
            </button>
            <button
              onClick={() => setDateRange('3months')}
              className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors whitespace-nowrap"
            >
              3 Months
            </button>
            <button
              onClick={() => setDateRange('1year')}
              className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors whitespace-nowrap"
            >
              1 Year
            </button>
          </div>
          {/* Custom Date Inputs */}
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-2">
              <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
                Start:
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="flex-1 sm:flex-none px-3 py-2 border border-gray-300 rounded-md text-sm min-w-0"
              />
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-2">
              <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
                End:
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="flex-1 sm:flex-none px-3 py-2 border border-gray-300 rounded-md text-sm min-w-0"
              />
            </div>
          </div>
        </div>
      </div>

      <InfoPanel
        title="What is an Income Statement?"
        content={
          <div className="space-y-3">
            <p>
              An <strong>Income Statement</strong> (also called Profit & Loss or P&L) shows your business's financial performance over a period of time (month, quarter, or year). It tells you if you made money or lost money.
            </p>
            <div>
              <p className="font-semibold mb-2">The Simple Formula:</p>
              <p className="text-lg font-bold mb-2">Revenue - Expenses = Net Income</p>
            </div>
            <div>
              <p className="font-semibold mb-2">Two Main Sections:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><strong>Revenue:</strong> Money coming into your business (Operating Revenue, Sales, Service Income). This is the "top line."</li>
                <li><strong>Expenses:</strong> Money going out of your business (Fuel, Repairs, Salaries, Rent, Insurance, etc.). These reduce your profit.</li>
              </ul>
            </div>
            <div>
              <p className="font-semibold mb-2">Net Income:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><strong>Positive (Profit):</strong> You made more than you spent - your business is profitable!</li>
                <li><strong>Negative (Loss):</strong> You spent more than you made - you need to reduce expenses or increase revenue.</li>
              </ul>
            </div>
            <div>
              <p className="font-semibold mb-2">Example:</p>
              <p className="mb-1">For the month of January:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Revenue: $50,000</li>
                <li>Expenses: $35,000</li>
                <li>Net Income: $15,000 (profit!)</li>
              </ul>
            </div>
            <p>
              <strong>Why it matters:</strong> The income statement helps you track profitability over time, identify which expenses are highest, and make informed decisions about pricing, cost-cutting, or expansion. It's essential for tax preparation and showing investors how your business performs.
            </p>
            {currentTenant?.business_type === 'logistics' && (
              <p className="mt-2 pt-2 border-t border-blue-300">
                {isLSLogistics ? (
                  <span><strong>Note:</strong> For LS Logistics, each truck and trailer has its own separate income statement. Select a vehicle above to view its financial performance.</span>
                ) : (
                  <span><strong>Tip:</strong> You can filter by individual vehicle to see which trucks or trailers are most profitable!</span>
                )}
              </p>
            )}
          </div>
        }
      />

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            Income Statement
          </h2>
          <p className="text-sm text-gray-500">
            {new Date(incomeStatement.start_date).toLocaleDateString()} -{' '}
            {new Date(incomeStatement.end_date).toLocaleDateString()}
          </p>
        </div>
        <div className="p-4 sm:p-6">
          <div className="max-w-2xl mx-auto">
            {/* Revenue */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Revenue</h3>
              <div className="space-y-2">
                <div className="flex justify-between items-center py-2 border-b gap-2">
                  <span className="text-gray-700 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Operating Revenue"
                      description="Total money earned from your business operations (e.g., settlements from completed loads). This is your 'top line' - all income before expenses."
                    >
                      <span className="truncate">
                        {Object.keys(incomeStatement.revenue).map(key => 
                          key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
                        ).join(', ')}
                      </span>
                    </AccountingTooltip>
                  </span>
                  <span className="font-medium whitespace-nowrap flex-shrink-0">
                    {formatCurrency(incomeStatement.revenue.total)}
                  </span>
                </div>
                <div className="flex justify-between py-2 mt-4 border-t-2 border-gray-400">
                  <span className="text-lg font-semibold text-gray-900 flex items-center">
                    <AccountingTooltip
                      term="Total Revenue"
                      description="Sum of all revenue streams. This is the total amount of money your business earned during this period."
                    >
                      Total Revenue
                    </AccountingTooltip>
                  </span>
                  <span className="text-lg font-semibold text-gray-900">
                    {formatCurrency(incomeStatement.revenue.total)}
                  </span>
                </div>
              </div>
            </div>

            {/* Expenses */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Expenses</h3>
              <div className="space-y-2">
                {Object.entries(incomeStatement.expenses)
                  .filter(([, amount]) => amount > 0)
                  .sort(([, a], [, b]) => b - a) // Sort by amount descending
                  .map(([name, amount]) => {
                    const displayName = name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
                    return (
                      <div key={name} className="flex justify-between items-center py-2 border-b gap-2">
                        <span className="text-gray-700 flex items-center min-w-0 flex-1">
                          <AccountingTooltip
                            term={displayName}
                            description={getExpenseDescription(name)}
                          >
                            <span className="truncate">{displayName}</span>
                          </AccountingTooltip>
                        </span>
                        <span className="font-medium text-red-600 whitespace-nowrap flex-shrink-0">
                          {formatCurrency(amount)}
                        </span>
                      </div>
                    )
                  })}
                <div className="flex justify-between items-center py-2 mt-4 border-t-2 border-gray-400 gap-2">
                  <span className="text-lg font-semibold text-gray-900 flex items-center min-w-0 flex-1">
                    <AccountingTooltip
                      term="Total Expenses"
                      description="Sum of all expenses during this period. This is the total amount of money your business spent."
                    >
                      <span className="truncate">Total Expenses</span>
                    </AccountingTooltip>
                  </span>
                  <span className="text-lg font-semibold text-red-600 whitespace-nowrap flex-shrink-0">
                    {formatCurrency(incomeStatement.total_expenses)}
                  </span>
                </div>
              </div>
            </div>

            {/* Net Income */}
            <div className="mt-6 pt-6 border-t-4 border-gray-600">
              <div className="flex justify-between items-center gap-2">
                <span className="text-xl font-bold text-gray-900 flex items-center min-w-0 flex-1">
                  <AccountingTooltip
                    term="Net Income"
                    description="Revenue minus expenses. Positive = profit (you made money). Negative = loss (you spent more than you earned). This is your 'bottom line'."
                  >
                    <span className="truncate">Net Income</span>
                  </AccountingTooltip>
                </span>
                <span
                  className={`text-xl font-bold whitespace-nowrap flex-shrink-0 ${
                    incomeStatement.net_income >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {formatCurrency(incomeStatement.net_income)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

