import { useEffect, useState } from 'react'
import { analyticsApi, trucksApi, Truck, TimeSeriesData } from '../services/api'
import ReactECharts from 'echarts-for-react'
import { useMobile } from '../utils/useMobile'

// Type definitions for dashboard data structures
interface RepairByMonth {
  repair_id?: number
  truck_id: number
  month_key: string
  month: string
  category?: string
  cost: number
  truck_name?: string
  description?: string
  repair_date?: string
}

interface BlockWithDate {
  block_id: string
  delivery_date?: string
}

interface BlockByTruckMonth {
  truck_id: number
  month_key: string
  month: string
  blocks: number
  block_ids?: (string | BlockWithDate)[]  // Array of block IDs (strings) or block objects with delivery dates
  truck_name?: string
}

interface ExpenseData {
  fuel: number[]
  dispatch_fee: number[]
  insurance: number[]
  safety: number[]
  prepass: number[]
  ifta: number[]
  loan_interest: number[]
  truck_parking: number[]
  custom: number[]
}

export default function Dashboard() {
  const isMobile = useMobile()
  const [data, setData] = useState<any>(null)
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [selectedTruck, setSelectedTruck] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesData | null>(null)
  const [timeSeriesLoading, setTimeSeriesLoading] = useState(false)
  const [activeTimeView, setActiveTimeView] = useState<'weekly' | 'monthly'>('weekly')
  const [showProfitDetails, setShowProfitDetails] = useState(false) // Collapsed by default, especially on mobile
  const [selectedCategories, setSelectedCategories] = useState<{ [key: string]: boolean }>({})
  const [selectedExpensePeriod, setSelectedExpensePeriod] = useState<string>('')
  const [expenseAnalysisView, setExpenseAnalysisView] = useState<'weekly' | 'monthly' | 'yearly' | 'all_time'>('weekly')
  // Collapse sections by default on mobile, expand on desktop
  const [settlementsInfoExpanded, setSettlementsInfoExpanded] = useState<boolean>(!isMobile)
  const [vehicleTypeFilter, setVehicleTypeFilter] = useState<'trucks' | 'trailers'>('trucks') // Filter for graphs and expense details - no 'all' option
  const [selectedBlockData, setSelectedBlockData] = useState<BlockByTruckMonth | null>(null) // Track clicked block data
  const [showBlockDetails, setShowBlockDetails] = useState<boolean>(false) // Show/hide block details table
  const [expenseDetailsExpanded, setExpenseDetailsExpanded] = useState<boolean>(!isMobile) // Collapsed by default on mobile
  const [repairExpensesExpanded, setRepairExpensesExpanded] = useState<boolean>(!isMobile) // Collapsed by default on mobile
  const [periodDetailsExpanded, setPeriodDetailsExpanded] = useState<boolean>(!isMobile) // Collapsed by default on mobile
  const [windowWidth, setWindowWidth] = useState<number>(typeof window !== 'undefined' ? window.innerWidth : 1024)

  useEffect(() => {
    loadTrucks()
    loadDashboard()
  }, [selectedTruck, vehicleTypeFilter])

  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    // Reset selected period when vehicle type filter changes, so it gets re-initialized with new data
    setSelectedExpensePeriod('')
    // Set default view based on vehicle type: weekly for trucks, monthly for trailers
    if (vehicleTypeFilter === 'trucks' && expenseAnalysisView === 'monthly') {
      setExpenseAnalysisView('weekly')
    } else if (vehicleTypeFilter === 'trailers' && expenseAnalysisView === 'weekly') {
      setExpenseAnalysisView('monthly')
    }
    loadTimeSeries()
  }, [selectedTruck, vehicleTypeFilter])

  // Initialize selected categories when expense data changes
  useEffect(() => {
    let expenseCategories: any = {}
    if (vehicleTypeFilter === 'trucks' && data?.trucks?.expense_categories) {
      expenseCategories = data.trucks.expense_categories
    } else if (vehicleTypeFilter === 'trailers' && data?.trailers?.expense_categories) {
      expenseCategories = data.trailers.expense_categories
    } else if (data?.expense_categories) {
      expenseCategories = data.expense_categories
    }
    
    if (expenseCategories && Object.keys(expenseCategories).length > 0) {
      const categories = [
        { name: 'Fuel', value: expenseCategories.fuel || 0 },
        { name: 'Repairs', value: expenseCategories.repairs || 0 },
        { name: 'Dispatch Fee', value: expenseCategories.dispatch_fee || 0 },
        { name: 'Insurance', value: expenseCategories.insurance || 0 },
        { name: 'Safety', value: expenseCategories.safety || 0 },
        { name: 'Prepass', value: expenseCategories.prepass || 0 },
        { name: 'IFTA', value: expenseCategories.ifta || 0 },
        { name: "Driver's Pay", value: expenseCategories.driver_pay || 0 },
        { name: 'Payroll Fee', value: expenseCategories.payroll_fee || 0 },
        { name: 'Loan Interest', value: expenseCategories.loan_interest || 0 },
        { name: 'Truck Parking', value: expenseCategories.truck_parking || 0 },
        { name: 'Custom', value: expenseCategories.custom || expenseCategories.other || 0 },
      ].filter(item => item.value > 0).sort((a, b) => b.value - a.value)
      
      if (categories.length > 0) {
        const initial: { [key: string]: boolean } = {}
        categories.forEach(item => {
          initial[item.name] = true
        })
        setSelectedCategories(initial)
      }
    }
  }, [data, vehicleTypeFilter])

  // Initialize selected period to most recent
  useEffect(() => {
    if (timeSeriesData && !selectedExpensePeriod) {
      // For "All Time", don't set a period
      if (expenseAnalysisView === 'all_time') {
        return
      }
      
      const periods = expenseAnalysisView === 'weekly' 
        ? (Array.isArray(timeSeriesData.by_week) ? timeSeriesData.by_week : [])
        : expenseAnalysisView === 'monthly'
        ? (Array.isArray(timeSeriesData.by_month) ? timeSeriesData.by_month : [])
        : (Array.isArray(timeSeriesData.by_year) ? timeSeriesData.by_year : [])
      
      if (periods.length > 0) {
        const periodKey = expenseAnalysisView === 'weekly' ? 'week_key' : expenseAnalysisView === 'monthly' ? 'month_key' : 'year_key'
        setSelectedExpensePeriod((periods[periods.length - 1] as any)[periodKey])
      }
    }
  }, [timeSeriesData, expenseAnalysisView, selectedExpensePeriod, vehicleTypeFilter])

  // Reset selected period when view or vehicle type filter changes
  useEffect(() => {
    if (timeSeriesData) {
      // For "All Time", clear the selected period
      if (expenseAnalysisView === 'all_time') {
        setSelectedExpensePeriod('')
        return
      }
      
      const periods = expenseAnalysisView === 'weekly' 
        ? (Array.isArray(timeSeriesData.by_week) ? timeSeriesData.by_week : [])
        : expenseAnalysisView === 'monthly'
        ? (Array.isArray(timeSeriesData.by_month) ? timeSeriesData.by_month : [])
        : (Array.isArray(timeSeriesData.by_year) ? timeSeriesData.by_year : [])
      
      if (periods.length > 0) {
        const periodKey = expenseAnalysisView === 'weekly' ? 'week_key' : expenseAnalysisView === 'monthly' ? 'month_key' : 'year_key'
        const currentPeriod = periods.find(p => (p as any)[periodKey] === selectedExpensePeriod)
        if (!currentPeriod) {
          // Period doesn't exist in new data, reset to most recent
          setSelectedExpensePeriod((periods[periods.length - 1] as any)[periodKey])
        }
      } else if (selectedExpensePeriod) {
        // No periods available, clear selection
        setSelectedExpensePeriod('')
      }
    }
    // Collapse settlements info and repair expenses when view or period changes
    setSettlementsInfoExpanded(false)
    setRepairExpensesExpanded(false)
  }, [expenseAnalysisView, timeSeriesData, selectedExpensePeriod, vehicleTypeFilter])

  const loadTrucks = async () => {
    try {
      const response = await trucksApi.getAll()
      setTrucks(Array.isArray(response.data) ? response.data : [])
    } catch (err) {
      console.error(err)
      setTrucks([])
    }
  }

  const loadDashboard = async () => {
    try {
      setLoading(true)
      const vehicleType = vehicleTypeFilter === 'trucks' ? 'truck' : 'trailer'
      const response = await analyticsApi.getDashboard(selectedTruck || undefined, vehicleType)
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
      // Map vehicle type filter to backend parameter
      const vehicleType = vehicleTypeFilter === 'trucks' ? 'truck' : vehicleTypeFilter === 'trailers' ? 'trailer' : undefined
      const response = await analyticsApi.getTimeSeries(undefined, selectedTruck || undefined, vehicleType)
      // Ensure response.data has array properties
      const data = response.data || {}
      setTimeSeriesData({
        by_week: Array.isArray(data.by_week) ? data.by_week : [],
        by_month: Array.isArray(data.by_month) ? data.by_month : [],
        by_year: Array.isArray(data.by_year) ? data.by_year : [],
      })
    } catch (err) {
      console.error('Failed to load time-series data:', err)
      setTimeSeriesData({
        by_week: [],
        by_month: [],
        by_year: [],
      })
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

  // Get expense categories based on vehicle type filter
  const getExpenseCategoriesData = () => {
    let expenseCategories: any = {}
    if (vehicleTypeFilter === 'trucks' && data?.trucks?.expense_categories) {
      expenseCategories = data.trucks.expense_categories
    } else if (vehicleTypeFilter === 'trailers' && data?.trailers?.expense_categories) {
      expenseCategories = data.trailers.expense_categories
    } else if (data?.expense_categories) {
      expenseCategories = data.expense_categories
    }
    
    // For trailers, only show repairs and custom expenses
    if (vehicleTypeFilter === 'trailers') {
      return [
        { name: 'Repairs', value: expenseCategories.repairs || 0, color: '#ef4444' },
        { name: 'Custom Expenses', value: expenseCategories.custom || expenseCategories.other || 0, color: '#6b7280' },
      ].filter(item => item.value > 0).sort((a, b) => b.value - a.value)
    }
    
    // For trucks, show all categories
    return expenseCategories && Object.keys(expenseCategories).length > 0 ? [
      { name: 'Fuel', value: expenseCategories.fuel || 0, color: '#3b82f6' },
      { name: 'Repairs', value: expenseCategories.repairs || 0, color: '#ef4444' },
      { name: 'Dispatch Fee', value: expenseCategories.dispatch_fee || 0, color: '#f59e0b' },
      { name: 'Insurance', value: expenseCategories.insurance || 0, color: '#f97316' },
      { name: 'Safety', value: expenseCategories.safety || 0, color: '#eab308' },
      { name: 'Prepass', value: expenseCategories.prepass || 0, color: '#84cc16' },
      { name: 'IFTA', value: expenseCategories.ifta || 0, color: '#10b981' },
      { name: "Driver's Pay", value: expenseCategories.driver_pay || 0, color: '#8b5cf6' },
      { name: 'Payroll Fee', value: expenseCategories.payroll_fee || 0, color: '#ec4899' },
      { name: 'Loan Interest', value: expenseCategories.loan_interest || 0, color: '#fbbf24' },
      { name: 'Truck Parking', value: expenseCategories.truck_parking || 0, color: '#a855f7' },
      { name: 'Custom', value: expenseCategories.custom || expenseCategories.other || 0, color: '#6b7280' },
    ].filter(item => item.value > 0).sort((a, b) => b.value - a.value) : []
  }
  
  const expenseCategoriesData = getExpenseCategoriesData()

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

  const processWeeklyData = (data: TimeSeriesData | null): { labels: string[], grossRevenue: number[], netProfit: number[], driverPay: number[], payrollFee: number[], expenses: ExpenseData } => {
    if (!data || !Array.isArray(data.by_week) || data.by_week.length === 0) {
      return { labels: [], grossRevenue: [], netProfit: [], driverPay: [], payrollFee: [], expenses: { fuel: [], dispatch_fee: [], insurance: [], safety: [], prepass: [], ifta: [], loan_interest: [], truck_parking: [], custom: [] } }
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
      loan_interest: data.by_week.map((item) => item.loan_interest || 0),
      truck_parking: data.by_week.map((item) => item.truck_parking),
      custom: data.by_week.map((item) => item.custom),
    }
    
    return { labels, grossRevenue, netProfit, driverPay, payrollFee, expenses }
  }

  const processMonthlyData = (data: TimeSeriesData | null): { labels: string[], grossRevenue: number[], netProfit: number[], driverPay: number[], payrollFee: number[], expenses: ExpenseData } => {
    if (!data || !Array.isArray(data.by_month) || data.by_month.length === 0) {
      return { labels: [], grossRevenue: [], netProfit: [], driverPay: [], payrollFee: [], expenses: { fuel: [], dispatch_fee: [], insurance: [], safety: [], prepass: [], ifta: [], loan_interest: [], truck_parking: [], custom: [] } }
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
      loan_interest: data.by_month.map((item) => item.loan_interest || 0),
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
    // For "All Time", aggregate from timeSeriesData to keep it in sync with period views
    if (expenseAnalysisView === 'all_time') {
      if (timeSeriesData) {
        const source = Array.isArray(timeSeriesData.by_month) ? timeSeriesData.by_month : []
        if (source.length > 0) {
          const sumField = (field: string) => source.reduce((sum, period) => sum + (Number((period as any)[field]) || 0), 0)
          const trucksSet = new Set<number>()
          source.forEach((period: any) => {
            if (Array.isArray(period.trucks)) {
              period.trucks.forEach((t: any) => {
                if (t.truck_id !== undefined) trucksSet.add(t.truck_id)
              })
            }
          })
          
          const grossRevenue = sumField('gross_revenue')
          const netProfit = sumField('net_profit')
          
          return {
            all_time_key: 'all_time',
            all_time_label: 'All Time',
            gross_revenue: grossRevenue,
            net_profit: netProfit,
            total_expenses: grossRevenue - netProfit,
            driver_pay: sumField('driver_pay'),
            payroll_fee: sumField('payroll_fee'),
            fuel: sumField('fuel'),
            dispatch_fee: sumField('dispatch_fee'),
            insurance: sumField('insurance'),
            safety: sumField('safety'),
            prepass: sumField('prepass'),
            ifta: sumField('ifta'),
            loan_interest: sumField('loan_interest'),
            truck_parking: sumField('truck_parking'),
            custom: sumField('custom'),
            repairs: sumField('repairs'),
            trucks: Array.from(trucksSet).map(truck_id => ({ truck_id, truck_name: `Truck ${truck_id}` }))
          }
        }
      }
      
      // Fallback to dashboard data if time series not available
      if (!data) return null
      
      // Get expense categories based on vehicle type filter
      let expenseCategories: any = {}
      let grossRevenue = 0
      let netProfit = 0
      let truckProfits: any[] = []
      
      if (vehicleTypeFilter === 'trucks' && data.trucks) {
        expenseCategories = data.trucks.expense_categories || {}
        grossRevenue = data.trucks.total_revenue || 0
        netProfit = data.trucks.net_profit || 0
        truckProfits = data.trucks.truck_profits || []
      } else if (vehicleTypeFilter === 'trailers' && data.trailers) {
        expenseCategories = data.trailers.expense_categories || {}
        grossRevenue = data.trailers.total_revenue || 0
        netProfit = data.trailers.net_profit || 0
        truckProfits = data.trailers.trailer_profits || []
      } else {
        // Fallback - should not happen since 'all' is removed
        expenseCategories = {}
        grossRevenue = 0
        netProfit = 0
        truckProfits = []
      }
      
      const aggregated = {
        all_time_key: 'all_time',
        all_time_label: 'All Time',
        gross_revenue: grossRevenue,
        net_profit: netProfit,
        total_expenses: (() => {
          // Use backend's calculated total_expenses if available, otherwise calculate from categories
          if (vehicleTypeFilter === 'trucks' && data.trucks) {
            return data.trucks.total_expenses || 0
          } else if (vehicleTypeFilter === 'trailers' && data.trailers) {
            return data.trailers.total_expenses || 0
          } else {
            return 0
          }
        })(),
        driver_pay: expenseCategories.driver_pay || 0,
        payroll_fee: expenseCategories.payroll_fee || 0,
        fuel: expenseCategories.fuel || 0,
        dispatch_fee: expenseCategories.dispatch_fee || 0,
        insurance: expenseCategories.insurance || 0,
        safety: expenseCategories.safety || 0,
        prepass: expenseCategories.prepass || 0,
        ifta: expenseCategories.ifta || 0,
        loan_interest: expenseCategories.loan_interest || 0,
        truck_parking: expenseCategories.truck_parking || 0,
        service_on_truck: expenseCategories.service_on_truck || 0,
        custom: expenseCategories.custom || 0,
        repairs: expenseCategories.repairs || 0,
        trucks: (Array.isArray(truckProfits) ? truckProfits : []).map((tp: any) => ({
          truck_id: tp.truck_id,
          truck_name: tp.truck_name
        }))
      }
      
      return aggregated
    }
    
    if (!timeSeriesData) return null
    
    if (!selectedExpensePeriod) return null
    
    const periods = expenseAnalysisView === 'weekly' 
      ? (Array.isArray(timeSeriesData.by_week) ? timeSeriesData.by_week : [])
      : expenseAnalysisView === 'monthly'
      ? (Array.isArray(timeSeriesData.by_month) ? timeSeriesData.by_month : [])
      : (Array.isArray(timeSeriesData.by_year) ? timeSeriesData.by_year : [])
    
    const periodKey = expenseAnalysisView === 'weekly' ? 'week_key' : expenseAnalysisView === 'monthly' ? 'month_key' : 'year_key'
    return periods.find(p => (p as any)[periodKey] === selectedExpensePeriod) || null
  }

  const selectedPeriodData = getSelectedPeriodData()

  return (
    <div>
      <div className="flex justify-between items-center mb-4 sm:mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Dashboard</h1>
        <select
          value={selectedTruck || ''}
          onChange={(e) => setSelectedTruck(e.target.value ? Number(e.target.value) : null)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        >
          <option value="">All Trucks</option>
          {trucks.map((truck) => (
            <option key={truck.id} value={truck.id}>
              {truck.name}
            </option>
          ))}
        </select>
      </div>

      {/* Detailed Expense Analysis Section - First Chart */}
      {timeSeriesData && (
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <div className="flex flex-col mb-6 gap-4">
            <h2 className="text-2xl font-semibold text-gray-900">Detailed Expense Analysis</h2>
            <div className="flex flex-col md:flex-row gap-3 md:items-center">
              {/* Vehicle Type Filter - Removed "All" option */}
              <div className="w-full md:w-auto flex rounded-md shadow-sm" role="group">
                <button
                  type="button"
                  onClick={() => setVehicleTypeFilter('trucks')}
                  className={`flex-1 md:flex-none px-3 py-2 text-xs sm:text-sm font-medium border rounded-l-lg ${
                    vehicleTypeFilter === 'trucks'
                      ? 'bg-green-600 text-white border-green-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  🚚 Trucks
                </button>
                <button
                  type="button"
                  onClick={() => setVehicleTypeFilter('trailers')}
                  className={`flex-1 md:flex-none px-3 py-2 text-xs sm:text-sm font-medium border rounded-r-lg ${
                    vehicleTypeFilter === 'trailers'
                      ? 'bg-green-600 text-white border-green-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  🚛 Trailers
                </button>
              </div>
              {/* Time Range Filter - Simplified on mobile, timeline style on desktop */}
              <div className="hidden md:flex items-center justify-center gap-2">
                {vehicleTypeFilter === 'trucks' && (
                  <>
                    <button
                      type="button"
                      onClick={() => setExpenseAnalysisView('weekly')}
                      className={`flex flex-col items-center gap-1 ${
                        expenseAnalysisView === 'weekly' ? 'text-blue-600' : 'text-gray-500 hover:text-gray-700'
                      }`}
                      title="Weekly"
                    >
                      <div className={`w-4 h-4 rounded-full border-2 ${
                        expenseAnalysisView === 'weekly'
                          ? 'bg-blue-600 border-blue-600'
                          : 'bg-white border-gray-300 hover:border-gray-400'
                      }`} />
                      <span className="text-xs font-medium">Weekly</span>
                    </button>
                    <div className="h-px w-8 bg-gray-300" />
                  </>
                )}
                <button
                  type="button"
                  onClick={() => setExpenseAnalysisView('monthly')}
                  className={`flex flex-col items-center gap-1 ${
                    expenseAnalysisView === 'monthly' ? 'text-blue-600' : 'text-gray-500 hover:text-gray-700'
                  }`}
                  title="Monthly"
                >
                  <div className={`w-4 h-4 rounded-full border-2 ${
                    expenseAnalysisView === 'monthly'
                      ? 'bg-blue-600 border-blue-600'
                      : 'bg-white border-gray-300 hover:border-gray-400'
                  }`} />
                  <span className="text-xs font-medium">Monthly</span>
                </button>
                <div className="h-px w-8 bg-gray-300" />
                <button
                  type="button"
                  onClick={() => setExpenseAnalysisView('yearly')}
                  className={`flex flex-col items-center gap-1 ${
                    expenseAnalysisView === 'yearly' ? 'text-blue-600' : 'text-gray-500 hover:text-gray-700'
                  }`}
                  title="Yearly"
                >
                  <div className={`w-4 h-4 rounded-full border-2 ${
                    expenseAnalysisView === 'yearly'
                      ? 'bg-blue-600 border-blue-600'
                      : 'bg-white border-gray-300 hover:border-gray-400'
                  }`} />
                  <span className="text-xs font-medium">Yearly</span>
                </button>
                <div className="h-px w-8 bg-gray-300" />
                <button
                  type="button"
                  onClick={() => setExpenseAnalysisView('all_time')}
                  className={`flex flex-col items-center gap-1 ${
                    expenseAnalysisView === 'all_time' ? 'text-blue-600' : 'text-gray-500 hover:text-gray-700'
                  }`}
                  title="All Time"
                >
                  <div className={`w-4 h-4 rounded-full border-2 ${
                    expenseAnalysisView === 'all_time'
                      ? 'bg-blue-600 border-blue-600'
                      : 'bg-white border-gray-300 hover:border-gray-400'
                  }`} />
                  <span className="text-xs font-medium">All Time</span>
                </button>
              </div>
              {/* Mobile: Simplified dropdown for time range */}
              <div className="md:hidden w-full">
                <select
                  value={expenseAnalysisView}
                  onChange={(e) => setExpenseAnalysisView(e.target.value as 'weekly' | 'monthly' | 'yearly' | 'all_time')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  {vehicleTypeFilter === 'trucks' && <option value="weekly">Weekly</option>}
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                  <option value="all_time">All Time</option>
                </select>
              </div>
              {/* Period Selector */}
              {expenseAnalysisView !== 'all_time' && (
              <select
                value={selectedExpensePeriod}
                onChange={(e) => setSelectedExpensePeriod(e.target.value)}
                className="w-full md:w-auto px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
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
                <div 
                  onClick={() => setPeriodDetailsExpanded(!periodDetailsExpanded)}
                  className="cursor-pointer flex items-center justify-between"
                >
                  <p className="text-sm text-gray-700">
                    <strong>Period Selected:</strong> {expenseAnalysisView === 'all_time'
                      ? 'All Time'
                      : expenseAnalysisView === 'weekly' 
                      ? (() => {
                          const label = (selectedPeriodData as any).week_label || ''
                          // Extract just the date part (e.g., "Jan 1, 2024" from "Week of Jan 1, 2024")
                          const dateMatch = label.match(/([A-Za-z]{3}\s+\d{1,2},\s+\d{4})/)
                          return dateMatch ? dateMatch[1] : label
                        })()
                      : expenseAnalysisView === 'monthly'
                      ? (() => {
                          const label = (selectedPeriodData as any).month_label || ''
                          // Extract just the month/year (e.g., "Jan 2024" from "January 2024" or "Jan 2024")
                          const monthMatch = label.match(/([A-Za-z]{3,9}\s+\d{4})/)
                          return monthMatch ? monthMatch[1] : label
                        })()
                      : (selectedPeriodData as any).year_label || ''}
                  </p>
                  <span className="text-gray-500 text-xs">
                    {periodDetailsExpanded ? '▼' : '▶'} {periodDetailsExpanded ? 'Hide' : 'Details'}
                  </span>
                </div>
                {periodDetailsExpanded && (
                  <div className="mt-3 pt-3 border-t border-gray-300">
                    <p className="text-sm text-gray-700">
                      <strong>Full Period:</strong> {expenseAnalysisView === 'all_time'
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
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
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
                    ${(() => {
                      const pd = selectedPeriodData as any
                      const revenue = pd.gross_revenue || 0
                      const profit = pd.net_profit || 0
                      
                      // For trailers, calculate as revenue - profit if total_expenses is not available or seems incorrect
                      if (vehicleTypeFilter === 'trailers') {
                        // Use backend's calculated total_expenses if available and > 0
                        if (pd.total_expenses !== undefined && pd.total_expenses > 0) {
                          return pd.total_expenses
                        }
                        
                        // Fallback: calculate from revenue - profit
                        const calculated = revenue - profit
                        if (calculated > 0) {
                          return calculated
                        }
                        
                        // Last resort: sum repairs and custom expenses
                        const sum = (
                          (Number(pd.custom) || 0) +
                          (expenseAnalysisView === 'yearly' || expenseAnalysisView === 'monthly' || expenseAnalysisView === 'all_time' ? (Number(pd.repairs) || 0) : 0)
                        )
                        return isNaN(sum) ? 0 : sum
                      }
                      
                      // For trucks, use backend's calculated total_expenses if available and > 0
                      if (pd.total_expenses !== undefined && pd.total_expenses > 0) {
                        return pd.total_expenses
                      }
                      
                      // For trucks, sum all categories
                      const sum = (
                        (Number(pd.fuel) || 0) +
                        (Number(pd.dispatch_fee) || 0) +
                        (Number(pd.insurance) || 0) +
                        (Number(pd.safety) || 0) +
                        (Number(pd.prepass) || 0) +
                        (Number(pd.ifta) || 0) +
                        (Number(pd.loan_interest) || 0) +
                        (Number(pd.truck_parking) || 0) +
                        (Number(pd.custom) || 0) +
                        (Number(pd.driver_pay) || 0) +
                        (Number(pd.payroll_fee) || 0) +
                        // Repairs are only included for yearly/monthly/all_time, not weekly
                        (expenseAnalysisView === 'yearly' || expenseAnalysisView === 'monthly' || expenseAnalysisView === 'all_time' ? (Number(pd.repairs) || 0) : 0)
                      )
                      return isNaN(sum) ? 0 : sum
                    })().toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{expenseAnalysisView === 'all_time' ? 'All time cumulative' : `For this ${expenseAnalysisView === 'weekly' ? 'week' : expenseAnalysisView === 'monthly' ? 'month' : 'year'} only`}</div>
                </div>
              </div>

              {/* Net Profit Details & Repair Expenses - Only show for trucks in weekly/monthly/yearly view */}
              {vehicleTypeFilter === 'trucks' && (expenseAnalysisView === 'weekly' || expenseAnalysisView === 'monthly' || expenseAnalysisView === 'yearly') && selectedPeriodData && (() => {
                const periodKey = expenseAnalysisView === 'weekly' 
                  ? (selectedPeriodData as any).week_key 
                  : expenseAnalysisView === 'monthly' 
                  ? (selectedPeriodData as any).month_key 
                  : (selectedPeriodData as any).year_key
                const periodLabel = expenseAnalysisView === 'weekly' 
                  ? ((selectedPeriodData as any).week_label || 'Selected Week')
                  : expenseAnalysisView === 'monthly'
                  ? ((selectedPeriodData as any).month_label || 'Selected Month')
                  : ((selectedPeriodData as any).year_label || 'Selected Year')
                const loanInterest = Number((selectedPeriodData as any).loan_interest) || 0
                const netProfitValue = Number(selectedPeriodData.net_profit) || 0
                
                // Filter repairs for the selected period
                let repairsForPeriod: RepairByMonth[] = []
                
                if (expenseAnalysisView === 'monthly') {
                  // For monthly view, filter by month_key
                  repairsForPeriod = repairsByMonth.filter((repair: RepairByMonth) => repair.month_key === periodKey)
                } else if (expenseAnalysisView === 'yearly') {
                  // For yearly view, filter by year extracted from repair_date
                  // year_key is in format "YYYY"
                  repairsForPeriod = repairsByMonth.filter((repair: RepairByMonth) => {
                    if (!repair.repair_date) return false
                    const repairYear = new Date(repair.repair_date).getFullYear().toString()
                    return repairYear === periodKey
                  })
                } else if (expenseAnalysisView === 'weekly') {
                  // For weekly view, match repairs to the week by finding repairs whose repair_date
                  // falls within the week range. week_key is the settlement_date (ISO format),
                  // which represents the end of the pay period. We'll match repairs that fall
                  // within 7 days before the settlement_date (the pay period)
                  const weekSettlementDate = new Date(periodKey)
                  const weekStart = new Date(weekSettlementDate.getTime() - 7 * 24 * 60 * 60 * 1000) // 7 days before settlement
                  const weekEnd = new Date(weekSettlementDate) // Settlement date is the end of the week
                  
                  // Filter repairs that fall within this week range
                  repairsForPeriod = repairsByMonth.filter((repair: RepairByMonth) => {
                    if (!repair.repair_date) return false
                    const repairDate = new Date(repair.repair_date)
                    return repairDate >= weekStart && repairDate <= weekEnd
                  })
                }
                
                // Calculate repairs total from filtered repairs to ensure consistency with displayed repairs
                const repairs = repairsForPeriod.reduce((sum, repair) => sum + (Number(repair.cost) || 0), 0)
                
                return (
                  <div className="mb-6 bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">
                      Net Profit Details - {periodLabel}
                    </h3>
                    
                    {/* Net Profit Breakdown */}
                    <div className="mb-6 space-y-3">
                      <div className="flex justify-between items-center py-2 border-b border-gray-200">
                        <span className="text-sm font-medium text-gray-700">Settlement Net Profit</span>
                        <span className="text-sm font-semibold text-gray-900">
                          ${(netProfitValue + loanInterest + repairs).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </span>
                      </div>
                      
                      {loanInterest > 0 && (
                        <div className="flex justify-between items-center py-2 border-b border-gray-200">
                          <span className="text-sm text-gray-600">Less: Loan Interest</span>
                          <span className="text-sm font-medium text-red-600">
                            -${loanInterest.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      )}
                      
                      {repairs > 0 && (
                        <div className="flex justify-between items-center py-2 border-b border-gray-200">
                          <span className="text-sm text-gray-600">Less: Repair Expenses</span>
                          <span className="text-sm font-medium text-red-600">
                            -${repairs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      )}
                      
                      <div className="flex justify-between items-center pt-2">
                        <span className="text-base font-semibold text-gray-900">True Net Profit</span>
                        <span className={`text-xl font-bold ${netProfitValue >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          ${netProfitValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </span>
                      </div>
                    </div>
                    
                    {/* Repair Expenses Details - Collapsible */}
                    <div className="mt-6">
                      <button
                        onClick={() => setRepairExpensesExpanded(!repairExpensesExpanded)}
                        className="w-full flex items-center justify-between text-left focus:outline-none focus:ring-2 focus:ring-blue-500 rounded mb-3"
                      >
                        <h4 className="text-md font-semibold text-gray-800">
                          Repair Expenses {expenseAnalysisView === 'weekly' ? 'This Week' : expenseAnalysisView === 'monthly' ? 'This Month' : 'This Year'}
                        </h4>
                        <svg
                          className={`w-5 h-5 text-gray-600 transition-transform ${repairExpensesExpanded ? 'transform rotate-180' : ''}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                      
                      {repairExpensesExpanded && (
                        <>
                          {repairsForPeriod.length > 0 ? (
                            <div className="space-y-3">
                              {repairsForPeriod.map((repair: RepairByMonth) => {
                                const isPM = repair.category === 'maintenance'
                                return (
                                  <div 
                                    key={repair.repair_id || `${repair.truck_id}-${repair.cost}-${repair.repair_date}`}
                                    className={`p-4 rounded-lg border ${
                                      isPM ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 border-gray-200'
                                    }`}
                                  >
                                    <div className="flex justify-between items-start">
                                      <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                          <span className="text-sm font-semibold text-gray-900">
                                            {repair.truck_name || `Truck ${repair.truck_id}`}
                                          </span>
                                          {isPM && (
                                            <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded">
                                              🔧 Preventive Maintenance
                                            </span>
                                          )}
                                          {repair.category && repair.category !== 'maintenance' && (
                                            <span className="px-2 py-0.5 text-xs font-medium bg-gray-200 text-gray-700 rounded capitalize">
                                              {repair.category}
                                            </span>
                                          )}
                                        </div>
                                        <p className="text-sm text-gray-600 mb-1">
                                          {repair.description || 'No description'}
                                        </p>
                                        {repair.repair_date && (
                                          <p className="text-xs text-gray-500">
                                            {new Date(repair.repair_date).toLocaleDateString()}
                                          </p>
                                        )}
                                      </div>
                                      <div className="ml-4 text-right">
                                        <span className="text-lg font-bold text-red-600">
                                          ${repair.cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                )
                              })}
                              <div className="mt-4 pt-3 border-t border-gray-300">
                                <div className="flex justify-between items-center">
                                  <span className="text-sm font-semibold text-gray-700">Total Repair Expenses</span>
                                  <span className="text-base font-bold text-red-600">
                                    ${repairs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </span>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg text-center">
                              <p className="text-sm text-gray-600">
                                No repair expenses {expenseAnalysisView === 'weekly' ? 'this week' : expenseAnalysisView === 'monthly' ? 'this month' : 'this year'}
                              </p>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )
              })()}

              {/* Trucks Involved - Only show for trucks */}
              {vehicleTypeFilter === 'trucks' && (selectedPeriodData as any).trucks && Array.isArray((selectedPeriodData as any).trucks) && (selectedPeriodData as any).trucks.length > 0 && (
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
              {expenseAnalysisView === 'monthly' && (selectedPeriodData as any).settlements && Array.isArray((selectedPeriodData as any).settlements) && (selectedPeriodData as any).settlements.length > 0 && (
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

              {/* Expense Breakdown Chart - Only show for trucks */}
              {vehicleTypeFilter === 'trucks' && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Expenses by Category - 🚚 Trucks - {expenseAnalysisView === 'all_time' ? 'All Time' : expenseAnalysisView === 'weekly' ? (selectedPeriodData as any).week_label : expenseAnalysisView === 'monthly' ? (selectedPeriodData as any).month_label : (selectedPeriodData as any).year_label}
                </h3>
                {(() => {
                  // For trucks, show all categories (trailers are not shown in this view)
                  const standardCategories = [
                        { key: 'fuel', label: 'Fuel', value: (selectedPeriodData as any).fuel || 0 },
                        { key: 'dispatch_fee', label: 'Dispatch Fee', value: (selectedPeriodData as any).dispatch_fee || 0 },
                        { key: 'insurance', label: 'Insurance', value: (selectedPeriodData as any).insurance || 0 },
                        { key: 'safety', label: 'Safety', value: (selectedPeriodData as any).safety || 0 },
                        { key: 'prepass', label: 'Prepass', value: (selectedPeriodData as any).prepass || 0 },
                        { key: 'ifta', label: 'IFTA', value: (selectedPeriodData as any).ifta || 0 },
                        { key: 'loan_interest', label: 'Loan Interest', value: (selectedPeriodData as any).loan_interest || 0 },
                        { key: 'truck_parking', label: 'Truck Parking', value: (selectedPeriodData as any).truck_parking || 0 },
                        { key: 'custom', label: 'Custom', value: (selectedPeriodData as any).custom || 0 },
                        { key: 'driver_pay', label: "Driver's Pay", value: (selectedPeriodData as any).driver_pay || 0 },
                        { key: 'payroll_fee', label: 'Payroll Fee', value: (selectedPeriodData as any).payroll_fee || 0 },
                        ...((expenseAnalysisView === 'all_time' || expenseAnalysisView === 'yearly' || expenseAnalysisView === 'monthly') && (selectedPeriodData as any).repairs ? [{ key: 'repairs', label: 'Repairs', value: (selectedPeriodData as any).repairs || 0 }] : []),
                      ]
                  
                  // Keep "Custom" label simple - descriptions are shown in settlement details, not in chart
                  const updatedStandardCategories = standardCategories
                  
                  // Combine standard categories, filter out zero values, and sort
                  const expenseCategories = updatedStandardCategories
                    .filter(cat => cat.value > 0)
                    .sort((a, b) => b.value - a.value)

                  const sortedLabels = expenseCategories.map(cat => cat.label)
                  const sortedValues = expenseCategories.map(cat => cat.value)
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
                  style={{ height: isMobile ? '350px' : '500px', width: '100%' }}
                  opts={{ renderer: 'svg' }}
                />
                  )
                })()}
              </div>
              )}

              {/* Expense Details Table - Only show relevant categories based on vehicle type */}
              {vehicleTypeFilter === 'trucks' && (
              <div className="mt-6">
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <button
                    onClick={() => setExpenseDetailsExpanded(!expenseDetailsExpanded)}
                    className="w-full flex items-center justify-between text-left focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
                  >
                    <h3 className="text-lg font-semibold text-gray-900">
                      Expense Details - {expenseAnalysisView === 'all_time' ? 'All Time' : expenseAnalysisView === 'weekly' ? (selectedPeriodData as any).week_label : expenseAnalysisView === 'monthly' ? (selectedPeriodData as any).month_label : (selectedPeriodData as any).year_label}
                    </h3>
                    <svg
                      className={`w-5 h-5 text-gray-600 transition-transform ${expenseDetailsExpanded ? 'transform rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {expenseDetailsExpanded && (
                    <>
                      <p className="text-sm text-gray-600 mb-4 mt-4">
                        {expenseAnalysisView === 'all_time'
                          ? 'All amounts shown are cumulative totals from all settlements across all time periods.'
                          : (
                            <>
                              All amounts shown are for <strong>{expenseAnalysisView === 'weekly' ? 'this week' : expenseAnalysisView === 'monthly' ? 'this month' : 'this year'}</strong> only, aggregated from all settlements in the selected period.
                            </>
                          )}
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
                        { key: 'driver_pay', label: "Driver's Pay" },
                        { key: 'payroll_fee', label: 'Payroll Fee' },
                        { key: 'loan_interest', label: 'Loan Interest' },
                        { key: 'truck_parking', label: 'Truck Parking' },
                        { key: 'custom', label: 'Custom' },
                        ...((expenseAnalysisView === 'all_time' || expenseAnalysisView === 'yearly' || expenseAnalysisView === 'monthly') && (selectedPeriodData as any).repairs ? [{ key: 'repairs', label: 'Repairs' }] : []),
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
                        
                        // Get custom expense descriptions for the "custom" category
                        const customDescriptions = key === 'custom' && (selectedPeriodData as any).custom_descriptions 
                          ? Object.values((selectedPeriodData as any).custom_descriptions).filter((d: any) => d && d.trim()).join('; ')
                          : null
                        
                        return (
                          <tr key={key} className={amount > 0 ? '' : 'opacity-50'}>
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">
                              <div>
                                <div>{label}</div>
                                {customDescriptions && (
                                  <div className="text-xs text-gray-500 font-normal mt-1 italic">
                                    {customDescriptions}
                                  </div>
                                )}
                              </div>
                            </td>
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
                    </>
                  )}
                </div>
              </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              Please select a period from the dropdown above.
            </div>
          )}
        </div>
      )}

      {/* Expenses by Category Pie Chart - Only show for trucks */}
      {vehicleTypeFilter === 'trucks' && (
      <div className="grid grid-cols-1 gap-6 mb-6">
        {expenseCategoriesData.length > 0 && (
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Expenses by Category</h2>
              <button
                onClick={allCategoriesSelected ? handleDeselectAllCategories : handleSelectAllCategories}
                className={`px-3 py-1 text-xs font-medium rounded ${
                  allCategoriesSelected
                    ? 'bg-gray-600 text-white hover:bg-gray-700'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {allCategoriesSelected ? 'Deselect All' : 'Select All'}
              </button>
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
                legend: isMobile ? { show: false } : {
                  orient: 'vertical',
                  right: 10,
                  top: 'center',
                  itemGap: 12,
                  itemWidth: 14,
                  itemHeight: 14,
                  align: 'left',
                  textStyle: {
                    fontSize: 12,
                    color: '#374151',
                    lineHeight: 16
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
                    radius: isMobile ? ['35%', '65%'] : ['40%', '70%'],
                    center: isMobile ? ['50%', '45%'] : ['35%', '50%'],
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
                    data: expenseCategoriesData
                      .filter(item => selectedCategories[item.name] !== false)
                      .map(item => ({
                        value: item.value,
                        name: item.name,
                        itemStyle: {
                          color: item.color
                        }
                      }))
                  }
                ]
              }}
              style={{ height: isMobile ? '300px' : '450px', width: '100%' }}
              opts={{ renderer: 'svg' }}
              onEvents={windowWidth >= 768 ? {
                legendselectchanged: handleLegendSelectChange
              } : {}}
            />
            {/* Custom Legend for Mobile */}
            {isMobile && (
              <div className="mt-1 grid grid-cols-2 sm:grid-cols-3 gap-3">
                {expenseCategoriesData.map((item) => {
                  const total = expenseCategoriesData.reduce((sum, d) => sum + d.value, 0)
                  const percent = ((item.value / total) * 100).toFixed(1)
                  const isSelected = selectedCategories[item.name] !== false
                  return (
                    <div
                      key={item.name}
                      onClick={() => {
                        const newSelected = { ...selectedCategories }
                        newSelected[item.name] = !isSelected
                        setSelectedCategories(newSelected)
                        // Trigger chart update
                        handleLegendSelectChange({ selected: newSelected })
                      }}
                      className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
                        isSelected ? 'bg-gray-50 hover:bg-gray-100' : 'bg-gray-100 opacity-50 hover:bg-gray-200'
                      }`}
                    >
                      <div
                        className="w-4 h-4 rounded flex-shrink-0"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="text-xs text-gray-700 flex-1">
                        {item.name} ({percent}%)
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
      )}

      {/* Repair Costs by Month - Only show for trucks */}
      {vehicleTypeFilter === 'trucks' && repairsByMonth.length > 0 && (() => {
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
              style={{ height: isMobile ? '300px' : '450px', width: '100%' }}
              opts={{ renderer: 'svg' }}
            />
          </div>
        )
      })()}

      {/* Blocks Delivered by Truck - Only show for trucks */}
      {vehicleTypeFilter === 'trucks' && blocksChartData && blocksChartData.series && blocksChartData.series.length > 0 && (
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
                    const blockCount = param.value || 0
                    result += `${param.seriesName}: ${blockCount} blocks<br/>`
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
                ...blocksChartData.series.map((series) => {
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
            style={{ height: isMobile ? '300px' : '450px', width: '100%' }}
            opts={{ renderer: 'svg' }}
            onEvents={{
              click: (params: any) => {
                // Handle click on chart bars
                if (params.seriesType === 'bar' && params.seriesName !== 'Average') {
                  const monthLabel = params.name
                  const truckName = params.seriesName
                  
                  // Find the block data for this truck and month
                  const blockData = blocksByTruckMonth.find(
                    (d: BlockByTruckMonth) => d.month === monthLabel && d.truck_name === truckName
                  )
                  
                  if (blockData) {
                    setSelectedBlockData(blockData)
                  }
                }
              }
            }}
          />
          
          {/* Clicked Block Details Modal */}
          {selectedBlockData && (
            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    Block Details: {selectedBlockData.truck_name} - {selectedBlockData.month}
                  </h3>
                  <div className="text-sm text-gray-700 mb-3">
                    <span className="font-medium">Total Blocks: {selectedBlockData.blocks}</span>
                  </div>
                  {selectedBlockData.block_ids && selectedBlockData.block_ids.length > 0 ? (
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-2">Block IDs:</p>
                      <div className="flex flex-col gap-2">
                        {selectedBlockData.block_ids.map((blockItem: string | BlockWithDate, idx: number) => {
                          const blockId = typeof blockItem === 'string' ? blockItem : blockItem.block_id
                          const deliveryDate = typeof blockItem === 'object' ? blockItem.delivery_date : undefined
                          
                          return (
                            <div key={idx} className="flex items-center gap-2">
                              <span className="inline-flex items-center px-3 py-1 rounded-md text-sm font-medium bg-blue-100 text-blue-800 border border-blue-200">
                                {blockId}
                              </span>
                              {deliveryDate && (
                                <span className="text-xs text-gray-500">
                                  {new Date(deliveryDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                                </span>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 italic">No block IDs available</p>
                  )}
                </div>
                <button
                  onClick={() => setSelectedBlockData(null)}
                  className="ml-4 text-gray-400 hover:text-gray-600 transition-colors"
                  aria-label="Close"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          )}
          
          {/* Blocks Detail Table - Collapsible */}
          {blocksByTruckMonth.length > 0 && (
            <div className="mt-6 border-t pt-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">All Block Details by Month</h3>
                <button
                  onClick={() => setShowBlockDetails(!showBlockDetails)}
                  className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors flex items-center gap-2"
                >
                  {showBlockDetails ? 'Hide' : 'Show'} Details
                  <svg 
                    className={`w-4 h-4 transition-transform ${showBlockDetails ? 'rotate-180' : ''}`}
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </div>
              {showBlockDetails && (
              <>
                {/* Mobile Card View */}
                <div className="md:hidden space-y-4">
                  {blocksByTruckMonth
                    .filter((item: BlockByTruckMonth) => !selectedTruck || item.truck_id === selectedTruck)
                    .sort((a: BlockByTruckMonth, b: BlockByTruckMonth) => {
                      // Sort by month_key descending, then by truck_name
                      if (a.month_key !== b.month_key) {
                        return b.month_key.localeCompare(a.month_key)
                      }
                      return (a.truck_name || '').localeCompare(b.truck_name || '')
                    })
                    .map((item: BlockByTruckMonth, index: number) => (
                      <div key={index} className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                        <div className="flex items-center justify-between mb-3 pb-3 border-b border-gray-200">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {item.truck_name || `Truck ${item.truck_id}`}
                            </div>
                            <div className="text-xs text-gray-500 mt-1">{item.month}</div>
                          </div>
                          <div className="text-lg font-semibold text-gray-900">
                            {item.blocks} <span className="text-sm font-normal text-gray-600">blocks</span>
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Block IDs</div>
                          {item.block_ids && item.block_ids.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                              {item.block_ids.map((blockItem: string | BlockWithDate, idx: number) => {
                                const blockId = typeof blockItem === 'string' ? blockItem : blockItem.block_id
                                const deliveryDate = typeof blockItem === 'object' ? blockItem.delivery_date : undefined
                                
                                return (
                                  <div key={idx} className="flex flex-col gap-1">
                                    <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800">
                                      {blockId}
                                    </span>
                                    {deliveryDate && (
                                      <span className="text-xs text-gray-500 text-center">
                                        {new Date(deliveryDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                                      </span>
                                    )}
                                  </div>
                                )
                              })}
                            </div>
                          ) : (
                            <span className="text-gray-400 italic text-sm">No block IDs available</span>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Truck</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Month</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Blocks</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Block IDs</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {blocksByTruckMonth
                        .filter((item: BlockByTruckMonth) => !selectedTruck || item.truck_id === selectedTruck)
                        .sort((a: BlockByTruckMonth, b: BlockByTruckMonth) => {
                          // Sort by month_key descending, then by truck_name
                          if (a.month_key !== b.month_key) {
                            return b.month_key.localeCompare(a.month_key)
                          }
                          return (a.truck_name || '').localeCompare(b.truck_name || '')
                        })
                        .map((item: BlockByTruckMonth, index: number) => (
                          <tr key={index} className="hover:bg-gray-50">
                            <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                              {item.truck_name || `Truck ${item.truck_id}`}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                              {item.month}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 font-semibold">
                              {item.blocks}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {item.block_ids && item.block_ids.length > 0 ? (
                                <div className="flex flex-row flex-wrap gap-2 items-center">
                                  {item.block_ids.map((blockItem: string | BlockWithDate, idx: number) => {
                                    const blockId = typeof blockItem === 'string' ? blockItem : blockItem.block_id
                                    const deliveryDate = typeof blockItem === 'object' ? blockItem.delivery_date : undefined
                                    
                                    return (
                                      <div key={idx} className="flex items-center gap-1">
                                        <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800 whitespace-nowrap">
                                          {blockId}
                                        </span>
                                        {deliveryDate && (
                                          <span className="text-xs text-gray-500 whitespace-nowrap">
                                            ({new Date(deliveryDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })})
                                          </span>
                                        )}
                                      </div>
                                    )
                                  })}
                                </div>
                              ) : (
                                <span className="text-gray-400 italic">No block IDs available</span>
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </>
              )}
            </div>
          )}
        </div>
      )}

      {/* Net Profit vs Repair Costs Chart - Enhanced - Only show for trucks */}
      {vehicleTypeFilter === 'trucks' && truckProfitsData.length > 0 && (
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <div className="mb-6 flex justify-between items-start">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">Profit Analysis by Truck</h2>
              <p className="text-sm text-gray-600">Showing profit before repairs, repair costs, and final net profit after repairs. Percentage indicates repair cost as % of profit before repairs.</p>
            </div>
            <button
              onClick={() => setShowProfitDetails(!showProfitDetails)}
              className="ml-4 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors flex items-center gap-2"
            >
              {showProfitDetails ? (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                  </svg>
                  Hide Details
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                  Show Details
                </>
              )}
            </button>
          </div>
          <ReactECharts
            option={{
              tooltip: {
                trigger: 'axis',
                axisPointer: {
                  type: 'shadow'
                },
                formatter: (params: any) => {
                  const truck = truckProfitsData.find((t: { truck_id: number; truck_name: string; license_plate?: string; vin?: string; total_revenue: number; total_expenses: number; settlement_expenses: number; repair_costs: number; profit_before_repairs: number; net_profit: number }) => t.truck_name === params[0]?.axisValue)
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
                data: truckProfitsData.map((t: { truck_id: number; truck_name: string; license_plate?: string; vin?: string; total_revenue: number; total_expenses: number; settlement_expenses: number; repair_costs: number; profit_before_repairs: number; net_profit: number }) => t.truck_name),
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
                  data: truckProfitsData.map((t: { truck_id: number; truck_name: string; license_plate?: string; vin?: string; total_revenue: number; total_expenses: number; settlement_expenses: number; repair_costs: number; profit_before_repairs: number; net_profit: number }) => t.profit_before_repairs || (t.total_revenue - (t.settlement_expenses || t.total_expenses - t.repair_costs))),
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
                  data: truckProfitsData.map((t: { truck_id: number; truck_name: string; license_plate?: string; vin?: string; total_revenue: number; total_expenses: number; settlement_expenses: number; repair_costs: number; profit_before_repairs: number; net_profit: number }) => ({
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
                  data: truckProfitsData.map((t: { truck_id: number; truck_name: string; license_plate?: string; vin?: string; total_revenue: number; total_expenses: number; settlement_expenses: number; repair_costs: number; profit_before_repairs: number; net_profit: number }) => t.net_profit),
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
            style={{ height: isMobile ? '350px' : '500px', width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
          
          {/* Summary Stats - Collapsible */}
          {showProfitDetails && (
            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4 pt-6 border-t border-gray-200">
            {truckProfitsData.map((truck: { truck_id: number; truck_name: string; license_plate?: string; vin?: string; total_revenue: number; total_expenses: number; settlement_expenses: number; repair_costs: number; profit_before_repairs: number; net_profit: number }) => {
              const profitBeforeRepairs = truck.profit_before_repairs || (truck.total_revenue - (truck.settlement_expenses || truck.total_expenses - truck.repair_costs))
              const repairRatio = profitBeforeRepairs > 0 && truck.repair_costs > 0 
                ? ((truck.repair_costs / profitBeforeRepairs) * 100).toFixed(1)
                : truck.repair_costs > 0 ? 'N/A' : '0'
              
              return (
                <div key={truck.truck_id} className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-1">{truck.truck_name}</h3>
                  {(truck.license_plate || truck.vin) && (
                    <div className="text-xs text-gray-500 mb-2">
                      {truck.license_plate && <span>Plate: {truck.license_plate}</span>}
                      {truck.license_plate && truck.vin && <span className="mx-2">•</span>}
                      {truck.vin && <span>VIN: {truck.vin}</span>}
                    </div>
                  )}
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
          )}
        </div>
      )}

      {/* Time-Series Charts Section - Only show for trucks */}
      {vehicleTypeFilter === 'trucks' && timeSeriesData && (
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
                    style={{ height: isMobile ? '300px' : '400px', width: '100%' }}
                    opts={{ renderer: 'svg' }}
                  />
                )}
              </div>
            )}

            {/* Driver Pay Chart - Only show for trucks */}
            {vehicleTypeFilter === 'trucks' && currentData.labels.length > 0 && (
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
                    style={{ height: isMobile ? '300px' : '400px', width: '100%' }}
                    opts={{ renderer: 'svg' }}
                  />
                )}
              </div>
            )}
          </div>

          {/* Expenses Chart - Full Width - Filter categories based on vehicle type */}
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
                          // For trucks, show all categories
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
                  style={{ height: isMobile ? '300px' : '450px', width: '100%' }}
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
