import { useEffect, useState } from 'react'
import { accountingApi, IncomeStatement as IncomeStatementType } from '../services/api'
import { useTenant } from '../contexts/TenantContext'

export default function IncomeStatement() {
  const { currentTenant } = useTenant()
  const [incomeStatement, setIncomeStatement] = useState<IncomeStatementType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Default to current month
  const today = new Date()
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1)
  const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0)
  
  const [startDate, setStartDate] = useState(firstDay.toISOString().split('T')[0])
  const [endDate, setEndDate] = useState(lastDay.toISOString().split('T')[0])

  useEffect(() => {
    if (startDate && endDate) {
      setIncomeStatement(null)
      loadIncomeStatement()
    }
  }, [startDate, endDate, currentTenant?.id])

  const loadIncomeStatement = async () => {
    if (!startDate || !endDate) return
    
    try {
      setLoading(true)
      setError(null)
      const response = await accountingApi.getIncomeStatement(startDate, endDate)
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
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Income Statement</h1>
        <div className="flex items-center gap-4">
          <div>
            <label className="text-sm font-medium text-gray-700 mr-2">
              Start Date:
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 mr-2">
              End Date:
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
          </div>
        </div>
      </div>

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
        <div className="p-6">
          <div className="max-w-2xl mx-auto">
            {/* Revenue */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Revenue</h3>
              <div className="space-y-2">
                <div className="flex justify-between py-2 border-b">
                  <span className="text-gray-700">
                    {Object.keys(incomeStatement.revenue).map(key => 
                      key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
                    ).join(', ')}
                  </span>
                  <span className="font-medium">
                    {formatCurrency(incomeStatement.revenue.total)}
                  </span>
                </div>
                <div className="flex justify-between py-2 mt-4 border-t-2 border-gray-400">
                  <span className="text-lg font-semibold text-gray-900">Total Revenue</span>
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
                  .sort(([, a], [, b]) => b - a) // Sort by amount descending
                  .map(([name, amount]) => (
                    <div key={name} className="flex justify-between py-2 border-b">
                      <span className="text-gray-700">
                        {name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </span>
                      <span className="font-medium text-red-600">
                        {formatCurrency(amount)}
                      </span>
                    </div>
                  ))}
                <div className="flex justify-between py-2 mt-4 border-t-2 border-gray-400">
                  <span className="text-lg font-semibold text-gray-900">Total Expenses</span>
                  <span className="text-lg font-semibold text-red-600">
                    {formatCurrency(incomeStatement.total_expenses)}
                  </span>
                </div>
              </div>
            </div>

            {/* Net Income */}
            <div className="mt-6 pt-6 border-t-4 border-gray-600">
              <div className="flex justify-between">
                <span className="text-xl font-bold text-gray-900">Net Income</span>
                <span
                  className={`text-xl font-bold ${
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

