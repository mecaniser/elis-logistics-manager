import { useEffect, useState } from 'react'
import { accountingApi } from '../services/api'
import { useTenant } from '../contexts/TenantContext'
import InfoPanel from '../components/InfoPanel'

interface ScheduleC {
  year: number
  business_name: string
  ein?: string
  line_1: number
  line_27: number
  line_31: number
  expense_breakdown: { [key: string]: number }
}

export default function ScheduleC() {
  const { currentTenant } = useTenant()
  const [scheduleC, setScheduleC] = useState<ScheduleC | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [year, setYear] = useState(new Date().getFullYear())

  useEffect(() => {
    loadScheduleC()
  }, [year, currentTenant?.id])

  const loadScheduleC = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await accountingApi.getScheduleC(year)
      setScheduleC(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load Schedule C')
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

  const handleExport = async (format: 'pdf' | 'excel') => {
    if (!scheduleC) return
    
    try {
      // Export as income statement formatted for Schedule C
      const startDate = `${year}-01-01`
      const endDate = `${year}-12-31`
      const response = await accountingApi.exportIncomeStatement(format, startDate, endDate)
      const blob = new Blob([response.data], { 
        type: format === 'excel' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : 'application/pdf'
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `schedule_c_${year}.${format === 'excel' ? 'xlsx' : 'pdf'}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err: any) {
      console.error('Export failed:', err)
      alert('Failed to export Schedule C')
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading Schedule C...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Schedule C Report</h1>
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Schedule C Report</h1>
        {scheduleC && (
          <div className="flex gap-2">
            <button
              onClick={() => handleExport('pdf')}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
            >
              Export PDF
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
        title="Schedule C (Form 1040)"
        content={
          <div className="space-y-3">
            <p>
              <strong>Schedule C</strong> is used by sole proprietors to report business income and expenses on their personal tax return (Form 1040). This report maps your accounting data to Schedule C line items.
            </p>
            <div>
              <p className="font-semibold mb-2">Key Line Items:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><strong>Line 1:</strong> Gross receipts or sales</li>
                <li><strong>Line 27:</strong> Total expenses</li>
                <li><strong>Line 31:</strong> Net profit or (loss)</li>
              </ul>
            </div>
            <p>
              <strong>Note:</strong> This is a simplified mapping. Consult with a tax professional for complete Schedule C preparation.
            </p>
          </div>
        }
      />

      {scheduleC && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b">
            <h2 className="text-lg font-semibold text-gray-900">
              Schedule C - {scheduleC.business_name} ({year})
            </h2>
            {scheduleC.ein && (
              <p className="text-sm text-gray-500 mt-1">EIN: {scheduleC.ein}</p>
            )}
          </div>
          <div className="p-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center py-2 border-b">
                <span className="font-semibold text-gray-900">Line 1: Gross receipts or sales</span>
                <span className="font-bold text-lg">{formatCurrency(scheduleC.line_1)}</span>
              </div>
              
              <div className="mt-6">
                <h3 className="font-semibold mb-3 text-gray-900">Expense Breakdown:</h3>
                <div className="space-y-2">
                  {Object.entries(scheduleC.expense_breakdown)
                    .sort(([, a], [, b]) => b - a)
                    .map(([line, amount]) => (
                      <div key={line} className="flex justify-between py-1">
                        <span className="text-gray-900">{line}</span>
                        <span className="font-medium text-red-600">{formatCurrency(amount)}</span>
                      </div>
                    ))}
                </div>
              </div>

              <div className="flex justify-between items-center py-2 border-t-2 border-gray-400 mt-4">
                <span className="font-semibold text-gray-900">Line 27: Total expenses</span>
                <span className="font-bold text-lg text-red-600">{formatCurrency(scheduleC.line_27)}</span>
              </div>

              <div className="flex justify-between items-center py-2 border-t-4 border-gray-600 mt-6">
                <span className="font-bold text-xl text-gray-900">Line 31: Net profit or (loss)</span>
                <span className={`font-bold text-2xl ${scheduleC.line_31 >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatCurrency(scheduleC.line_31)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

