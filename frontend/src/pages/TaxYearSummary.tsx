import { useEffect, useState } from 'react'
import { accountingApi } from '../services/api'
import { useTenant } from '../contexts/TenantContext'
import InfoPanel from '../components/InfoPanel'

interface TaxYearSummary {
  year: number
  start_date: string
  end_date: string
  truck_id?: number | null
  revenue: {
    total: number
  }
  expenses: { [key: string]: number }
  total_expenses: number
  net_income: number
  account_balances: {
    cash: number
    accounts_receivable: number
    vehicles: number
    accumulated_depreciation: number
    accounts_payable: number
    loans_payable: number
    owner_equity: number
    retained_earnings: number
  }
}

export default function TaxYearSummary() {
  const { currentTenant } = useTenant()
  const [summary, setSummary] = useState<TaxYearSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [year, setYear] = useState(new Date().getFullYear())

  useEffect(() => {
    loadSummary()
  }, [year, currentTenant?.id])

  const loadSummary = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await accountingApi.getTaxYearSummary(year)
      setSummary(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load tax year summary')
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

  const handleExport = async (format: 'csv' | 'excel' | 'pdf') => {
    if (!summary) return
    
    try {
      // For now, export as income statement for the tax year
      const response = await accountingApi.exportIncomeStatement(
        format === 'pdf' ? 'pdf' : 'excel',
        summary.start_date,
        summary.end_date,
        summary.truck_id || undefined
      )
      const blob = new Blob([response.data], { 
        type: format === 'excel' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : format === 'pdf' ? 'application/pdf' : 'text/csv'
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `tax_year_summary_${year}.${format === 'excel' ? 'xlsx' : format === 'pdf' ? 'pdf' : 'csv'}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err: any) {
      console.error('Export failed:', err)
      alert('Failed to export tax year summary')
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading tax year summary...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Tax Year Summary</h1>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Tax Year Summary</h1>
        {summary && (
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
            <button
              onClick={() => handleExport('pdf')}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
            >
              Export PDF
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-3">
        <label className="text-sm font-medium text-gray-700">Tax Year:</label>
        <select
          value={year}
          onChange={(e) => setYear(parseInt(e.target.value))}
          className="px-3 py-2 border border-gray-300 rounded-md text-sm"
        >
          {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>

      <InfoPanel
        title="Tax Year Summary"
        content={
          <div className="space-y-3">
            <p>
              A <strong>Tax Year Summary</strong> provides a comprehensive overview of your business's financial activity for a specific tax year (January 1 - December 31). This summary includes all revenue, expenses, and account balances needed for tax preparation.
            </p>
            <p>
              <strong>Use this report to:</strong>
            </p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>Prepare your tax returns (Schedule C for sole proprietorships)</li>
              <li>Review annual financial performance</li>
              <li>Export data for your accountant</li>
              <li>Track year-over-year changes</li>
            </ul>
          </div>
        }
      />

      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Total Revenue</h3>
            <p className="text-2xl font-bold text-green-600">{formatCurrency(summary.revenue.total)}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Total Expenses</h3>
            <p className="text-2xl font-bold text-red-600">{formatCurrency(summary.total_expenses)}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Net Income</h3>
            <p className={`text-2xl font-bold ${summary.net_income >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(summary.net_income)}
            </p>
          </div>
        </div>
      )}

      {summary && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b">
            <h2 className="text-lg font-semibold text-gray-900">Account Balances as of December 31, {year}</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-md font-semibold text-gray-900 mb-3">Assets</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-700">Cash</span>
                    <span className="font-medium text-sm text-gray-900">{formatCurrency(summary.account_balances.cash)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Accounts Receivable</span>
                    <span className="font-medium text-sm text-gray-900">{formatCurrency(summary.account_balances.accounts_receivable)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Vehicles</span>
                    <span className="font-medium text-sm text-gray-900">{formatCurrency(summary.account_balances.vehicles)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Accumulated Depreciation</span>
                    <span className="font-medium text-sm text-red-600">
                      ({formatCurrency(Math.abs(summary.account_balances.accumulated_depreciation))})
                    </span>
                  </div>
                </div>
              </div>
              <div>
                <h3 className="text-md font-semibold text-gray-900 mb-3">Liabilities & Equity</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-700">Accounts Payable</span>
                    <span className="font-medium text-sm text-gray-900">{formatCurrency(summary.account_balances.accounts_payable)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Loans Payable</span>
                    <span className="font-medium text-sm text-gray-900">{formatCurrency(summary.account_balances.loans_payable)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Owner Equity</span>
                    <span className="font-medium text-sm text-gray-900">{formatCurrency(summary.account_balances.owner_equity)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Retained Earnings</span>
                    <span className="font-medium text-sm text-gray-900">{formatCurrency(summary.account_balances.retained_earnings)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

