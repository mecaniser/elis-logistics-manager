import { useEffect, useState } from 'react'
import { analyticsApi, trucksApi, Truck, TimeSeriesData } from '../services/api'
import ReactECharts from 'echarts-for-react'

// Type definitions for dashboard data structures
interface RepairByMonth {
  truck_id: number
  month_key: string
  month: string
  category?: string
  cost: number
}

interface BlockByTruckMonth {
  truck_id: number
  month_key: string
  month: string
  blocks: number
  truck_name?: string
}

interface ExpenseData {
  fuel: number[]
  dispatch_fee: number[]
  insurance: number[]
  safety: number[]
  prepass: number[]
  ifta: number[]
  truck_parking: number[]
  custom: number[]
}

export default function Dashboard() {
  const [data, setData] = useState<any>(null)
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [selectedTruck, setSelectedTruck] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesData | null>(null)
  const [groupBy, setGroupBy] = useState<'week_start' | 'settlement_date'>('week_start')
  const [timeSeriesLoading, setTimeSeriesLoading] = useState(false)
  const [activeTimeView, setActiveTimeView] = useState<'weekly' | 'monthly'>('weekly')
  const [selectedCategories, setSelectedCategories] = useState<{ [key: string]: boolean }>({})
  const [selectedExpensePeriod, setSelectedExpensePeriod] = useState<string>('')
  const [expenseAnalysisView, setExpenseAnalysisView] = useState<'weekly' | 'monthly' | 'yearly' | 'all_time'>('monthly')
  const [settlementsInfoExpanded, setSettlementsInfoExpanded] = useState<boolean>(false) // Collapsed by default

  useEffect(() => {
    loadTrucks()
    loadDashboard()
    loadTimeSeries()
  }, [selectedTruck, groupBy])

  // Initialize selected categories when expense data changes
  useEffect(() => {
    if (data?.expense_categories) {
      const categories = [
        { name: 'Fuel', value: data.expense_categories.fuel },
        { name: 'Repairs', value: data.expense_categories.repairs },
        { name: 'Dispatch Fee', value: data.expense_categories.dispatch_fee },
        { name: 'Insurance', value: data.expense_categories.insurance },
        { name: 'Safety', value: data.expense_categories.safety },
        { name: 'Prepass', value: data.expense_categories.prepass },
        { name: 'IFTA', value: data.expense_categories.ifta },
        { name: "Driver's Pay", value: data.expense_categories.driver_pay },
        { name: 'Payroll Fee', value: data.expense_categories.payroll_fee },
        { name: 'Truck Parking', value: data.expense_categories.truck_parking },
        { name: 'Custom', value: data.expense_categories.custom || data.expense_categories.other || 0 },
      ].filter(item => item.value > 0).sort((a, b) => b.value - a.value)
      
      if (categories.length > 0) {
        const initial: { [key: string]: boolean } = {}
        categories.forEach(item => {
          initial[item.name] = true
        })
        setSelectedCategories(initial)
      }
    }
  }, [data])

  // Initialize selected period to most recent
  useEffect(() => {
    if (timeSeriesData && !selectedExpensePeriod) {
      // For "All Time", don't set a period
      if (expenseAnalysisView === 'all_time') {
        return
      }
      
      const periods = expenseAnalysisView === 'weekly' 
        ? timeSeriesData.by_week 
        : expenseAnalysisView === 'monthly'
        ? timeSeriesData.by_month
        : timeSeriesData.by_year
      
      if (periods.length > 0) {
        const periodKey = expenseAnalysisView === 'weekly' ? 'week_key' : expenseAnalysisView === 'monthly' ? 'month_key' : 'year_key'
        setSelectedExpensePeriod((periods[periods.length - 1] as any)[periodKey])
      }
    }
  }, [timeSeriesData, expenseAnalysisView, selectedExpensePeriod])

  // Reset selected period when view changes
  useEffect(() => {
    if (timeSeriesData) {
      // For "All Time", clear the selected period
      if (expenseAnalysisView === 'all_time') {
        setSelectedExpensePeriod('')
        return
      }
      
      const periods = expenseAnalysisView === 'weekly' 
        ? timeSeriesData.by_week 
        : expenseAnalysisView === 'monthly'
        ? timeSeriesData.by_month
        : timeSeriesData.by_year
      
      if (periods.length > 0) {
        const periodKey = expenseAnalysisView === 'weekly' ? 'week_key' : expenseAnalysisView === 'monthly' ? 'month_key' : 'year_key'
        const currentPeriod = periods.find(p => (p as any)[periodKey] === selectedExpensePeriod)
        if (!currentPeriod) {
          setSelectedExpensePeriod((periods[periods.length - 1] as any)[periodKey])
        }
      }
    }
    // Collapse settlements info when view or period changes
    setSettlementsInfoExpanded(false)
  }, [expenseAnalysisView, timeSeriesData, selectedExpensePeriod])

  const loadTrucks = async () => {
    try {
      const response = await trucksApi.getAll()
      setTrucks(response.data)
    } catch (err) {
      console.error(err)
    }
  }

  const loadDashboard = async () => {
    try {
      setLoading(true)
      const response = await analyticsApi.getDashboard(selectedTruck || undefined)
      setData(response.data)
    } catch (err) {
      console.error('Failed to load dashboard:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadTimeSeries = async () => {
    try {
      setTimeSeriesLoading(true)
      const response = await analyticsApi.getTimeSeries(groupBy, selectedTruck || undefined)
      setTimeSeriesData(response.data)
    } catch (err) {
      console.error('Failed to load time-series data:', err)
    } finally {
      setTimeSeriesLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-8">Loading dashboard...</div>
  }

  if (!data) {
    return <div className="text-center py-8 text-red-600">Failed to load dashboard data</div>
  }

  const expenseCategoriesData = data.expense_categories ? [
    { name: 'Fuel', value: data.expense_categories.fuel, color: '#3b82f6' },
    { name: 'Repairs', value: data.expense_categories.repairs, color: '#ef4444' },
    { name: 'Dispatch Fee', value: data.expense_categories.dispatch_fee, color: '#f59e0b' },
    { name: 'Insurance', value: data.expense_categories.insurance, color: '#f97316' },
    { name: 'Safety', value: data.expense_categories.safety, color: '#eab308' },
    { name: 'Prepass', value: data.expense_categories.prepass, color: '#84cc16' },
    { name: 'IFTA', value: data.expense_categories.ifta, color: '#10b981' },
    { name: "Driver's Pay", value: data.expense_categories.driver_pay, color: '#8b5cf6' },
    { name: 'Payroll Fee', value: data.expense_categories.payroll_fee, color: '#ec4899' },
    { name: 'Truck Parking', value: data.expense_categories.truck_parking, color: '#a855f7' },
    { name: 'Custom', value: data.expense_categories.custom || data.expense_categories.other || 0, color: '#6b7280' },
  ].filter(item => item.value > 0).sort((a, b) => b.value - a.value) : []

  const truckProfitsData = data.truck_profits || []
  const blocksByTruckMonth: BlockByTruckMonth[] = data.blocks_by_truck_month || []
  const repairsByMonth: RepairByMonth[] = data.repairs_by_month || []

  // Identify months with PM (preventive maintenance) repairs by truck
  const getPMMonthsByTruck = () => {
    const pmMonths: { [truckId: number]: Set<string> } = {}
    
    repairsByMonth.forEach((repair: RepairByMonth) => {
      // PM repairs are categorized as "maintenance"
      if (repair.category === 'maintenance' && repair.month_key) {
        if (!pmMonths[repair.truck_id]) {
          pmMonths[repair.truck_id] = new Set()
        }
        pmMonths[repair.truck_id].add(repair.month_key)
      }
    })
    
    return pmMonths
  }

  const pmMonthsByTruck = getPMMonthsByTruck()

  // Process blocks data for chart
  const processBlocksData = () => {
    if (blocksByTruckMonth.length === 0) return { months: [], series: [], averageLine: [] }
    
    // Get all unique months
    const monthSet = new Set<string>()
    blocksByTruckMonth.forEach((item: BlockByTruckMonth) => {
      monthSet.add(item.month_key)
    })
    const months = Array.from(monthSet).sort()
    
    // Get all unique trucks
    const truckSet = new Set<number>()
    blocksByTruckMonth.forEach((item: BlockByTruckMonth) => {
      truckSet.add(item.truck_id)
    })
    const truckIds = Array.from(truckSet)
    
    // Get truck names
    const truckMap = new Map<number, string>()
    trucks.forEach(truck => {
      truckMap.set(truck.id, truck.name)
    })
    
    // Create series for each truck
    const series = truckIds.map(truckId => {
      const truckName = truckMap.get(truckId) || `Truck ${truckId}`
      const data = months.map(monthKey => {
        const item = blocksByTruckMonth.find(
          (d: BlockByTruckMonth) => d.truck_id === truckId && d.month_key === monthKey
        )
        return item ? item.blocks : 0
      })
      
      return {
        name: truckName,
        type: 'bar',
        data: data
      }
    })
    
    // Calculate average blocks per month across all trucks
    const averageLine = months.map(monthKey => {
      const monthData = blocksByTruckMonth.filter((d: BlockByTruckMonth) => d.month_key === monthKey)
      if (monthData.length === 0) return 0
      const totalBlocks = monthData.reduce((sum: number, d: BlockByTruckMonth) => sum + d.blocks, 0)
      const avgBlocks = totalBlocks / monthData.length
      return Math.round(avgBlocks * 100) / 100 // Round to 2 decimal places
    })
    
    // Format month labels
    const monthLabels = months.map(monthKey => {
      const item = blocksByTruckMonth.find((d: BlockByTruckMonth) => d.month_key === monthKey)
      return item ? item.month : monthKey
    })
    
    return { months: monthLabels, series, averageLine }
  }

  const blocksChartData = processBlocksData()
  const pmStatus = data.pm_status || []

  // Filter PM status by selected truck if applicable
  const filteredPMStatus = selectedTruck 
    ? pmStatus.filter((pm) => pm.truck_id === selectedTruck)
    : pmStatus

  // Separate trucks due vs not due
  const trucksDueForPM = filteredPMStatus.filter((pm) => pm.is_due)
  const trucksNotDueForPM = filteredPMStatus.filter((pm) => !pm.is_due)

  const processWeeklyData = (data: TimeSeriesData | null): { labels: string[], grossRevenue: number[], netProfit: number[], driverPay: number[], payrollFee: number[], expenses: ExpenseData } => {
    if (!data || !data.by_week || data.by_week.length === 0) {
      return { labels: [], grossRevenue: [], netProfit: [], driverPay: [], payrollFee: [], expenses: { fuel: [], dispatch_fee: [], insurance: [], safety: [], prepass: [], ifta: [], truck_parking: [], custom: [] } }
    }
    
    const labels = data.by_week.map((item) => item.week_label)
    const grossRevenue = data.by_week.map((item) => item.gross_revenue)
    const netProfit = data.by_week.map((item) => item.net_profit)
    const driverPay = data.by_week.map((item) => item.driver_pay)
    const payrollFee = data.by_week.map((item) => item.payroll_fee)
    
    const expenses: ExpenseData = {
      fuel: data.by_week.map((item) => item.fuel),
      dispatch_fee: data.by_week.map((item) => item.dispatch_fee),
      insurance: data.by_week.map((item) => item.insurance),
      safety: data.by_week.map((item) => item.safety),
      prepass: data.by_week.map((item) => item.prepass),
      ifta: data.by_week.map((item) => item.ifta),
      truck_parking: data.by_week.map((item) => item.truck_parking),
      custom: data.by_week.map((item) => item.custom),
    }
    
    return { labels, grossRevenue, netProfit, driverPay, payrollFee, expenses }
  }

  const processMonthlyData = (data: TimeSeriesData | null): { labels: string[], grossRevenue: number[], netProfit: number[], driverPay: number[], payrollFee: number[], expenses: ExpenseData } => {
    if (!data || !data.by_month || data.by_month.length === 0) {
      return { labels: [], grossRevenue: [], netProfit: [], driverPay: [], payrollFee: [], expenses: { fuel: [], dispatch_fee: [], insurance: [], safety: [], prepass: [], ifta: [], truck_parking: [], custom: [] } }
    }
    
    const labels = data.by_month.map((item) => item.month_label)
    const grossRevenue = data.by_month.map((item) => item.gross_revenue)
    const netProfit = data.by_month.map((item) => item.net_profit)
    const driverPay = data.by_month.map((item) => item.driver_pay)
    const payrollFee = data.by_month.map((item) => item.payroll_fee)
    
    const expenses: ExpenseData = {
      fuel: data.by_month.map((item) => item.fuel),
      dispatch_fee: data.by_month.map((item) => item.dispatch_fee),
      insurance: data.by_month.map((item) => item.insurance),
      safety: data.by_month.map((item) => item.safety),
      prepass: data.by_month.map((item) => item.prepass),
      ifta: data.by_month.map((item) => item.ifta),
      truck_parking: data.by_month.map((item) => item.truck_parking),
      custom: data.by_month.map((item) => item.custom),
    }
    
    return { labels, grossRevenue, netProfit, driverPay, payrollFee, expenses }
  }

  const weeklyData = processWeeklyData(timeSeriesData)
  const monthlyData = processMonthlyData(timeSeriesData)
  const currentData = activeTimeView === 'weekly' ? weeklyData : monthlyData

  // Helper functions for category selection
  const handleSelectAllCategories = () => {
    const allSelected: { [key: string]: boolean } = {}
    expenseCategoriesData.forEach(item => {
      allSelected[item.name] = true
    })
    setSelectedCategories(allSelected)
  }

  const handleDeselectAllCategories = () => {
    const allDeselected: { [key: string]: boolean } = {}
    expenseCategoriesData.forEach(item => {
      allDeselected[item.name] = false
    })
    setSelectedCategories(allDeselected)
  }

  const handleLegendSelectChange = (params: any) => {
    if (params && params.selected) {
      setSelectedCategories(params.selected)
    }
  }

  const allCategoriesSelected = expenseCategoriesData.length > 0 && 
    expenseCategoriesData.every(item => selectedCategories[item.name] !== false)
  
  const noCategoriesSelected = expenseCategoriesData.length > 0 && 
    expenseCategoriesData.every(item => selectedCategories[item.name] === false)

  // Calculate average expense percentages from all data
  const calculateAveragePercentages = () => {
    if (!timeSeriesData) return {}
    
    const allPeriods = expenseAnalysisView === 'weekly' 
      ? timeSeriesData.by_week 
      : expenseAnalysisView === 'monthly'
      ? timeSeriesData.by_month
      : timeSeriesData.by_year
    
    if (allPeriods.length === 0) return {}
    
    const totals: { [key: string]: { total: number; count: number } } = {}
    
    allPeriods.forEach(period => {
      const revenue = period.gross_revenue || 0
      if (revenue > 0) {
        const categories = ['fuel', 'dispatch_fee', 'insurance', 'safety', 'prepass', 'ifta', 'truck_parking', 'custom', 'driver_pay', 'payroll_fee']
        categories.forEach(cat => {
          const amount = (period as any)[cat] || 0
          const percent = (amount / revenue) * 100
          if (!totals[cat]) {
            totals[cat] = { total: 0, count: 0 }
          }
          totals[cat].total += percent
          totals[cat].count += 1
        })
      }
    })
    
    const averages: { [key: string]: number } = {}
    Object.keys(totals).forEach(cat => {
      if (totals[cat].count > 0) {
        averages[cat] = totals[cat].total / totals[cat].count
      }
    })
    
    return averages
  }

  const averagePercentages = calculateAveragePercentages()

  // Get selected period data
  const getSelectedPeriodData = () => {
    // For "All Time", use dashboard data directly (includes repairs and all settlements)
    if (expenseAnalysisView === 'all_time') {
      if (!data) return null
      
      // Use dashboard data which already has correct totals from all settlements
      const expenseCategories = data.expense_categories || {}
      const aggregated = {
        all_time_key: 'all_time',
        all_time_label: 'All Time',
        gross_revenue: data.total_revenue || 0,
        net_profit: data.net_profit || 0,
        driver_pay: expenseCategories.driver_pay || 0,
        payroll_fee: expenseCategories.payroll_fee || 0,
        fuel: expenseCategories.fuel || 0,
        dispatch_fee: expenseCategories.dispatch_fee || 0,
        insurance: expenseCategories.insurance || 0,
        safety: expenseCategories.safety || 0,
        prepass: expenseCategories.prepass || 0,
        ifta: expenseCategories.ifta || 0,
        truck_parking: expenseCategories.truck_parking || 0,
        custom: expenseCategories.custom || 0,
        repairs: expenseCategories.repairs || 0, // Include repairs
        trucks: (data.truck_profits || []).map((tp: any) => ({
          truck_id: tp.truck_id,
          truck_name: tp.truck_name
        }))
      }
      
      return aggregated
    }
    
    if (!timeSeriesData) return null
    
    if (!selectedExpensePeriod) return null
    
    const periods = expenseAnalysisView === 'weekly' 
      ? timeSeriesData.by_week 
      : expenseAnalysisView === 'monthly'
      ? timeSeriesData.by_month
      : timeSeriesData.by_year
    
    const periodKey = expenseAnalysisView === 'weekly' ? 'week_key' : expenseAnalysisView === 'monthly' ? 'month_key' : 'year_key'
    return periods.find(p => (p as any)[periodKey] === selectedExpensePeriod) || null
  }

  const selectedPeriodData = getSelectedPeriodData()

  return (
    <div>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-0 mb-4 sm:mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
          <div className="w-full sm:w-auto">
            <label className="block text-sm font-medium text-gray-700 mb-2 sm:mb-0 sm:inline-block sm:mr-2">
              Filter by Truck:
            </label>
            <select
              value={selectedTruck || ''}
              onChange={(e) => setSelectedTruck(e.target.value ? Number(e.target.value) : null)}
              className="w-full sm:w-auto px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              <option value="">All Trucks</option>
              {trucks.map((truck) => (
                <option key={truck.id} value={truck.id}>
                  {truck.name}
                </option>
              ))}
            </select>
          </div>
          <div className="w-full sm:w-auto">
            <label className="block text-sm font-medium text-gray-700 mb-2 sm:mb-0 sm:inline-block sm:mr-2">
              Week Grouping:
            </label>
            <div className="inline-flex rounded-md shadow-sm" role="group">
              <button
                type="button"
                onClick={() => setGroupBy('week_start')}
                className={`px-3 py-2 text-sm font-medium border rounded-l-lg ${
                  groupBy === 'week_start'
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Week Start
              </button>
              <button
                type="button"
                onClick={() => setGroupBy('settlement_date')}
                className={`px-3 py-2 text-sm font-medium border rounded-r-lg ${
                  groupBy === 'settlement_date'
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Settlement Date
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* PM Status Alert */}
      {trucksDueForPM.length > 0 && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-6 rounded-r-lg">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-sm font-medium text-red-800 mb-2">
                ⚠️ {trucksDueForPM.length} Truck{trucksDueForPM.length !== 1 ? 's' : ''} Due for D13 Full PM
              </h3>
              <div className="mt-2 space-y-1">
                {trucksDueForPM.map((pm) => (
                  <div key={pm.truck_id} className="text-sm text-red-700">
                    <span className="font-semibold">{pm.truck_name}</span>
                    {pm.last_pm_date ? (
                      <>
                        {' - Last PM: '}
                        <span className="font-medium">
                          {new Date(pm.last_pm_date).toLocaleDateString()}
                        </span>
                        {pm.days_overdue !== null && (
                          <>
                            {' ('}
                            <span className="font-bold">{pm.days_overdue}</span>
                            {' days overdue)'}
                          </>
                        )}
                      </>
                    ) : (
                      <span className="font-medium"> - No PM record found</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PM Status Summary Card */}
      {pmStatus.length > 0 && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">D13 Full PM Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Trucks Due */}
            <div className="border-l-4 border-red-500 pl-4">
              <div className="text-sm font-medium text-gray-500 mb-1">Due for PM</div>
              <div className="text-2xl font-bold text-red-600">{trucksDueForPM.length}</div>
              {trucksDueForPM.length > 0 && (
                <div className="mt-2 space-y-1">
                  {trucksDueForPM.map((pm) => (
                    <div key={pm.truck_id} className="text-sm text-gray-700">
                      {pm.truck_name}
                      {pm.days_overdue !== null && (
                        <span className="text-red-600 font-medium ml-2">
                          ({pm.days_overdue} days overdue)
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* Trucks Not Due */}
            <div className="border-l-4 border-green-500 pl-4">
              <div className="text-sm font-medium text-gray-500 mb-1">Up to Date</div>
              <div className="text-2xl font-bold text-green-600">{trucksNotDueForPM.length}</div>
              {trucksNotDueForPM.length > 0 && (
                <div className="mt-2 space-y-1">
                  {trucksNotDueForPM.map((pm) => (
                    <div key={pm.truck_id} className="text-sm text-gray-700">
                      {pm.truck_name}
                      {pm.last_pm_date && pm.days_since_pm !== null && (
                        <span className="text-gray-500 ml-2">
                          ({pm.days_since_pm} days ago)
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="mt-4 text-xs text-gray-500">
            PM threshold: Every {pmStatus[0]?.pm_threshold_months || 3} months
          </div>
        </div>
      )}

      {/* Summary Cards - Always show All Time totals */}
      <div className="mb-4">
        <p className="text-xs text-gray-500 mb-2">📊 Summary (All Time)</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6 sm:mb-8">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-4 sm:p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="text-xl sm:text-2xl font-bold text-gray-900">
                  {data.total_trucks || trucks.length}
                </div>
              </div>
              <div className="ml-4 sm:ml-5 w-0 flex-1">
                <p className="text-sm font-medium text-gray-500 truncate">Total Trucks</p>
                <p className="text-xs text-gray-400 mt-0.5">All Time</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-4 sm:p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="text-xl sm:text-2xl font-bold text-green-600">
                  ${(data.total_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>
              <div className="ml-4 sm:ml-5 w-0 flex-1">
                <p className="text-sm font-medium text-gray-500 truncate">Total Revenue</p>
                <p className="text-xs text-gray-400 mt-0.5">All Time</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-4 sm:p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="text-xl sm:text-2xl font-bold text-red-600">
                  ${(data.total_expenses || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>
              <div className="ml-4 sm:ml-5 w-0 flex-1">
                <p className="text-sm font-medium text-gray-500 truncate">Total Expenses</p>
                <p className="text-xs text-gray-400 mt-0.5">All Time</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-4 sm:p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className={`text-xl sm:text-2xl font-bold ${(data.net_profit || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  ${(data.net_profit || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>
              <div className="ml-4 sm:ml-5 w-0 flex-1">
                <p className="text-sm font-medium text-gray-500 truncate">Net Profit</p>
                <p className="text-xs text-gray-400 mt-0.5">All Time</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Detailed Expense Analysis Section - First Chart */}
      {timeSeriesData && (
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
            <h2 className="text-2xl font-semibold text-gray-900">Detailed Expense Analysis</h2>
            <div className="flex flex-wrap gap-3 items-center">
              <div className="inline-flex rounded-md shadow-sm" role="group">
                <button
                  type="button"
                  onClick={() => setExpenseAnalysisView('weekly')}
                  className={`px-4 py-2 text-sm font-medium border rounded-l-lg ${
                    expenseAnalysisView === 'weekly'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  Weekly
                </button>
                <button
                  type="button"
                  onClick={() => setExpenseAnalysisView('monthly')}
                  className={`px-4 py-2 text-sm font-medium border-t border-b ${
                    expenseAnalysisView === 'monthly'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  Monthly
                </button>
                <button
                  type="button"
                  onClick={() => setExpenseAnalysisView('yearly')}
                  className={`px-4 py-2 text-sm font-medium border-t border-b ${
                    expenseAnalysisView === 'yearly'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  Yearly
                </button>
                <button
                  type="button"
                  onClick={() => setExpenseAnalysisView('all_time')}
                  className={`px-4 py-2 text-sm font-medium border rounded-r-lg ${
                    expenseAnalysisView === 'all_time'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  All Time
                </button>
              </div>
              {expenseAnalysisView !== 'all_time' && (
              <select
                value={selectedExpensePeriod}
                onChange={(e) => setSelectedExpensePeriod(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              >
                {(expenseAnalysisView === 'weekly' 
                  ? (timeSeriesData?.by_week || []) 
                  : expenseAnalysisView === 'monthly'
                  ? (timeSeriesData?.by_month || [])
                  : (timeSeriesData?.by_year || [])
                ).map((period: any) => {
                  const key = expenseAnalysisView === 'weekly' ? period.week_key : expenseAnalysisView === 'monthly' ? period.month_key : period.year_key
                  const label = expenseAnalysisView === 'weekly' ? period.week_label : expenseAnalysisView === 'monthly' ? period.month_label : period.year_label
                  return (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  )
                })}
              </select>
              )}
            </div>
          </div>

          {!timeSeriesData.by_week?.length && !timeSeriesData.by_month?.length ? (
            <div className="text-center py-8 text-gray-500">
              No time-series data available. Please ensure you have settlements with dates.
            </div>
          ) : selectedPeriodData ? (
            <div className="space-y-6">
              {/* Period Summary */}
              <div className="bg-gray-50 p-4 rounded-lg mb-4">
                <p className="text-sm text-gray-700">
                  <strong>Period Selected:</strong> {expenseAnalysisView === 'all_time'
                    ? 'All Time'
                    : expenseAnalysisView === 'weekly' 
                    ? (selectedPeriodData as any).week_label 
                    : expenseAnalysisView === 'monthly'
                    ? (selectedPeriodData as any).month_label
                    : (selectedPeriodData as any).year_label}
                  {' '}
                  ({expenseAnalysisView === 'all_time'
                    ? 'Cumulative totals from all periods'
                    : expenseAnalysisView === 'weekly' 
                    ? 'This week only' 
                    : expenseAnalysisView === 'monthly'
                    ? 'This month only - not cumulative'
                    : 'This year only - not cumulative'})
                </p>
                <p className="text-xs text-gray-600 mt-1">
                  {expenseAnalysisView === 'all_time'
                    ? 'All amounts below are cumulative totals from all settlements across all time periods.'
                    : `All amounts below are totals for this ${expenseAnalysisView === 'weekly' ? 'week' : expenseAnalysisView === 'monthly' ? 'month' : 'year'} only, aggregated from all settlements in the selected period.`}
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="bg-blue-50 p-4 rounded-lg">
                  <div className="text-sm font-medium text-gray-600">Gross Revenue</div>
                  <div className="text-2xl font-bold text-blue-600">
                    ${selectedPeriodData.gross_revenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{expenseAnalysisView === 'all_time' ? 'All time cumulative' : `For this ${expenseAnalysisView === 'weekly' ? 'week' : expenseAnalysisView === 'monthly' ? 'month' : 'year'} only`}</div>
                </div>
                <div className="bg-red-50 p-4 rounded-lg">
                  <div className="text-sm font-medium text-gray-600">Total Expenses</div>
                  <div className="text-2xl font-bold text-red-600">
                    ${(
                      (selectedPeriodData as any).fuel +
                      (selectedPeriodData as any).dispatch_fee +
                      (selectedPeriodData as any).insurance +
                      (selectedPeriodData as any).safety +
                      (selectedPeriodData as any).prepass +
                      (selectedPeriodData as any).ifta +
                      (selectedPeriodData as any).truck_parking +
                      (selectedPeriodData as any).custom +
                      (selectedPeriodData as any).driver_pay +
                      (selectedPeriodData as any).payroll_fee +
                      ((selectedPeriodData as any).repairs || 0) // Include repairs (for All Time and Yearly)
                    ).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{expenseAnalysisView === 'all_time' ? 'All time cumulative' : `For this ${expenseAnalysisView === 'weekly' ? 'week' : expenseAnalysisView === 'monthly' ? 'month' : 'year'} only`}</div>
                </div>
                <div className="bg-green-50 p-4 rounded-lg">
                  <div className="text-sm font-medium text-gray-600">Net Profit</div>
                  <div className={`text-2xl font-bold ${selectedPeriodData.net_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ${selectedPeriodData.net_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{expenseAnalysisView === 'all_time' ? 'All time cumulative' : `For this ${expenseAnalysisView === 'weekly' ? 'week' : expenseAnalysisView === 'monthly' ? 'month' : 'year'} only`}</div>
                </div>
              </div>

              {/* Trucks Involved */}
              {(selectedPeriodData as any).trucks && (selectedPeriodData as any).trucks.length > 0 && (
                <div className="mb-4">
                  <div className="text-sm font-medium text-gray-700 mb-2">
                    Trucks Involved ({expenseAnalysisView === 'all_time' ? 'all time' : expenseAnalysisView === 'weekly' ? 'this week' : expenseAnalysisView === 'monthly' ? 'this month' : 'this year'}):
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(selectedPeriodData as any).trucks.map((truck: any) => (
                      <span
                        key={truck.truck_id}
                        className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                      >
                        {truck.truck_name}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Settlement Breakdown - Show which settlements contribute */}
              {expenseAnalysisView === 'monthly' && (selectedPeriodData as any).settlements && (selectedPeriodData as any).settlements.length > 0 && (
                <div className="mb-4 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <button
                    onClick={() => setSettlementsInfoExpanded(!settlementsInfoExpanded)}
                    className="w-full flex items-center justify-between text-left focus:outline-none focus:ring-2 focus:ring-yellow-500 rounded"
                  >
                    <div className="text-sm font-medium text-gray-700">
                      Settlements Included (this month): {(selectedPeriodData as any).settlement_count || (selectedPeriodData as any).settlements.length}
                    </div>
                    <svg
                      className={`w-5 h-5 text-gray-600 transition-transform ${settlementsInfoExpanded ? 'transform rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {settlementsInfoExpanded && (
                    <>
                      <div className="text-xs text-gray-600 mb-3 mt-2">
                        This shows which individual settlements are being aggregated into this month's totals.
                        Note: Settlements with week_start on/after the 28th are counted in the next month.
                      </div>
                      <div className="max-h-48 overflow-y-auto">
                    <table className="min-w-full text-xs">
                      <thead className="bg-yellow-100 sticky top-0">
                        <tr>
                          <th className="px-2 py-1 text-left font-medium">Settlement Date</th>
                          <th className="px-2 py-1 text-left font-medium">Week Start</th>
                          <th className="px-2 py-1 text-left font-medium">Truck</th>
                          <th className="px-2 py-1 text-right font-medium">Insurance</th>
                          <th className="px-2 py-1 text-right font-medium">Driver's Pay</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-yellow-200">
                        {(selectedPeriodData as any).settlements.map((settlement: any, idx: number) => (
                          <tr key={settlement.settlement_id || idx} className="bg-white">
                            <td className="px-2 py-1">{settlement.settlement_date ? new Date(settlement.settlement_date).toLocaleDateString() : '-'}</td>
                            <td className="px-2 py-1">{settlement.week_start ? new Date(settlement.week_start).toLocaleDateString() : '-'}</td>
                            <td className="px-2 py-1">{settlement.truck_name}</td>
                            <td className="px-2 py-1 text-right">${settlement.insurance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                            <td className="px-2 py-1 text-right">${settlement.driver_pay.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-yellow-100 font-medium">
                        <tr>
                          <td colSpan={3} className="px-2 py-1 text-right">Totals:</td>
                          <td className="px-2 py-1 text-right">
                            ${(selectedPeriodData as any).settlements.reduce((sum: number, s: any) => sum + (s.insurance || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td className="px-2 py-1 text-right">
                            ${(selectedPeriodData as any).settlements.reduce((sum: number, s: any) => sum + (s.driver_pay || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Expense Breakdown Chart */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Expenses by Category - {expenseAnalysisView === 'all_time' ? 'All Time' : expenseAnalysisView === 'weekly' ? (selectedPeriodData as any).week_label : expenseAnalysisView === 'monthly' ? (selectedPeriodData as any).month_label : (selectedPeriodData as any).year_label}
                </h3>
                {(() => {
                  // Create sorted expense categories based on values (biggest to smallest)
                  const expenseCategories = [
                    { key: 'fuel', label: 'Fuel', value: (selectedPeriodData as any).fuel || 0 },
                    { key: 'dispatch_fee', label: 'Dispatch Fee', value: (selectedPeriodData as any).dispatch_fee || 0 },
                    { key: 'insurance', label: 'Insurance', value: (selectedPeriodData as any).insurance || 0 },
                    { key: 'safety', label: 'Safety', value: (selectedPeriodData as any).safety || 0 },
                    { key: 'prepass', label: 'Prepass', value: (selectedPeriodData as any).prepass || 0 },
                    { key: 'ifta', label: 'IFTA', value: (selectedPeriodData as any).ifta || 0 },
                    { key: 'truck_parking', label: 'Truck Parking', value: (selectedPeriodData as any).truck_parking || 0 },
                    { key: 'custom', label: 'Custom', value: (selectedPeriodData as any).custom || 0 },
                    { key: 'driver_pay', label: "Driver's Pay", value: (selectedPeriodData as any).driver_pay || 0 },
                    { key: 'payroll_fee', label: 'Payroll Fee', value: (selectedPeriodData as any).payroll_fee || 0 },
                    ...((expenseAnalysisView === 'all_time' || expenseAnalysisView === 'yearly') && (selectedPeriodData as any).repairs ? [{ key: 'repairs', label: 'Repairs', value: (selectedPeriodData as any).repairs || 0 }] : []),
                  ].filter(cat => cat.value > 0).sort((a, b) => b.value - a.value)

                  const sortedLabels = expenseCategories.map(cat => cat.label)
                  const sortedValues = expenseCategories.map(cat => cat.value)
                  const sortedKeys = expenseCategories.map(cat => cat.key)
                  const sortedAverages = expenseCategories.map(cat => averagePercentages[cat.key] || 0)

                  return (
                    <ReactECharts
                      option={{
                        tooltip: {
                          trigger: 'axis',
                          axisPointer: { type: 'shadow' },
                          formatter: (params: any) => {
                            let result = `${params[0]?.axisValue}<br/>`
                            params.forEach((param: any) => {
                              const value = param.value || 0
                              const seriesName = param.seriesName
                              if (seriesName === 'Selected Period') {
                                const percent = selectedPeriodData.gross_revenue > 0 
                                  ? ((value / selectedPeriodData.gross_revenue) * 100).toFixed(1)
                                  : '0'
                                result += `${param.marker}${seriesName}: $${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${percent}%)<br/>`
                              } else {
                                result += `${param.marker}${seriesName}: ${value.toFixed(1)}%<br/>`
                              }
                            })
                            return result
                          },
                          backgroundColor: '#fff',
                          borderColor: '#e5e7eb',
                          borderWidth: 1,
                          borderRadius: 8,
                          padding: [8, 12]
                        },
                        legend: {
                          data: ['Selected Period', 'Average %'],
                          top: 10
                        },
                        grid: {
                          left: '3%',
                          right: '4%',
                          bottom: '3%',
                          top: '15%',
                          containLabel: true
                        },
                        xAxis: {
                          type: 'category',
                          data: sortedLabels,
                          axisLabel: {
                            rotate: 45,
                            fontSize: 11
                          }
                        },
                        yAxis: [
                          {
                            type: 'value',
                            name: 'Amount ($)',
                            position: 'left',
                            axisLabel: {
                              formatter: (value: number) => `$${value.toLocaleString()}`
                            }
                          },
                          {
                            type: 'value',
                            name: 'Percentage (%)',
                            position: 'right',
                            axisLabel: {
                              formatter: (value: number) => `${value.toFixed(1)}%`
                            }
                          }
                        ],
                        series: [
                          {
                            name: 'Selected Period',
                            type: 'bar',
                            data: sortedValues,
                        itemStyle: {
                          color: (params: any) => {
                            const categoryIndex = params.dataIndex
                            const amount = params.value
                            const revenue = selectedPeriodData.gross_revenue || 1
                            const percent = (amount / revenue) * 100
                            const avgPercent = sortedAverages[categoryIndex] || 0
                            
                            // Highlight if significantly above average (more than 20% higher)
                            if (avgPercent > 0 && percent > avgPercent * 1.2) {
                              return '#ef4444' // Red for unusual high spending
                            } else if (avgPercent > 0 && percent < avgPercent * 0.8) {
                              return '#10b981' // Green for lower than average
                            }
                            return '#3b82f6' // Blue for normal
                          },
                          borderRadius: [4, 4, 0, 0]
                        },
                        label: {
                          show: true,
                          position: 'top',
                          formatter: (params: any) => {
                            const value = params.value || 0
                            const revenue = selectedPeriodData.gross_revenue || 1
                            const percent = ((value / revenue) * 100).toFixed(1)
                            return value > 0 ? `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}\n(${percent}%)` : ''
                          },
                          fontSize: 9
                        }
                      },
                      {
                        name: 'Average %',
                        type: 'line',
                        yAxisIndex: 1,
                        data: sortedAverages,
                        lineStyle: {
                          color: '#f59e0b',
                          width: 2,
                          type: 'dashed'
                        },
                        itemStyle: {
                          color: '#f59e0b'
                        },
                        symbol: 'circle',
                        symbolSize: 6,
                        label: {
                          show: true,
                          position: 'top',
                          formatter: (params: any) => {
                            const value = params.value || 0
                            return value > 0 ? `${value.toFixed(1)}%` : ''
                          },
                          fontSize: 9,
                          color: '#f59e0b'
                        }
                      }
                    ]
                  }}
                  style={{ height: '500px', width: '100%' }}
                  opts={{ renderer: 'svg' }}
                />
                  )
                })()}
              </div>

              {/* Expense Details Table */}
              <div className="mt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Expense Details - {expenseAnalysisView === 'all_time' ? 'All Time' : expenseAnalysisView === 'weekly' ? (selectedPeriodData as any).week_label : expenseAnalysisView === 'monthly' ? (selectedPeriodData as any).month_label : (selectedPeriodData as any).year_label}
                </h3>
                <p className="text-sm text-gray-600 mb-4">
                  {expenseAnalysisView === 'all_time'
                    ? 'All amounts shown are cumulative totals from all settlements across all time periods.'
                    : `All amounts shown are for <strong>${expenseAnalysisView === 'weekly' ? 'this week' : expenseAnalysisView === 'monthly' ? 'this month' : 'this year'}</strong> only, aggregated from all settlements in the selected period.`}
                </p>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">% of Revenue</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Average %</th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {[
                        { key: 'fuel', label: 'Fuel' },
                        { key: 'dispatch_fee', label: 'Dispatch Fee' },
                        { key: 'insurance', label: 'Insurance' },
                        { key: 'safety', label: 'Safety' },
                        { key: 'prepass', label: 'Prepass' },
                        { key: 'ifta', label: 'IFTA' },
                        { key: 'truck_parking', label: 'Truck Parking' },
                        { key: 'custom', label: 'Custom' },
                        { key: 'driver_pay', label: "Driver's Pay" },
                        { key: 'payroll_fee', label: 'Payroll Fee' },
                        ...((expenseAnalysisView === 'all_time' || expenseAnalysisView === 'yearly') && (selectedPeriodData as any).repairs ? [{ key: 'repairs', label: 'Repairs' }] : []),
                      ]
                        .map(({ key, label }) => ({
                          key,
                          label,
                          amount: (selectedPeriodData as any)[key] || 0
                        }))
                        .sort((a, b) => b.amount - a.amount)
                        .map(({ key, label }) => {
                        const amount = (selectedPeriodData as any)[key] || 0
                        const revenue = selectedPeriodData.gross_revenue || 1
                        const percent = (amount / revenue) * 100
                        const avgPercent = averagePercentages[key] || 0
                        const diff = avgPercent > 0 ? percent - avgPercent : 0
                        const diffPercent = avgPercent > 0 ? ((diff / avgPercent) * 100) : 0
                        
                        let status = 'normal'
                        let statusColor = 'text-gray-600'
                        let statusBg = 'bg-gray-100'
                        
                        if (avgPercent > 0) {
                          if (percent > avgPercent * 1.2) {
                            status = 'high'
                            statusColor = 'text-red-700'
                            statusBg = 'bg-red-100'
                          } else if (percent < avgPercent * 0.8) {
                            status = 'low'
                            statusColor = 'text-green-700'
                            statusBg = 'bg-green-100'
                          }
                        }
                        
                        return (
                          <tr key={key} className={amount > 0 ? '' : 'opacity-50'}>
                            <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">{label}</td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                              ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                              {percent.toFixed(1)}%
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-500">
                              {avgPercent > 0 ? `${avgPercent.toFixed(1)}%` : '-'}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-center">
                              {avgPercent > 0 && amount > 0 && (
                                <span className={`px-2 py-1 text-xs font-medium rounded ${statusBg} ${statusColor}`}>
                                  {status === 'high' && `↑ ${Math.abs(diffPercent).toFixed(0)}% above avg`}
                                  {status === 'low' && `↓ ${Math.abs(diffPercent).toFixed(0)}% below avg`}
                                  {status === 'normal' && 'Normal'}
                                </span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              Please select a period from the dropdown above.
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 mb-6">
        {expenseCategoriesData.length > 0 && (
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Expenses by Category</h2>
              <div className="flex gap-2">
                <button
                  onClick={handleSelectAllCategories}
                  disabled={allCategoriesSelected}
                  className={`px-3 py-1 text-xs font-medium rounded ${
                    allCategoriesSelected
                      ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  Select All
                </button>
                <button
                  onClick={handleDeselectAllCategories}
                  disabled={noCategoriesSelected}
                  className={`px-3 py-1 text-xs font-medium rounded ${
                    noCategoriesSelected
                      ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                      : 'bg-gray-600 text-white hover:bg-gray-700'
                  }`}
                >
                  Deselect All
                </button>
              </div>
            </div>
            <ReactECharts
              option={{
                tooltip: {
                  trigger: 'item',
                  formatter: (params: any) => {
                    const value = params.value || 0
                    const percent = params.percent || 0
                    return `${params.name}<br/>$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${percent}%)`
                  },
                  backgroundColor: '#fff',
                  borderColor: '#e5e7eb',
                  borderWidth: 1,
                  borderRadius: 8,
                  padding: [8, 12],
                  textStyle: {
                    color: '#374151'
                  }
                },
                legend: {
                  orient: 'vertical',
                  right: 10,
                  top: 'center',
                  itemGap: 12,
                  textStyle: {
                    fontSize: 12,
                    color: '#374151'
                  },
                  formatter: (name: string) => {
                    const item = expenseCategoriesData.find(d => d.name === name)
                    const total = expenseCategoriesData.reduce((sum, d) => sum + d.value, 0)
                    const percent = item ? ((item.value / total) * 100).toFixed(1) : '0'
                    return `${name} (${percent}%)`
                  },
                  selected: selectedCategories
                },
                series: [
                  {
                    name: 'Expenses',
                    type: 'pie',
                    radius: ['40%', '70%'],
                    center: ['35%', '50%'],
                    avoidLabelOverlap: false,
                    itemStyle: {
                      borderRadius: 8,
                      borderColor: '#fff',
                      borderWidth: 2
                    },
                    label: {
                      show: false
                    },
                    emphasis: {
                      label: {
                        show: true,
                        fontSize: 14,
                        fontWeight: 'bold'
                      },
                      itemStyle: {
                        shadowBlur: 10,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                      }
                    },
                    labelLine: {
                      show: false
                    },
                    data: expenseCategoriesData.map(item => ({
                      value: item.value,
                      name: item.name,
                      itemStyle: {
                        color: item.color
                      }
                    }))
                  }
                ]
              }}
              style={{ height: '450px', width: '100%' }}
              opts={{ renderer: 'svg' }}
              onEvents={{
                legendselectchanged: handleLegendSelectChange
              }}
            />
          </div>
        )}
      </div>

      {repairsByMonth.length > 0 && (() => {
        // Group repairs by month
        const repairsByMonthGrouped: { [key: string]: RepairByMonth[] } = {}
        repairsByMonth.forEach((repair: RepairByMonth) => {
          if (!repairsByMonthGrouped[repair.month_key]) {
            repairsByMonthGrouped[repair.month_key] = []
          }
          repairsByMonthGrouped[repair.month_key].push(repair)
        })
        
        // Get unique months sorted
        const uniqueMonths = Array.from(new Set(repairsByMonth.map((r: RepairByMonth) => r.month_key))).sort()
        
        // Create x-axis categories: each repair gets its own position, grouped by month
        const xAxisData: string[] = []
        const repairData: number[] = []
        const repairTooltips: string[] = []
        const repairColors: string[] = []
        
        uniqueMonths.forEach((monthKey: string) => {
          const repairsInMonth = repairsByMonthGrouped[monthKey] || []
          const firstRepair = repairsInMonth[0]
          const monthLabel = firstRepair ? firstRepair.month : monthKey
          
          repairsInMonth.forEach((repair: RepairByMonth, idx: number) => {
            // Create label: "Month - Repair #" or just show month if only one repair
            const label = repairsInMonth.length > 1 
              ? `${monthLabel} - #${idx + 1}` 
              : monthLabel
            xAxisData.push(label)
            repairData.push(repair.cost)
            
            // Create tooltip with repair details
            const isPM = repair.category === 'maintenance'
            const pmIndicator = isPM ? '<br/><span style="color: #3b82f6; font-weight: bold;">🔧 Preventive Maintenance</span>' : ''
            const tooltip = `${repair.truck_name}<br/>${repair.description || 'No description'}${pmIndicator}<br/>$${repair.cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
            repairTooltips.push(tooltip)
            
            // Color by truck, but highlight PM repairs with blue
            if (isPM) {
              repairColors.push('#3b82f6') // Blue for PM
            } else {
              const colorIndex = repair.truck_id % 3
              const colors = ['#ef4444', '#f97316', '#ec4899']
              repairColors.push(colors[colorIndex])
            }
          })
        })
        
        return (
          <div className="bg-white p-6 rounded-lg shadow mb-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Repair Costs by Month (Individual Repairs)</h2>
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-blue-600 rounded"></div>
                  <span className="text-gray-600">PM Repair</span>
                </div>
              </div>
            </div>
            <ReactECharts
              option={{
                tooltip: {
                  trigger: 'axis',
                  axisPointer: {
                    type: 'shadow'
                  },
                  formatter: (params: any) => {
                    const param = params[0]
                    const index = param.dataIndex
                    return repairTooltips[index] || `${param.axisValue}<br/>$${param.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                  },
                  backgroundColor: '#fff',
                  borderColor: '#e5e7eb',
                  borderWidth: 1,
                  borderRadius: 8,
                  padding: [8, 12]
                },
                grid: {
                  left: '3%',
                  right: '4%',
                  bottom: '10%',
                  containLabel: true
                },
                xAxis: {
                  type: 'category',
                  data: xAxisData,
                  axisLabel: {
                    rotate: xAxisData.length > 10 ? 45 : 0,
                    fontSize: 10,
                    interval: 0
                  }
                },
                yAxis: {
                  type: 'value',
                  name: 'Cost ($)',
                  axisLabel: {
                    formatter: (value: number) => `$${value.toLocaleString()}`
                  }
                },
                series: [
                  {
                    name: 'Repair Cost',
                    type: 'bar',
                    data: repairData.map((cost, idx) => ({
                      value: cost,
                      itemStyle: {
                        color: repairColors[idx],
                        borderRadius: [4, 4, 0, 0]
                      }
                    })),
                    label: {
                      show: true,
                      position: 'top',
                      formatter: (params: any) => {
                        const value = params.value || 0
                        return value > 0 ? `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : ''
                      },
                      fontSize: 9
                    }
                  }
                ]
              }}
              style={{ height: '450px', width: '100%' }}
              opts={{ renderer: 'svg' }}
            />
          </div>
        )
      })()}

      {blocksChartData.series.length > 0 && (
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-900">Blocks Delivered by Truck (Monthly)</h2>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-200 border border-blue-400 rounded"></div>
                <span className="text-gray-600">PM Month</span>
              </div>
            </div>
          </div>
          <ReactECharts
            option={{
              tooltip: {
                trigger: 'axis',
                axisPointer: {
                  type: 'shadow'
                },
                formatter: (params: any) => {
                  let result = `${params[0]?.axisValue}<br/>`
                  params.forEach((param: any) => {
                    result += `${param.seriesName}: ${param.value} blocks<br/>`
                  })
                  return result
                },
                backgroundColor: '#fff',
                borderColor: '#e5e7eb',
                borderWidth: 1,
                borderRadius: 8,
                padding: [8, 12]
              },
              legend: {
                data: [...blocksChartData.series.map(s => s.name), 'Average'],
                top: 30,
                textStyle: {
                  fontSize: 12
                }
              },
              grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                top: '15%',
                containLabel: true
              },
              xAxis: {
                type: 'category',
                data: blocksChartData.months,
                axisLabel: {
                  rotate: blocksChartData.months.length > 6 ? 45 : 0,
                  fontSize: 11
                }
              },
              yAxis: {
                type: 'value',
                name: 'Blocks',
                axisLabel: {
                  formatter: (value: number) => Math.round(value).toString()
                }
              },
              series: [
                ...blocksChartData.series.map((series, seriesIndex) => {
                  // Get truck ID from series name or data
                  const truckId = trucks.find(t => t.name === series.name)?.id
                  const pmMonths = truckId ? pmMonthsByTruck[truckId] : null
                  
                  // Create markArea data for PM months
                  const markAreaData: any[] = []
                  if (pmMonths && pmMonths.size > 0) {
                    blocksChartData.months.forEach((monthLabel: string, index: number) => {
                      // Extract month_key from month label or use index
                      const monthKey = blocksByTruckMonth.find(
                        (d: BlockByTruckMonth) => d.month === monthLabel && d.truck_name === series.name
                      )?.month_key
                      
                      if (monthKey && pmMonths.has(monthKey)) {
                        markAreaData.push([
                          { xAxis: index },
                          { xAxis: index }
                        ])
                      }
                    })
                  }
                  
                  return {
                    ...series,
                    itemStyle: {
                      borderRadius: [4, 4, 0, 0],
                      color: (params: any) => {
                        // Color bars based on whether they meet the 11 blocks target
                        return params.value >= 11 ? '#10b981' : '#ef4444'
                      }
                    },
                    label: {
                      show: true,
                      position: 'inside',
                      formatter: (params: any) => {
                        const value = params.value || 0
                        return value > 0 ? value.toString() : ''
                      },
                      fontSize: 10,
                      color: '#fff'
                    },
                    markLine: {
                      silent: true,
                      lineStyle: {
                        color: '#f59e0b',
                        type: 'dashed',
                        width: 2
                      },
                      label: {
                        show: true,
                        position: 'end',
                        formatter: 'Target: 11 blocks',
                        color: '#f59e0b',
                        fontSize: 11,
                        fontWeight: 'bold'
                      },
                      data: [
                        {
                          yAxis: 11,
                          name: 'Target'
                        }
                      ]
                    },
                    markArea: markAreaData.length > 0 ? {
                      silent: true,
                      itemStyle: {
                        color: 'rgba(59, 130, 246, 0.15)', // Light blue background
                        borderColor: 'rgba(59, 130, 246, 0.3)',
                        borderWidth: 1
                      },
                      label: {
                        show: false
                      },
                      data: markAreaData
                    } : undefined
                  }
                }),
                // Add average line
                {
                  name: 'Average',
                  type: 'line',
                  data: blocksChartData.averageLine,
                  lineStyle: {
                    color: '#6366f1',
                    width: 2,
                    type: 'solid'
                  },
                  itemStyle: {
                    color: '#6366f1'
                  },
                  symbol: 'circle',
                  symbolSize: 6,
                  label: {
                    show: true,
                    position: 'top',
                    formatter: (params: any) => {
                      const value = params.value || 0
                      return value > 0 ? value.toFixed(1) : ''
                    },
                    fontSize: 10,
                    color: '#6366f1',
                    fontWeight: 'bold'
                  },
                  tooltip: {
                    formatter: (params: any) => {
                      const value = params.value || 0
                      return `Average: ${value.toFixed(2)} blocks`
                    }
                  }
                }
              ]
            }}
            style={{ height: '450px', width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
        </div>
      )}

      {/* Net Profit vs Repair Costs Chart - Enhanced */}
      {truckProfitsData.length > 0 && (
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Profit Analysis by Truck</h2>
            <p className="text-sm text-gray-600">Showing profit before repairs, repair costs, and final net profit after repairs. Percentage indicates repair cost as % of profit before repairs.</p>
          </div>
          <ReactECharts
            option={{
              tooltip: {
                trigger: 'axis',
                axisPointer: {
                  type: 'shadow'
                },
                formatter: (params: any) => {
                  const truck = truckProfitsData.find((t) => t.truck_name === params[0]?.axisValue)
                  let result = `<strong>${params[0]?.axisValue}</strong><br/>`
                  
                  params.forEach((param: any) => {
                    const value = param.value || 0
                    const formatted = `$${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                    result += `${param.marker}${param.seriesName}: ${formatted}<br/>`
                  })
                  
                  // Add additional context
                  if (truck) {
                    const profitBeforeRepairs = truck.profit_before_repairs || (truck.total_revenue - (truck.settlement_expenses || truck.total_expenses - truck.repair_costs))
                    result += `<hr style="margin: 8px 0; border-color: #e5e7eb;"/>`
                    result += `Total Revenue: $${truck.total_revenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}<br/>`
                    result += `Settlement Expenses: $${(truck.settlement_expenses || truck.total_expenses - truck.repair_costs).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}<br/>`
                    result += `Profit Before Repairs: $${profitBeforeRepairs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}<br/>`
                    result += `Repair Costs: $${truck.repair_costs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}<br/>`
                    result += `<strong>Net Profit (After Repairs): $${truck.net_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>`
                    if (truck.repair_costs > 0 && profitBeforeRepairs > 0) {
                      const ratio = (truck.repair_costs / profitBeforeRepairs) * 100
                      result += `<br/>Repair Ratio: ${ratio.toFixed(1)}% of profit before repairs`
                    }
                  }
                  
                  return result
                },
                backgroundColor: '#fff',
                borderColor: '#e5e7eb',
                borderWidth: 1,
                borderRadius: 8,
                padding: [8, 12]
              },
              legend: {
                data: ['Profit Before Repairs', 'Repair Costs', 'Net Profit (After Repairs)'],
                top: 30,
                textStyle: {
                  fontSize: 12
                },
                selectedMode: true
              },
              grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                top: '15%',
                containLabel: true
              },
              xAxis: {
                type: 'category',
                data: truckProfitsData.map((t) => t.truck_name),
                axisLabel: {
                  rotate: truckProfitsData.length > 6 ? 45 : 0,
                  fontSize: 11
                }
              },
              yAxis: {
                type: 'value',
                name: 'Amount ($)',
                axisLabel: {
                  formatter: (value: number) => `$${Math.abs(value).toLocaleString()}`
                },
                splitLine: {
                  show: true,
                  lineStyle: {
                    type: 'dashed',
                    opacity: 0.3
                  }
                }
              },
              series: [
                {
                  name: 'Profit Before Repairs',
                  type: 'bar',
                  data: truckProfitsData.map((t) => t.profit_before_repairs || (t.total_revenue - (t.settlement_expenses || t.total_expenses - t.repair_costs))),
                  itemStyle: {
                    color: '#3b82f6',  // Blue for profit before repairs
                    borderRadius: [4, 4, 0, 0]
                  },
                  label: {
                    show: true,
                    position: 'top',
                    formatter: (params: any) => {
                      const value = params.value || 0
                      return value !== 0 ? `$${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : ''
                    },
                    fontSize: 9,
                    color: '#3b82f6'
                  }
                },
                {
                  name: 'Repair Costs',
                  type: 'bar',
                  data: truckProfitsData.map((t) => ({
                    value: t.repair_costs || 0,
                    profitBeforeRepairs: t.profit_before_repairs || (t.total_revenue - (t.settlement_expenses || t.total_expenses - t.repair_costs))
                  })),
                  itemStyle: {
                    color: '#f97316',
                    borderRadius: [4, 4, 0, 0]
                  },
                  label: {
                    show: true,
                    position: 'inside',
                    formatter: (params: any) => {
                      const repairCost = params.value?.value || params.value || 0
                      const profitBeforeRepairs = params.value?.profitBeforeRepairs || truckProfitsData[params.dataIndex]?.profit_before_repairs || (truckProfitsData[params.dataIndex]?.total_revenue - (truckProfitsData[params.dataIndex]?.settlement_expenses || truckProfitsData[params.dataIndex]?.total_expenses - truckProfitsData[params.dataIndex]?.repair_costs))
                      
                      if (repairCost === 0) return ''
                      
                      // Calculate percentage: (repair_cost / profit_before_repairs) * 100
                      let percentage = ''
                      if (profitBeforeRepairs > 0) {
                        const ratio = (repairCost / profitBeforeRepairs) * 100
                        percentage = `${ratio.toFixed(1)}%`
                      } else if (profitBeforeRepairs < 0) {
                        percentage = 'N/A'
                      } else {
                        percentage = profitBeforeRepairs === 0 && repairCost > 0 ? '∞' : ''
                      }
                      
                      return percentage
                    },
                    fontSize: 11,
                    fontWeight: 'bold',
                    color: '#fff',
                    textBorderColor: '#000',
                    textBorderWidth: 1
                  }
                },
                {
                  name: 'Net Profit (After Repairs)',
                  type: 'bar',
                  data: truckProfitsData.map((t) => t.net_profit),
                  itemStyle: {
                    color: (params: any) => {
                      const value = params.value || 0
                      return value >= 0 ? '#10b981' : '#ef4444'  // Green for positive, red for negative
                    },
                    borderRadius: [4, 4, 0, 0]
                  },
                  label: {
                    show: true,
                    position: 'top',
                    formatter: (params: any) => {
                      const value = params.value || 0
                      return value !== 0 ? `$${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : ''
                    },
                    fontSize: 9,
                    color: (params: any) => {
                      const value = params.value || 0
                      return value >= 0 ? '#10b981' : '#ef4444'
                    }
                  }
                }
              ]
            }}
            style={{ height: '500px', width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
          
          {/* Summary Stats */}
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4 pt-6 border-t border-gray-200">
            {truckProfitsData.map((truck) => {
              const profitBeforeRepairs = truck.profit_before_repairs || (truck.total_revenue - (truck.settlement_expenses || truck.total_expenses - truck.repair_costs))
              const repairRatio = profitBeforeRepairs > 0 && truck.repair_costs > 0 
                ? ((truck.repair_costs / profitBeforeRepairs) * 100).toFixed(1)
                : truck.repair_costs > 0 ? 'N/A' : '0'
              
              return (
                <div key={truck.truck_id} className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">{truck.truck_name}</h3>
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Profit Before Repairs:</span>
                      <span className="font-medium text-blue-600">
                        ${profitBeforeRepairs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Repair Costs:</span>
                      <span className="font-medium text-orange-600">
                        ${truck.repair_costs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between pt-1 border-t border-gray-200">
                      <span className="text-gray-700 font-medium">Actual Profit (After Repairs):</span>
                      <span className={`font-semibold ${truck.net_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ${truck.net_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    {truck.repair_costs > 0 && profitBeforeRepairs > 0 && (
                      <div className="flex justify-between pt-1 border-t border-gray-200">
                        <span className="text-gray-600">Repair Ratio:</span>
                        <span className="font-semibold text-gray-900">{repairRatio}%</span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Time-Series Charts Section */}
      {timeSeriesData && (
        <div className="mt-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-semibold text-gray-900">Time-Series Analytics</h2>
            <div className="inline-flex rounded-md shadow-sm" role="group">
              <button
                type="button"
                onClick={() => setActiveTimeView('weekly')}
                className={`px-4 py-2 text-sm font-medium border rounded-l-lg ${
                  activeTimeView === 'weekly'
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Weekly
              </button>
              <button
                type="button"
                onClick={() => setActiveTimeView('monthly')}
                className={`px-4 py-2 text-sm font-medium border rounded-r-lg ${
                  activeTimeView === 'monthly'
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Monthly
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Revenue Chart */}
            {currentData.labels.length > 0 && (
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-xl font-semibold text-gray-900 mb-4">Revenue Over Time</h3>
                {timeSeriesLoading ? (
                  <div className="text-center py-8 text-gray-500">Loading...</div>
                ) : (
                  <ReactECharts
                    option={{
                      tooltip: {
                        trigger: 'axis',
                        axisPointer: { type: 'cross' },
                        formatter: (params: any) => {
                          let result = `${params[0]?.axisValue}<br/>`
                          params.forEach((param: any) => {
                            const value = param.value || 0
                            result += `${param.marker}${param.seriesName}: $${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}<br/>`
                          })
                          return result
                        },
                        backgroundColor: '#fff',
                        borderColor: '#e5e7eb',
                        borderWidth: 1,
                        borderRadius: 8,
                        padding: [8, 12]
                      },
                      legend: {
                        data: ['Gross Revenue', 'Net Profit'],
                        top: 10
                      },
                      grid: {
                        left: '3%',
                        right: '4%',
                        bottom: '3%',
                        top: '15%',
                        containLabel: true
                      },
                      xAxis: {
                        type: 'category',
                        data: currentData.labels,
                        axisLabel: {
                          rotate: currentData.labels.length > 10 ? 45 : 0,
                          fontSize: 11
                        }
                      },
                      yAxis: {
                        type: 'value',
                        name: 'Amount ($)',
                        axisLabel: {
                          formatter: (value: number) => `$${value.toLocaleString()}`
                        }
                      },
                      series: [
                        {
                          name: 'Gross Revenue',
                          type: 'line',
                          smooth: true,
                          data: currentData.grossRevenue,
                          itemStyle: { color: '#3b82f6' },
                          lineStyle: { width: 2 }
                        },
                        {
                          name: 'Net Profit',
                          type: 'line',
                          smooth: true,
                          data: currentData.netProfit,
                          itemStyle: { color: '#10b981' },
                          lineStyle: { width: 2 }
                        }
                      ]
                    }}
                    style={{ height: '400px', width: '100%' }}
                    opts={{ renderer: 'svg' }}
                  />
                )}
              </div>
            )}

            {/* Driver Pay Chart */}
            {currentData.labels.length > 0 && (
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-xl font-semibold text-gray-900 mb-4">Driver Pay Over Time</h3>
                {timeSeriesLoading ? (
                  <div className="text-center py-8 text-gray-500">Loading...</div>
                ) : (
                  <ReactECharts
                    option={{
                      tooltip: {
                        trigger: 'axis',
                        axisPointer: { type: 'cross' },
                        formatter: (params: any) => {
                          let result = `${params[0]?.axisValue}<br/>`
                          params.forEach((param: any) => {
                            const value = param.value || 0
                            result += `${param.marker}${param.seriesName}: $${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}<br/>`
                          })
                          return result
                        },
                        backgroundColor: '#fff',
                        borderColor: '#e5e7eb',
                        borderWidth: 1,
                        borderRadius: 8,
                        padding: [8, 12]
                      },
                      legend: {
                        data: ["Driver's Pay", 'Payroll Fee'],
                        top: 10
                      },
                      grid: {
                        left: '3%',
                        right: '4%',
                        bottom: '3%',
                        top: '15%',
                        containLabel: true
                      },
                      xAxis: {
                        type: 'category',
                        data: currentData.labels,
                        axisLabel: {
                          rotate: currentData.labels.length > 10 ? 45 : 0,
                          fontSize: 11
                        }
                      },
                      yAxis: {
                        type: 'value',
                        name: 'Amount ($)',
                        axisLabel: {
                          formatter: (value: number) => `$${value.toLocaleString()}`
                        }
                      },
                      series: [
                        {
                          name: "Driver's Pay",
                          type: 'line',
                          smooth: true,
                          data: currentData.driverPay,
                          itemStyle: { color: '#3b82f6' },
                          lineStyle: { width: 2 }
                        },
                        {
                          name: 'Payroll Fee',
                          type: 'line',
                          smooth: true,
                          data: currentData.payrollFee,
                          itemStyle: { color: '#f97316' },
                          lineStyle: { width: 2 }
                        }
                      ]
                    }}
                    style={{ height: '400px', width: '100%' }}
                    opts={{ renderer: 'svg' }}
                  />
                )}
              </div>
            )}
          </div>

          {/* Expenses Chart - Full Width */}
          {currentData.labels.length > 0 && (
            <div className="bg-white p-6 rounded-lg shadow mb-6">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Expenses Over Time</h3>
              {timeSeriesLoading ? (
                <div className="text-center py-8 text-gray-500">Loading...</div>
              ) : (
                <ReactECharts
                  option={{
                    tooltip: {
                      trigger: 'axis',
                      axisPointer: { type: 'cross' },
                      formatter: (params: any) => {
                        let result = `${params[0]?.axisValue}<br/>`
                        params.forEach((param: any) => {
                          const value = param.value || 0
                          if (value > 0) {
                            result += `${param.marker}${param.seriesName}: $${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}<br/>`
                          }
                        })
                        return result
                      },
                      backgroundColor: '#fff',
                      borderColor: '#e5e7eb',
                      borderWidth: 1,
                      borderRadius: 8,
                      padding: [8, 12]
                    },
                    legend: {
                      data: ['Fuel', 'Dispatch Fee', 'Insurance', 'Safety', 'Prepass', 'IFTA', 'Truck Parking', 'Custom'],
                      top: 10,
                      type: 'scroll',
                      orient: 'horizontal'
                    },
                    grid: {
                      left: '3%',
                      right: '4%',
                      bottom: '15%',
                      top: '20%',
                      containLabel: true
                    },
                    xAxis: {
                      type: 'category',
                      data: currentData.labels,
                      axisLabel: {
                        rotate: currentData.labels.length > 10 ? 45 : 0,
                        fontSize: 11
                      }
                    },
                    yAxis: {
                      type: 'value',
                      name: 'Amount ($)',
                      axisLabel: {
                        formatter: (value: number) => `$${value.toLocaleString()}`
                      }
                    },
                    series: [
                      {
                        name: 'Fuel',
                        type: 'line',
                        smooth: true,
                        data: currentData.expenses?.fuel || [],
                        itemStyle: { color: '#3b82f6' }
                      },
                      {
                        name: 'Dispatch Fee',
                        type: 'line',
                        smooth: true,
                        data: currentData.expenses?.dispatch_fee || [],
                        itemStyle: { color: '#f59e0b' }
                      },
                      {
                        name: 'Insurance',
                        type: 'line',
                        smooth: true,
                        data: currentData.expenses?.insurance || [],
                        itemStyle: { color: '#f97316' }
                      },
                      {
                        name: 'Safety',
                        type: 'line',
                        smooth: true,
                        data: currentData.expenses?.safety || [],
                        itemStyle: { color: '#eab308' }
                      },
                      {
                        name: 'Prepass',
                        type: 'line',
                        smooth: true,
                        data: currentData.expenses?.prepass || [],
                        itemStyle: { color: '#84cc16' }
                      },
                      {
                        name: 'IFTA',
                        type: 'line',
                        smooth: true,
                        data: currentData.expenses?.ifta || [],
                        itemStyle: { color: '#10b981' }
                      },
                      {
                        name: 'Truck Parking',
                        type: 'line',
                        smooth: true,
                        data: currentData.expenses?.truck_parking || [],
                        itemStyle: { color: '#a855f7' }
                      },
                      {
                        name: 'Custom',
                        type: 'line',
                        smooth: true,
                        data: currentData.expenses?.custom || [],
                        itemStyle: { color: '#6b7280' }
                      }
                    ]
                  }}
                  style={{ height: '450px', width: '100%' }}
                  opts={{ renderer: 'svg' }}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
