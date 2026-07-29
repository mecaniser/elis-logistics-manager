import { useEffect, useRef, useState } from 'react'
import { analyticsApi, reserveApi, trucksApi, Truck, TimeSeriesData, TimeSeriesPeriod, ReserveBalance } from '../services/api'
import ReactECharts from 'echarts-for-react'
import { useMobile } from '../utils/useMobile'
import { useTenant } from '../contexts/TenantContext'
import AccountingTooltip from '../components/AccountingTooltip'

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
  tolls: number[]
  dispatch_fee: number[]
  deduct: number[]
  fleet_manager_support: number[]
  insurance: number[]
  safety: number[]
  prepass: number[]
  ifta: number[]
  loan_interest: number[]
  truck_parking: number[]
  custom: number[]
}

interface MetricTrendPoint {
  label: string
  value: number
  isCurrent: boolean
  isPrevious: boolean
}

// Helper function to safely format numbers (handles null/undefined)
const safeToLocaleString = (value: number | null | undefined, options?: Intl.NumberFormatOptions): string => {
  if (value == null || isNaN(value)) return '0.00'
  return value.toLocaleString(undefined, options || { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatCurrencyMetric = (value: number | null | undefined): string => {
  if (value == null || isNaN(value)) return '—'
  return `$${safeToLocaleString(value)}`
}

const formatMetricDelta = (value: number): string => {
  return `$${safeToLocaleString(Math.abs(value))}`
}

const formatMilesMetricDelta = (value: number): string => {
  return `${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })} mi`
}

const formatMilesMetricValue = (value: number): string => {
  return `${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })} mi`
}

const formatDieselMetricValue = (value: number): string => {
  return `$${safeToLocaleString(value, { minimumFractionDigits: 3, maximumFractionDigits: 3 })}/gal`
}

const formatDieselMetricDelta = (value: number): string => {
  return `$${safeToLocaleString(Math.abs(value), { minimumFractionDigits: 3, maximumFractionDigits: 3 })}/gal`
}

function MetricLabelWithTooltip({ label, description }: { label: string; description: string }) {
  return (
    <div className="flex items-center gap-1">
      <span>{label}</span>
      <div className="hidden md:inline-flex">
        <AccountingTooltip term={label} description={description}>
          <span className="sr-only">{label} description</span>
        </AccountingTooltip>
      </div>
    </div>
  )
}

function MetricSparkline({
  points,
  strokeColor,
  fillColor,
  valueFormatter,
}: {
  points: MetricTrendPoint[]
  strokeColor: string
  fillColor: string
  valueFormatter: (value: number) => string
}) {
  const [hoveredPointIndex, setHoveredPointIndex] = useState<number | null>(null)

  if (points.length < 2) {
    return <div className="mt-2 text-[10px] sm:text-xs text-gray-400">Not enough history for a trend line</div>
  }

  const width = 160
  const height = 40
  const padding = 4
  const values = points.map((point) => point.value)
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const valueRange = maxValue - minValue
  const stepX = points.length === 1 ? 0 : (width - padding * 2) / (points.length - 1)

  const toY = (value: number) => {
    if (valueRange < 0.0001) return height / 2
    return padding + ((maxValue - value) / valueRange) * (height - padding * 2)
  }

  const polylinePoints = points
    .map((point, index) => `${padding + index * stepX},${toY(point.value)}`)
    .join(' ')

  const areaPoints = [
    `${padding},${height - padding}`,
    ...points.map((point, index) => `${padding + index * stepX},${toY(point.value)}`),
    `${padding + (points.length - 1) * stepX},${height - padding}`,
  ].join(' ')
  const hoveredPoint = hoveredPointIndex != null ? points[hoveredPointIndex] : null

  return (
    <div className="mt-3">
      <div className="min-h-[1rem] text-[10px] sm:text-xs text-gray-500">
        {hoveredPoint ? `${hoveredPoint.label}: ${valueFormatter(hoveredPoint.value)}` : '\u00A0'}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-10 w-full overflow-visible">
        <polygon points={areaPoints} fill={fillColor} />
        <polyline
          points={polylinePoints}
          fill="none"
          stroke={strokeColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {points.map((point, index) => {
          const cx = padding + index * stepX
          const cy = toY(point.value)
          const radius = point.isCurrent ? 3.5 : point.isPrevious ? 3 : 2.5
          return (
            <g key={`${point.label}-${index}`}>
              <circle
                cx={cx}
                cy={cy}
                r={Math.max(radius + 6, 8)}
                fill="transparent"
                onMouseEnter={() => setHoveredPointIndex(index)}
                onMouseLeave={() => setHoveredPointIndex((current) => (current === index ? null : current))}
              />
              <circle
                cx={cx}
                cy={cy}
                r={radius}
                fill={point.isCurrent ? strokeColor : '#ffffff'}
                stroke={strokeColor}
                strokeWidth={point.isCurrent ? 2 : 1.5}
              />
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export default function Dashboard() {
  const isMobile = useMobile()
  const { currentTenant } = useTenant()
  const [data, setData] = useState<any>(null)
  const [businessSummary, setBusinessSummary] = useState<any>(null)
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [selectedTruck, setSelectedTruck] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesData | null>(null)
  const [businessTimeSeries, setBusinessTimeSeries] = useState<{ truck: TimeSeriesData | null; trailer: TimeSeriesData | null }>({
    truck: null,
    trailer: null,
  })
  const [timeSeriesLoading, setTimeSeriesLoading] = useState(false)
  const [dieselBenchmarkLoading, setDieselBenchmarkLoading] = useState(false)
  const [timeSeriesReady, setTimeSeriesReady] = useState(false)
  const [reserveBalances, setReserveBalances] = useState<ReserveBalance[]>([])
  const [selectedTrailerContributionTotal, setSelectedTrailerContributionTotal] = useState(0)
  const [activeTimeView, setActiveTimeView] = useState<'weekly' | 'monthly'>('monthly')
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
  const [cumulativePositionExpanded, setCumulativePositionExpanded] = useState<boolean>(false)
  const [windowWidth, setWindowWidth] = useState<number>(typeof window !== 'undefined' ? window.innerWidth : 1024)
  const timeSeriesRequestRef = useRef(0)

  useEffect(() => {
    // Reset vehicle-scoped dashboard state when the tenant changes.
    setSelectedTruck(null)
    setTrucks([])
    setData(null)
    setReserveBalances([])
    setSelectedTrailerContributionTotal(0)
    setBusinessTimeSeries({ truck: null, trailer: null })
    setTimeSeriesData(null)
    setTimeSeriesReady(false)
    setTimeSeriesLoading(false)
    setDieselBenchmarkLoading(false)

    if (currentTenant?.business_type !== 'logistics') {
      setBusinessSummary(null)
      setLoading(false)
    }
  }, [currentTenant?.id, currentTenant?.business_type])

  useEffect(() => {
    if (currentTenant?.business_type === 'logistics') {
      loadTrucks()
      loadDashboard()
      loadReserveBalances()
    }
  }, [selectedTruck, vehicleTypeFilter, currentTenant?.id, currentTenant?.business_type])

  useEffect(() => {
    if (currentTenant?.business_type === 'logistics') {
      loadBusinessSummary()
    } else {
      setBusinessSummary(null)
    }
  }, [currentTenant?.id, currentTenant?.business_type])

  useEffect(() => {
    if (currentTenant?.business_type === 'logistics') {
      loadBusinessTimeSeries()
    } else {
      setBusinessTimeSeries({ truck: null, trailer: null })
    }
  }, [currentTenant?.id, currentTenant?.business_type])

  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    // Only run for logistics businesses
    if (currentTenant?.business_type !== 'logistics') return
    
    // Reset selected period when vehicle type filter changes, so it gets re-initialized with new data
    setSelectedExpensePeriod('')
    // Set default view based on vehicle type: weekly for trucks, monthly for trailers
    if (vehicleTypeFilter === 'trucks' && expenseAnalysisView === 'monthly') {
      setExpenseAnalysisView('weekly')
    } else if (vehicleTypeFilter === 'trailers' && expenseAnalysisView === 'weekly') {
      setExpenseAnalysisView('monthly')
    }
    loadTimeSeries()
  }, [selectedTruck, vehicleTypeFilter, currentTenant?.business_type])

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
        { name: 'Tolls', value: expenseCategories.tolls || 0 },
        { name: 'Repairs', value: expenseCategories.repairs || 0 },
        { name: 'Dispatch Fee', value: expenseCategories.dispatch_fee || 0 },
        { name: 'Deductions', value: expenseCategories.deduct || 0 },
        { name: 'Insurance', value: expenseCategories.insurance || 0 },
        { name: 'Safety', value: expenseCategories.safety || 0 },
        { name: 'Prepass', value: expenseCategories.prepass || 0 },
        { name: 'IFTA', value: expenseCategories.ifta || 0 },
        { name: "Driver's Pay", value: expenseCategories.driver_pay || 0 },
        { name: 'Payroll Fee', value: expenseCategories.payroll_fee || 0 },
        { name: 'Loan Interest', value: expenseCategories.loan_interest || 0 },
        { name: 'Truck Parking', value: expenseCategories.truck_parking || 0 },
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
    setCumulativePositionExpanded(false)
  }, [expenseAnalysisView, timeSeriesData, selectedExpensePeriod, vehicleTypeFilter])

  useEffect(() => {
    if (currentTenant?.business_type !== 'logistics') {
      setSelectedTrailerContributionTotal(0)
      return
    }

    const selectedVehicle = selectedTruck ? trucks.find((truck) => truck.id === selectedTruck) : null

    if (!selectedTruck) {
      setSelectedTrailerContributionTotal(Number(businessSummary?.trailers?.net_profit) || 0)
      return
    }

    const trailerId =
      selectedVehicle?.vehicle_type === 'trailer'
        ? selectedVehicle.id
        : selectedVehicle?.default_trailer_id || null

    if (!trailerId) {
      setSelectedTrailerContributionTotal(0)
      return
    }

    let cancelled = false

    const loadTrailerContribution = async () => {
      try {
        const response = await analyticsApi.getVehicleROI(trailerId)
        if (!cancelled) {
          setSelectedTrailerContributionTotal(Number(response.data.cumulative_net_profit) || 0)
        }
      } catch (err) {
        console.error('Failed to load trailer contribution total:', err)
        if (!cancelled) {
          setSelectedTrailerContributionTotal(0)
        }
      }
    }

    loadTrailerContribution()

    return () => {
      cancelled = true
    }
  }, [selectedTruck, trucks, businessSummary, currentTenant?.business_type])

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

  const loadBusinessSummary = async () => {
    try {
      const response = await analyticsApi.getDashboard()
      setBusinessSummary(response.data)
    } catch (err) {
      console.error('Failed to load business summary:', err)
      setBusinessSummary(null)
    }
  }

  const loadReserveBalances = async () => {
    try {
      const response = await reserveApi.getAllBalances()
      setReserveBalances(Array.isArray(response.data) ? response.data : [])
    } catch (err) {
      console.error('Failed to load reserve balances:', err)
      setReserveBalances([])
    }
  }

  const loadTimeSeries = async () => {
    const requestId = ++timeSeriesRequestRef.current
    try {
      setTimeSeriesLoading(true)
      setTimeSeriesReady(false)
      // Map vehicle type filter to backend parameter
      const vehicleType = vehicleTypeFilter === 'trucks' ? 'truck' : vehicleTypeFilter === 'trailers' ? 'trailer' : undefined
      const dieselRequest =
        vehicleTypeFilter === 'trucks'
          ? analyticsApi.getTimeSeries(undefined, selectedTruck || undefined, vehicleType, true)
          : null

      if (dieselRequest) {
        setDieselBenchmarkLoading(true)
      } else {
        setDieselBenchmarkLoading(false)
      }

      const response = await analyticsApi.getTimeSeries(undefined, selectedTruck || undefined, vehicleType, false)
      if (requestId !== timeSeriesRequestRef.current) return

      const normalizedData = normalizeTimeSeries(response.data || {})
      setTimeSeriesData(normalizedData)
      setTimeSeriesReady(true)

      if (dieselRequest) {
        dieselRequest
          .then((dieselResponse) => {
            if (requestId !== timeSeriesRequestRef.current) return
            const normalizedDieselData = normalizeTimeSeries(dieselResponse.data || {})
            setTimeSeriesData((currentData) => mergeDieselBenchmarks(currentData || normalizedData, normalizedDieselData))
          })
          .catch((err) => {
            console.error('Failed to load diesel benchmark time-series:', err)
          })
          .finally(() => {
            if (requestId === timeSeriesRequestRef.current) {
              setDieselBenchmarkLoading(false)
            }
          })
      }
    } catch (err) {
      console.error('Failed to load time-series data:', err)
      if (requestId !== timeSeriesRequestRef.current) return
      setTimeSeriesData({
        by_week: [],
        by_month: [],
        by_year: [],
      })
      setTimeSeriesReady(true)
    } finally {
      if (requestId === timeSeriesRequestRef.current) {
        setTimeSeriesLoading(false)
        if (vehicleTypeFilter !== 'trucks') {
          setDieselBenchmarkLoading(false)
        }
      }
    }
  }

  const normalizeTimeSeries = (rawData: any): TimeSeriesData => ({
    by_week: Array.isArray(rawData?.by_week) ? rawData.by_week : [],
    by_month: Array.isArray(rawData?.by_month) ? rawData.by_month : [],
    by_year: Array.isArray(rawData?.by_year) ? rawData.by_year : [],
  })

  const mergeDieselBenchmarks = (baseData: TimeSeriesData, dieselData: TimeSeriesData): TimeSeriesData => {
    const mergePeriods = (
      basePeriods: any[],
      dieselPeriods: any[],
      key: 'week_key' | 'month_key' | 'year_key',
    ) => {
      const dieselByKey = new Map(
        dieselPeriods.map((period) => [period[key], period.diesel_price_per_gallon ?? null])
      )

      return basePeriods.map((period) => ({
        ...period,
        diesel_price_per_gallon: dieselByKey.has(period[key]) ? dieselByKey.get(period[key]) ?? null : period.diesel_price_per_gallon ?? null,
      }))
    }

    return {
      by_week: mergePeriods(baseData.by_week, dieselData.by_week, 'week_key'),
      by_month: mergePeriods(baseData.by_month, dieselData.by_month, 'month_key'),
      by_year: mergePeriods(baseData.by_year, dieselData.by_year, 'year_key'),
    }
  }

  const loadBusinessTimeSeries = async () => {
    try {
      const [truckResponse, trailerResponse] = await Promise.all([
        analyticsApi.getTimeSeries(undefined, undefined, 'truck'),
        analyticsApi.getTimeSeries(undefined, undefined, 'trailer'),
      ])
      setBusinessTimeSeries({
        truck: normalizeTimeSeries(truckResponse.data),
        trailer: normalizeTimeSeries(trailerResponse.data),
      })
    } catch (err) {
      console.error('Failed to load business time series:', err)
      setBusinessTimeSeries({ truck: null, trailer: null })
    }
  }

  // Show placeholder dashboard for non-logistics businesses FIRST (before any data checks)
  if (currentTenant && currentTenant.business_type !== 'logistics') {
    const businessTypeLabels: Record<string, { title: string; description: string; icon: string }> = {
      'tech': {
        title: 'IT Services Dashboard',
        description: 'Track projects, clients, contracts, and revenue for your IT consulting business.',
        icon: '💻'
      },
      'real_estate': {
        title: 'Real Estate Dashboard', 
        description: 'Monitor properties, rentals, occupancy rates, and rental income.',
        icon: '🏠'
      }
    }
    
    const businessInfo = businessTypeLabels[currentTenant.business_type] || {
      title: `${currentTenant.name} Dashboard`,
      description: 'Dashboard coming soon for this business type.',
      icon: '📊'
    }

    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center max-w-lg mx-auto px-4">
          <div className="text-6xl mb-6">{businessInfo.icon}</div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-4">
            {businessInfo.title}
          </h1>
          <p className="text-gray-600 mb-8">
            {businessInfo.description}
          </p>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <h3 className="font-semibold text-blue-900 mb-2">Coming Soon</h3>
            <p className="text-blue-700 text-sm">
              We're building a specialized dashboard for <strong>{currentTenant.name}</strong>. 
              In the meantime, you can use the Accounting features to track your finances.
            </p>
          </div>
        </div>
      </div>
    )
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
    
    // For trailers, only show repairs
    if (vehicleTypeFilter === 'trailers') {
      return [
        { name: 'Repairs', value: expenseCategories.repairs || 0, color: '#ef4444' },
      ].filter(item => item.value > 0).sort((a, b) => b.value - a.value)
    }
    
    // For trucks, show all categories
    return expenseCategories && Object.keys(expenseCategories).length > 0 ? [
      { name: 'Fuel', value: expenseCategories.fuel || 0, color: '#3b82f6' },
      { name: 'Tolls', value: expenseCategories.tolls || 0, color: '#14b8a6' },
      { name: 'Repairs', value: expenseCategories.repairs || 0, color: '#ef4444' },
      { name: 'Dispatch Fee', value: expenseCategories.dispatch_fee || 0, color: '#f59e0b' },
      { name: 'Deductions', value: expenseCategories.deduct || 0, color: '#6366f1' },
      { name: 'Fleet Manager Support', value: expenseCategories.fleet_manager_support || 0, color: '#0f766e' },
      { name: 'Insurance', value: expenseCategories.insurance || 0, color: '#f97316' },
      { name: 'Safety', value: expenseCategories.safety || 0, color: '#eab308' },
      { name: 'Prepass', value: expenseCategories.prepass || 0, color: '#84cc16' },
      { name: 'IFTA', value: expenseCategories.ifta || 0, color: '#10b981' },
      { name: "Driver's Pay", value: expenseCategories.driver_pay || 0, color: '#8b5cf6' },
      { name: 'Payroll Fee', value: expenseCategories.payroll_fee || 0, color: '#ec4899' },
      { name: 'Loan Interest', value: expenseCategories.loan_interest || 0, color: '#fbbf24' },
      { name: 'Truck Parking', value: expenseCategories.truck_parking || 0, color: '#a855f7' },
    ].filter(item => item.value > 0).sort((a, b) => b.value - a.value) : []
  }
  
  const expenseCategoriesData = getExpenseCategoriesData()

  const blocksByTruckMonth: BlockByTruckMonth[] = data.blocks_by_truck_month || []
  const repairsByMonth: RepairByMonth[] = data.repairs_by_month || []

  const getRepairsForSelectedPeriod = (pd: any): RepairByMonth[] => {
    if (!pd || vehicleTypeFilter !== 'trucks') return []

    if (expenseAnalysisView === 'monthly') {
      return repairsByMonth.filter((repair: RepairByMonth) => repair.month_key === pd.month_key)
    }

    if (expenseAnalysisView === 'yearly') {
      return repairsByMonth.filter((repair: RepairByMonth) => {
        if (!repair.repair_date) return false
        const repairYear = new Date(repair.repair_date).getFullYear().toString()
        return repairYear === pd.year_key
      })
    }

    if (expenseAnalysisView === 'weekly') {
      const weekStart = pd.week_start ? new Date(pd.week_start) : new Date(new Date(pd.week_key).getTime() - 7 * 24 * 60 * 60 * 1000)
      const weekEnd = pd.week_end ? new Date(pd.week_end) : new Date(pd.week_key)

      return repairsByMonth.filter((repair: RepairByMonth) => {
        if (!repair.repair_date) return false
        const repairDate = new Date(repair.repair_date)
        return repairDate >= weekStart && repairDate <= weekEnd
      })
    }

    return []
  }

  const getRepairCostForSelectedPeriod = (pd: any): number => {
    if (!pd) return 0

    if (vehicleTypeFilter === 'trucks') {
      if (expenseAnalysisView === 'weekly' || expenseAnalysisView === 'monthly' || expenseAnalysisView === 'yearly') {
        return getRepairsForSelectedPeriod(pd).reduce((sum, repair) => sum + (Number(repair.cost) || 0), 0)
      }
      if (expenseAnalysisView === 'all_time') {
        return Number(pd.repairs) || 0
      }
    }

    return (expenseAnalysisView === 'yearly' || expenseAnalysisView === 'monthly' || expenseAnalysisView === 'all_time')
      ? (Number(pd.repairs) || 0)
      : 0
  }

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
      return { labels: [], grossRevenue: [], netProfit: [], driverPay: [], payrollFee: [], expenses: { fuel: [], tolls: [], dispatch_fee: [], deduct: [], fleet_manager_support: [], insurance: [], safety: [], prepass: [], ifta: [], loan_interest: [], truck_parking: [], custom: [] } }
    }
    
    const labels = data.by_week.map((item) => item.week_label)
    const grossRevenue = data.by_week.map((item) => item.gross_revenue)
    const netProfit = data.by_week.map((item) => item.net_profit)
    const driverPay = data.by_week.map((item) => item.driver_pay)
    const payrollFee = data.by_week.map((item) => item.payroll_fee)
    
    const expenses: ExpenseData = {
      fuel: data.by_week.map((item) => item.fuel),
      tolls: data.by_week.map((item) => (item as any).tolls || 0),
      dispatch_fee: data.by_week.map((item) => item.dispatch_fee),
      deduct: data.by_week.map((item) => item.deduct || 0),
      fleet_manager_support: data.by_week.map((item) => item.fleet_manager_support || 0),
      insurance: data.by_week.map((item) => item.insurance),
      safety: data.by_week.map((item) => item.safety),
      prepass: data.by_week.map((item) => item.prepass),
      ifta: data.by_week.map((item) => item.ifta),
      loan_interest: data.by_week.map((item) => item.loan_interest || 0),
      truck_parking: data.by_week.map((item) => item.truck_parking),
      custom: data.by_week.map(() => 0),
    }
    
    return { labels, grossRevenue, netProfit, driverPay, payrollFee, expenses }
  }

  const processMonthlyData = (data: TimeSeriesData | null): { labels: string[], grossRevenue: number[], netProfit: number[], driverPay: number[], payrollFee: number[], expenses: ExpenseData } => {
    if (!data || !Array.isArray(data.by_month) || data.by_month.length === 0) {
      return { labels: [], grossRevenue: [], netProfit: [], driverPay: [], payrollFee: [], expenses: { fuel: [], tolls: [], dispatch_fee: [], deduct: [], fleet_manager_support: [], insurance: [], safety: [], prepass: [], ifta: [], loan_interest: [], truck_parking: [], custom: [] } }
    }
    
    const labels = data.by_month.map((item) => item.month_label)
    const grossRevenue = data.by_month.map((item) => item.gross_revenue)
    const netProfit = data.by_month.map((item) => item.net_profit)
    const driverPay = data.by_month.map((item) => item.driver_pay)
    const payrollFee = data.by_month.map((item) => item.payroll_fee)
    
    const expenses: ExpenseData = {
      fuel: data.by_month.map((item) => item.fuel),
      tolls: data.by_month.map((item) => (item as any).tolls || 0),
      dispatch_fee: data.by_month.map((item) => item.dispatch_fee),
      deduct: data.by_month.map((item) => item.deduct || 0),
      fleet_manager_support: data.by_month.map((item) => item.fleet_manager_support || 0),
      insurance: data.by_month.map((item) => item.insurance),
      safety: data.by_month.map((item) => item.safety),
      prepass: data.by_month.map((item) => item.prepass),
      ifta: data.by_month.map((item) => item.ifta),
      loan_interest: data.by_month.map((item) => item.loan_interest || 0),
      truck_parking: data.by_month.map((item) => item.truck_parking),
      custom: data.by_month.map(() => 0),
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
    const categories = ['fuel', 'tolls', 'dispatch_fee', 'deduct', 'insurance', 'safety', 'prepass', 'ifta', 'truck_parking', 'driver_pay', 'payroll_fee']
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
    // For "All Time", use dashboard data which has correct totals
    if (expenseAnalysisView === 'all_time') {
      // Always use dashboard data for "all time" as it has accurate totals
      if (!data) return null
      
      // Get expense categories based on vehicle type filter
      let expenseCategories: any = {}
      let grossRevenue = 0
      let netProfit = 0
      let truckProfits: any[] = []
      let totalExpensesFromBackend = 0
      let operationalMetrics: any = {}
      
      if (vehicleTypeFilter === 'trucks' && data.trucks) {
        expenseCategories = data.trucks.expense_categories || {}
        grossRevenue = data.trucks.total_revenue || 0
        netProfit = data.trucks.net_profit || 0
        truckProfits = data.trucks.truck_profits || []
        totalExpensesFromBackend = data.trucks.total_expenses || 0
        operationalMetrics = data.trucks.operational_metrics || {}
        expenseCategories.custom = 0
      } else if (vehicleTypeFilter === 'trailers' && data.trailers) {
        expenseCategories = data.trailers.expense_categories || {}
        grossRevenue = data.trailers.total_revenue || 0
        netProfit = data.trailers.net_profit || 0
        truckProfits = data.trailers.trailer_profits || []
        totalExpensesFromBackend = data.trailers.total_expenses || 0
        operationalMetrics = data.trailers.operational_metrics || {}
        expenseCategories.custom = 0
      } else {
        // Fallback - should not happen since 'all' is removed
        expenseCategories = {}
        grossRevenue = 0
        netProfit = 0
        truckProfits = []
        totalExpensesFromBackend = 0
        operationalMetrics = {}
      }

      // Remove custom expenses from totals/net profit to align with settlement net profit
      const customAmount = expenseCategories.custom || 0
      const adjustedTotalExpenses = Math.max(0, (totalExpensesFromBackend || 0) - customAmount)
      const adjustedNetProfit = netProfit + customAmount
      
      const aggregated = {
        all_time_key: 'all_time',
        all_time_label: 'All Time',
        gross_revenue: grossRevenue,
        raw_gross_revenue: operationalMetrics.raw_gross_revenue || 0,
        raw_gross_miles_driven: operationalMetrics.raw_gross_miles_driven || 0,
        miles_driven: operationalMetrics.miles_driven || 0,
        net_profit: adjustedNetProfit,
        expenses: operationalMetrics.settlement_expenses || 0,
        total_expenses: (() => {
          return adjustedTotalExpenses
        })(),
        driver_pay: expenseCategories.driver_pay || 0,
        payroll_fee: expenseCategories.payroll_fee || 0,
        fuel: expenseCategories.fuel || 0,
        tolls: expenseCategories.tolls || 0,
        dispatch_fee: expenseCategories.dispatch_fee || 0,
        deduct: expenseCategories.deduct || 0,
        insurance: expenseCategories.insurance || 0,
        safety: expenseCategories.safety || 0,
        prepass: expenseCategories.prepass || 0,
        ifta: expenseCategories.ifta || 0,
        loan_interest: expenseCategories.loan_interest || 0,
        truck_parking: expenseCategories.truck_parking || 0,
        service_on_truck: expenseCategories.service_on_truck || 0,
        custom: 0,
        repairs: operationalMetrics.repair_costs || expenseCategories.repairs || 0,
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
  const availableExpensePeriods = expenseAnalysisView === 'weekly'
    ? (Array.isArray(timeSeriesData?.by_week) ? timeSeriesData.by_week : [])
    : expenseAnalysisView === 'monthly'
    ? (Array.isArray(timeSeriesData?.by_month) ? timeSeriesData.by_month : [])
    : expenseAnalysisView === 'yearly'
    ? (Array.isArray(timeSeriesData?.by_year) ? timeSeriesData.by_year : [])
    : []
  const hasAnyTimeSeriesPeriods = Boolean(
    (timeSeriesData?.by_week?.length || 0) > 0 ||
    (timeSeriesData?.by_month?.length || 0) > 0 ||
    (timeSeriesData?.by_year?.length || 0) > 0
  )
  const isTimeSeriesPending = !timeSeriesReady
  const getSelectedPeriodsList = () => {
    if (!timeSeriesData) return []
    if (expenseAnalysisView === 'weekly') return Array.isArray(timeSeriesData.by_week) ? timeSeriesData.by_week : []
    if (expenseAnalysisView === 'monthly') return Array.isArray(timeSeriesData.by_month) ? timeSeriesData.by_month : []
    if (expenseAnalysisView === 'yearly') return Array.isArray(timeSeriesData.by_year) ? timeSeriesData.by_year : []
    return []
  }

  const getSelectedPeriodKey = () => {
    if (expenseAnalysisView === 'weekly') return 'week_key'
    if (expenseAnalysisView === 'monthly') return 'month_key'
    if (expenseAnalysisView === 'yearly') return 'year_key'
    return ''
  }

  const getComparisonPeriodLabel = () => {
    if (expenseAnalysisView === 'weekly') return 'previous week'
    if (expenseAnalysisView === 'monthly') return 'previous month'
    if (expenseAnalysisView === 'yearly') return 'previous year'
    return 'previous period'
  }

  const getComparisonPeriodUnit = () => {
    if (expenseAnalysisView === 'weekly') return 'week'
    if (expenseAnalysisView === 'monthly') return 'month'
    if (expenseAnalysisView === 'yearly') return 'year'
    return 'period'
  }

  const getPeriodDisplayLabel = (periodData: any) => {
    if (!periodData) return getComparisonPeriodLabel()
    if (expenseAnalysisView === 'weekly') return periodData.week_label || periodData.week_key || getComparisonPeriodLabel()
    if (expenseAnalysisView === 'monthly') return periodData.month_label || periodData.month_key || getComparisonPeriodLabel()
    if (expenseAnalysisView === 'yearly') return periodData.year_label || periodData.year_key || getComparisonPeriodLabel()
    return getComparisonPeriodLabel()
  }

  const getPeriodComparisonSignature = (periodData: any) => {
    if (!periodData) return null

    const truckIds = Array.isArray(periodData.trucks)
      ? periodData.trucks
          .map((truck: any) => Number(truck?.truck_id))
          .filter((truckId: number) => Number.isFinite(truckId))
          .sort((a: number, b: number) => a - b)
      : []

    const settlementTypes = Array.isArray(periodData.settlement_types)
      ? periodData.settlement_types
          .map((settlementType: any) => String(settlementType || '').trim())
          .filter(Boolean)
          .sort()
      : []

    return JSON.stringify({
      truckIds,
      settlementTypes,
    })
  }

  const getPeriodComparisonContext = (periodData: any) => {
    if (!periodData) return null

    const comparisonSignature = getPeriodComparisonSignature(periodData)
    const truckIds = Array.isArray(periodData.trucks)
      ? periodData.trucks
          .map((truck: any) => Number(truck?.truck_id))
          .filter((truckId: number) => Number.isFinite(truckId))
          .sort((a: number, b: number) => a - b)
      : []
    const settlementTypes = Array.isArray(periodData.settlement_types)
      ? periodData.settlement_types
          .map((settlementType: any) => String(settlementType || '').trim())
          .filter(Boolean)
          .sort()
      : []

    return {
      truckIds,
      settlementTypes,
      comparisonSignature,
    }
  }

  const isComparablePreviousPeriod = (currentPeriod: any, candidatePeriod: any) => {
    const currentContext = getPeriodComparisonContext(currentPeriod)
    const candidateContext = getPeriodComparisonContext(candidatePeriod)

    if (!currentContext || !candidateContext) return false
    if (currentContext.truckIds.length === 0 || candidateContext.truckIds.length === 0) return false

    const shouldUseSingleTruckComparison = selectedTruck != null || currentContext.truckIds.length === 1
    if (shouldUseSingleTruckComparison) {
      if (candidateContext.truckIds.length !== 1 || candidateContext.truckIds[0] !== currentContext.truckIds[0]) {
        return false
      }

      if (currentContext.settlementTypes.length === 1) {
        return (
          candidateContext.settlementTypes.length === 1 &&
          candidateContext.settlementTypes[0] === currentContext.settlementTypes[0]
        )
      }

      return true
    }

    return (
      currentContext.comparisonSignature != null &&
      currentContext.comparisonSignature === candidateContext.comparisonSignature
    )
  }

  const selectedPeriods = getSelectedPeriodsList() as TimeSeriesPeriod[]
  const selectedPeriodKey = getSelectedPeriodKey() as keyof TimeSeriesPeriod
  const selectedPeriodIndex =
    selectedExpensePeriod && selectedPeriodKey
      ? selectedPeriods.findIndex((period) => period[selectedPeriodKey] === selectedExpensePeriod)
      : -1

  const getPreviousPeriodWithValue = (
    valueGetter: (period: TimeSeriesPeriod) => number | null,
  ) => {
    if (selectedPeriodIndex <= 0) return null
    for (let index = selectedPeriodIndex - 1; index >= 0; index -= 1) {
      const candidatePeriod = selectedPeriods[index]
      const value = valueGetter(candidatePeriod)
      if (value != null && Number.isFinite(value)) {
        return {
          period: candidatePeriod,
          index,
          value,
        }
      }
    }
    return null
  }

  const getComparablePreviousPeriodInfo = () => {
    if (!selectedExpensePeriod || expenseAnalysisView === 'all_time' || !selectedPeriodData) return null
    if (selectedPeriodIndex <= 0) return null

    for (let index = selectedPeriodIndex - 1; index >= 0; index -= 1) {
      const candidatePeriod = selectedPeriods[index]
      if (isComparablePreviousPeriod(selectedPeriodData, candidatePeriod)) {
        return {
          period: candidatePeriod as any,
          index,
        }
      }
    }

    return null
  }

  const previousComparablePeriodInfo = getComparablePreviousPeriodInfo()
  const previousPeriodData = previousComparablePeriodInfo?.period ?? null
  const hasAnyPriorPeriods = selectedPeriodIndex > 0
  const comparisonReferenceLabel = previousComparablePeriodInfo
    ? getPeriodDisplayLabel(previousComparablePeriodInfo.period)
    : getComparisonPeriodLabel()
  const singleTruckComparisonMode =
    selectedTruck != null || (getPeriodComparisonContext(selectedPeriodData)?.truckIds.length || 0) === 1
  const shouldSuppressComparison =
    expenseAnalysisView !== 'all_time' &&
    hasAnyPriorPeriods &&
    previousComparablePeriodInfo == null
  const comparisonUnavailableMessage = singleTruckComparisonMode
    ? `Comparison unavailable. No comparable prior ${getComparisonPeriodUnit()} for this truck/source mix.`
    : `Comparison unavailable. No comparable prior ${getComparisonPeriodUnit()} for this vehicle/source mix.`

  const getPeriodRepairCost = (periodData: any) => {
    if (!periodData) return 0
    return getRepairCostForSelectedPeriod(periodData)
  }

  const calculatePeriodMetrics = (periodData: any) => {
    if (!periodData) {
      return {
        totalMiles: null,
        revenuePerMile: null,
        rawGrossPerMile: null,
        settlementCostPerMile: null,
        allInCostPerMile: null,
      }
    }

    const milesDriven = Number(periodData.miles_driven) || 0
    const rawGrossRevenue = Number(periodData.raw_gross_revenue) || 0
    const rawGrossMilesDriven = Number(periodData.raw_gross_miles_driven) || 0
    const settlementExpenses = Number(periodData.expenses) || 0
    const repairsForPeriod = getPeriodRepairCost(periodData)

    return {
      totalMiles: milesDriven > 0 ? milesDriven : null,
      revenuePerMile: milesDriven > 0 ? Number(periodData.gross_revenue) / milesDriven : null,
      rawGrossPerMile: rawGrossMilesDriven > 0 ? rawGrossRevenue / rawGrossMilesDriven : null,
      settlementCostPerMile: milesDriven > 0 ? settlementExpenses / milesDriven : null,
      allInCostPerMile: milesDriven > 0 ? (settlementExpenses + repairsForPeriod) / milesDriven : null,
    }
  }

  const previousPeriodMetrics = calculatePeriodMetrics(previousPeriodData)
  const previousDieselBenchmarkInfo = getPreviousPeriodWithValue((period) => {
    const price = Number((period as any).diesel_price_per_gallon) || 0
    return price > 0 ? price : null
  })
  const previousDieselBenchmarkLabel = previousDieselBenchmarkInfo
    ? getPeriodDisplayLabel(previousDieselBenchmarkInfo.period)
    : getComparisonPeriodLabel()
  const getTrendWindowLabel = () => {
    if (expenseAnalysisView === 'weekly') return 'Recent weeks'
    if (expenseAnalysisView === 'monthly') return 'Recent months'
    if (expenseAnalysisView === 'yearly') return 'Recent years'
    return 'Recent periods'
  }

  const buildSelectedPeriodTrendPoints = (
    metricGetter: (period: TimeSeriesPeriod) => number | null,
  ): MetricTrendPoint[] => {
    if (!selectedExpensePeriod || expenseAnalysisView === 'all_time') return []

    if (selectedPeriodIndex < 0) return []

    const recentWindowStart = Math.max(0, selectedPeriodIndex - 5)
    const comparisonIndex = previousComparablePeriodInfo?.index ?? selectedPeriodIndex - 1
    const trendWindowStart =
      comparisonIndex >= 0 ? Math.min(recentWindowStart, comparisonIndex) : recentWindowStart

    return selectedPeriods
      .slice(trendWindowStart, selectedPeriodIndex + 1)
      .map((period, index) => {
        const absoluteIndex = trendWindowStart + index
        const value = metricGetter(period)
        if (value == null || !Number.isFinite(value)) return null

        const label =
          expenseAnalysisView === 'weekly'
            ? period.week_label || period.week_key || `Week ${absoluteIndex + 1}`
            : expenseAnalysisView === 'monthly'
            ? period.month_label || period.month_key || `Month ${absoluteIndex + 1}`
            : period.year_label || period.year_key || `Year ${absoluteIndex + 1}`

        return {
          label,
          value,
          isCurrent: absoluteIndex === selectedPeriodIndex,
          isPrevious: absoluteIndex === comparisonIndex,
        }
      })
      .filter((point): point is MetricTrendPoint => point != null)
  }

  const selectableVehicles = trucks.filter((truck) =>
    vehicleTypeFilter === 'trucks'
      ? truck.vehicle_type === 'truck'
      : truck.vehicle_type === 'trailer'
  )

  const getMatchingBusinessPeriod = (series: TimeSeriesData | null) => {
    if (!series || expenseAnalysisView === 'all_time') return null
    const periods =
      expenseAnalysisView === 'weekly'
        ? series.by_week
        : expenseAnalysisView === 'monthly'
        ? series.by_month
        : series.by_year
    const keyName = expenseAnalysisView === 'weekly' ? 'week_key' : expenseAnalysisView === 'monthly' ? 'month_key' : 'year_key'
    if (!periods.length) return null
    if (!selectedExpensePeriod) return periods[periods.length - 1] as any
    return ((periods as any[]).find((period) => period[keyName] === selectedExpensePeriod) || null) as any
  }

  const sumNetProfitAcrossSeries = (series: TimeSeriesData | null) => {
    if (!series) return 0
    return series.by_year.reduce((sum, period) => sum + (Number(period.net_profit) || 0), 0)
  }

  const detailReserveBalances = selectedTruck
    ? reserveBalances.filter((row) => row.truck_id === selectedTruck)
    : reserveBalances
  const summaryReserveBalance = reserveBalances.reduce((sum, row) => sum + (Number(row.balance) || 0), 0)
  const summaryReserveDepositsToDate = reserveBalances.reduce((sum, row) => sum + (Number(row.deposits_total) || 0), 0)
  const detailReserveBalance = detailReserveBalances.reduce((sum, row) => sum + (Number(row.balance) || 0), 0)
  const detailReserveDepositsToDate = detailReserveBalances.reduce((sum, row) => sum + (Number(row.deposits_total) || 0), 0)
  const detailReserveWithdrawalsToDate = detailReserveBalances.reduce((sum, row) => sum + (Number(row.withdrawals_total) || 0), 0)
  const detailReserveAdjustmentsToDate = detailReserveBalances.reduce((sum, row) => sum + (Number(row.adjustments_total) || 0), 0)
  const businessTruckPeriod = getMatchingBusinessPeriod(businessTimeSeries.truck)
  const businessTrailerPeriod = getMatchingBusinessPeriod(businessTimeSeries.trailer)
  const businessReserveDepositsThisPeriod = expenseAnalysisView === 'all_time'
    ? summaryReserveDepositsToDate
    : Number((businessTruckPeriod as any)?.repair_reserve_amount) || 0
  const truckNetProfitTotal = expenseAnalysisView === 'all_time'
    ? sumNetProfitAcrossSeries(businessTimeSeries.truck) || Number(businessSummary?.trucks?.net_profit) || 0
    : Number((businessTruckPeriod as any)?.net_profit) || 0
  const trailerNetProfitTotal = expenseAnalysisView === 'all_time'
    ? sumNetProfitAcrossSeries(businessTimeSeries.trailer) || Number(businessSummary?.trailers?.net_profit) || 0
    : Number((businessTrailerPeriod as any)?.net_profit) || 0
  const businessTotalProfit = truckNetProfitTotal + trailerNetProfitTotal
  const businessPeriodSectionLabel = expenseAnalysisView === 'all_time' ? 'All Time' : 'This Period'

  const renderMetricTrend = (
    currentValue: number | null,
    previousValue: number | null,
    prefersLower: boolean,
    deltaFormatter: (value: number) => string = formatMetricDelta,
  ) => {
    if (shouldSuppressComparison) {
      return <div className="text-[10px] sm:text-xs text-gray-400 mt-1">{comparisonUnavailableMessage}</div>
    }

    if (expenseAnalysisView === 'all_time' || currentValue == null || previousValue == null) {
      return <div className="text-[10px] sm:text-xs text-gray-400 mt-1">No prior comparison</div>
    }

    const difference = currentValue - previousValue
    if (Math.abs(difference) < 0.005) {
      return (
        <div className="text-[10px] sm:text-xs text-gray-500 mt-1">
          <span className="font-semibold">→</span> Flat vs {getComparisonPeriodLabel()}
        </div>
      )
    }

    const direction = difference > 0 ? 'up' : 'down'
    const improved = prefersLower ? difference < 0 : difference > 0
    const colorClass = improved ? 'text-green-600' : 'text-red-600'
    const arrow = direction === 'up' ? '↑' : '↓'
    const movementLabel = direction === 'up' ? 'up' : 'down'

    return (
      <div className={`text-[10px] sm:text-xs mt-1 ${colorClass}`}>
        <span className="font-semibold">{arrow}</span> {movementLabel} {deltaFormatter(difference)} vs {comparisonReferenceLabel}
      </div>
    )
  }

  const renderMetricTrendSparkline = (
    points: MetricTrendPoint[],
    strokeColor: string,
    fillColor: string,
    valueFormatter: (value: number) => string,
  ) => {
    if (shouldSuppressComparison || expenseAnalysisView === 'all_time') return null

    return (
      <>
        <MetricSparkline
          points={points}
          strokeColor={strokeColor}
          fillColor={fillColor}
          valueFormatter={valueFormatter}
        />
        <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-gray-400">{getTrendWindowLabel()}</div>
      </>
    )
  }

  const renderDieselBenchmarkTrend = (currentValue: number | null, previousValue: number | null) => {
    if (expenseAnalysisView === 'all_time' || currentValue == null || previousValue == null) {
      return <div className="text-[10px] sm:text-xs text-gray-400 mt-1">No prior comparison</div>
    }

    const difference = currentValue - previousValue
    if (Math.abs(difference) < 0.0005) {
      return (
        <div className="text-[10px] sm:text-xs text-gray-500 mt-1">
          <span className="font-semibold">→</span> Flat vs {previousDieselBenchmarkLabel}
        </div>
      )
    }

    const direction = difference > 0 ? 'up' : 'down'
    const colorClass = difference > 0 ? 'text-red-600' : 'text-green-600'
    const arrow = direction === 'up' ? '↑' : '↓'

    return (
      <div className={`text-[10px] sm:text-xs mt-1 ${colorClass}`}>
        <span className="font-semibold">{arrow}</span> {direction} {formatDieselMetricDelta(difference)} vs {previousDieselBenchmarkLabel}
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4 sm:mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Dashboard</h1>
      </div>

      {vehicleTypeFilter !== 'trailers' && <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Business Total</h2>
            <p className="mt-1 text-sm text-gray-600">
              Truck and trailer profit combined across all vehicles.
            </p>
          </div>
          <div className="text-left lg:text-right">
            <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Total Business Profit</div>
            <div className={`text-2xl font-bold ${businessTotalProfit >= 0 ? 'text-green-700' : 'text-red-600'}`}>
              ${safeToLocaleString(businessTotalProfit)}
            </div>
          </div>
        </div>
        <div className="mt-5 xl:flex xl:items-stretch xl:gap-5">
          <div className="flex-1">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500">{businessPeriodSectionLabel}</div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
                <div className="text-xs font-medium text-gray-600">Truck Profits</div>
                <div className={`mt-1 text-xl font-bold ${truckNetProfitTotal >= 0 ? 'text-blue-700' : 'text-red-600'}`}>
                  ${safeToLocaleString(truckNetProfitTotal)}
                </div>
              </div>
              <div className="rounded-lg border border-purple-100 bg-purple-50 p-3">
                <div className="text-xs font-medium text-gray-600">Trailer Profits</div>
                <div className={`mt-1 text-xl font-bold ${trailerNetProfitTotal >= 0 ? 'text-purple-700' : 'text-red-600'}`}>
                  ${safeToLocaleString(trailerNetProfitTotal)}
                </div>
              </div>
              <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                <div className="text-xs font-medium text-gray-600">Reserve Deposited This Period</div>
                <div className="mt-1 text-xl font-bold text-amber-700">
                  ${safeToLocaleString(businessReserveDepositsThisPeriod)}
                </div>
              </div>
            </div>
          </div>
          <div className="my-5 hidden w-px bg-slate-200 xl:block" />
          <div className="mt-5 xl:mt-0 xl:w-72 xl:flex-shrink-0">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500">Running Totals</div>
            <div className="mt-3">
              <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
                <div className="text-xs font-medium text-gray-600">Reserve Balance (to date)</div>
                <div className={`mt-1 text-xl font-bold ${summaryReserveBalance >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                  ${safeToLocaleString(summaryReserveBalance)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>}

      {/* Detailed Expense Analysis Section - First Chart */}
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <div className="flex flex-col mb-6 gap-4">
            <h2 className="text-2xl font-semibold text-gray-900">Detailed Expense Analysis</h2>
            <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-3">
              <div className="flex flex-col lg:flex-row lg:items-center gap-3">
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
                    🚚 Vehicles
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
                <select
                  value={selectedTruck || ''}
                  onChange={(e) => setSelectedTruck(e.target.value ? Number(e.target.value) : null)}
                  className="w-full lg:w-auto px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  <option value="">All Vehicles</option>
                  {selectableVehicles.map((truck) => (
                    <option key={truck.id} value={truck.id}>
                      {truck.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center justify-center flex-1 gap-2 overflow-x-auto">
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
                    <div className="h-px w-4 md:w-8 bg-gray-300" />
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
                <div className="h-px w-4 md:w-8 bg-gray-300" />
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
                <div className="h-px w-4 md:w-8 bg-gray-300" />
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
              {expenseAnalysisView !== 'all_time' && (
                <div className="w-full xl:w-auto">
                  <select
                    value={selectedExpensePeriod}
                    onChange={(e) => setSelectedExpensePeriod(e.target.value)}
                    disabled={isTimeSeriesPending || availableExpensePeriods.length === 0}
                    className="w-full xl:w-auto px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
                  >
                    {availableExpensePeriods.map((period: any) => {
                      const key = expenseAnalysisView === 'weekly' ? period.week_key : expenseAnalysisView === 'monthly' ? period.month_key : period.year_key
                      const label = expenseAnalysisView === 'weekly' ? period.week_label : expenseAnalysisView === 'monthly' ? period.month_label : period.year_label
                      return (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      )
                    })}
                  </select>
                </div>
              )}
            </div>
          </div>

          {isTimeSeriesPending ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                Loading detailed expense metrics...
              </div>
              <div className="grid grid-cols-1 gap-2 sm:gap-4 md:grid-cols-3">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div key={index} className="h-20 animate-pulse rounded-lg bg-slate-100" />
                ))}
              </div>
              <div className="grid grid-cols-1 gap-2 sm:gap-4 md:grid-cols-2 xl:grid-cols-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="h-32 animate-pulse rounded-lg bg-slate-100" />
                ))}
              </div>
            </div>
          ) : !hasAnyTimeSeriesPeriods ? (
            <div className="text-center py-8 text-gray-500">
              No time-series data available. Please ensure you have settlements with dates.
            </div>
          ) : selectedPeriodData ? (
            <div className="space-y-6">
              {(() => {
                // Calculate repairs for the selected period to show True Net Profit
                const pd = selectedPeriodData as any
                const repairsForPeriod = getRepairCostForSelectedPeriod(pd)
                
                    const netProfitValue = Number(selectedPeriodData.net_profit) || 0
                    const loanInterestOuter = Number(pd.loan_interest) || 0
                    const trailerSplitOuter = vehicleTypeFilter === 'trailers'
                      ? Math.max(0, (Number(selectedPeriodData.gross_revenue) || 0) - netProfitValue)
                      : Number(pd.trailer_income_split_amount) || 0
                    const repairReserveOuter = Number(pd.repair_reserve_amount) || 0
                    const grossSettlementProfit = netProfitValue + loanInterestOuter + trailerSplitOuter + repairReserveOuter
                    const milesDriven = Number(pd.miles_driven) || 0
                    const rawGrossRevenue = Number(pd.raw_gross_revenue) || 0
                    const rawGrossMilesDriven = Number(pd.raw_gross_miles_driven) || 0
                    const settlementExpenses = Number(pd.expenses) || 0
                    const revenuePerMile = milesDriven > 0 ? Number(selectedPeriodData.gross_revenue) / milesDriven : null
                    const rawGrossPerMile = rawGrossMilesDriven > 0 ? rawGrossRevenue / rawGrossMilesDriven : null
                    const settlementCostPerMile = milesDriven > 0 ? settlementExpenses / milesDriven : null
                    const allInCostPerMile = milesDriven > 0 ? (settlementExpenses + repairsForPeriod) / milesDriven : null
                    const involvedTruckNames = Array.isArray(pd.trucks)
                      ? Array.from(
                          new Set(
                            pd.trucks
                              .map((truck: any) => String(truck?.truck_name || '').trim())
                              .filter(Boolean)
                          )
                        )
                      : []
                    const dieselBenchmarkPrice = Number(pd.diesel_price_per_gallon) || 0
                    const involvedTrucksLabel =
                      expenseAnalysisView === 'weekly'
                        ? 'Trucks included this week'
                        : expenseAnalysisView === 'monthly'
                        ? 'Trucks included this month'
                        : expenseAnalysisView === 'yearly'
                        ? 'Trucks included this year'
                        : 'Included trucks'
                    const dieselBenchmarkLabel =
                      expenseAnalysisView === 'weekly'
                        ? 'Avg diesel price this week'
                        : expenseAnalysisView === 'monthly'
                        ? 'Avg diesel price this month'
                        : expenseAnalysisView === 'yearly'
                        ? 'Avg diesel price this year'
                        : 'Avg diesel price'
                    const showCostPerMileParityNote =
                      vehicleTypeFilter === 'trucks' &&
                      repairsForPeriod === 0 &&
                      settlementCostPerMile != null &&
                      allInCostPerMile != null
                    const revenuePerMileDescription = 'Gross revenue divided by miles driven. This is revenue efficiency, not a cost metric.'
                    const rawGrossPerMileDescription = 'Pre-dispatch gross divided by miles from settlements that include raw-gross data.'
                    const settlementCostPerMileDescription = 'Settlement expenses divided by miles driven. This is booked cost per mile before repairs.'
                    const allInCostPerMileDescription = 'Settlement expenses plus repairs for this period, divided by miles driven.'
                    const totalMilesTrendPoints = buildSelectedPeriodTrendPoints((period) => calculatePeriodMetrics(period).totalMiles)
                    const revenuePerMileTrendPoints = buildSelectedPeriodTrendPoints((period) => calculatePeriodMetrics(period).revenuePerMile)
                    const settlementCostTrendPoints = buildSelectedPeriodTrendPoints((period) => calculatePeriodMetrics(period).settlementCostPerMile)
                    const dieselBenchmarkTrendPoints = buildSelectedPeriodTrendPoints((period) => {
                      const price = Number((period as any).diesel_price_per_gallon) || 0
                      return price > 0 ? price : null
                    })
                
                return (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 sm:gap-4 mb-4 sm:mb-6">
                      <div className="bg-blue-50 p-2 sm:p-4 rounded-lg">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-xs sm:text-sm font-medium text-gray-600">Gross Revenue:</span>
                          <span className="text-base sm:text-xl font-bold text-blue-600">
                            ${safeToLocaleString(selectedPeriodData.gross_revenue)}
                          </span>
                        </div>
                        <div className="text-[10px] sm:text-xs text-gray-500">{expenseAnalysisView === 'all_time' ? 'All time cumulative' : `For this ${expenseAnalysisView === 'weekly' ? 'week' : expenseAnalysisView === 'monthly' ? 'month' : 'year'} only`}</div>
                      </div>
                      {vehicleTypeFilter === 'trailers' ? (
                        <>
                          <div className="bg-amber-50 p-2 sm:p-4 rounded-lg">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <span className="text-xs sm:text-sm font-medium text-gray-600">Depreciation Recoupment:</span>
                              <span className="text-base sm:text-xl font-bold text-amber-600">
                                ${safeToLocaleString(trailerSplitOuter)}
                              </span>
                            </div>
                            <div className="text-[10px] sm:text-xs text-gray-500">Earmarked — stays yours</div>
                          </div>
                          <div className="bg-green-50 p-2 sm:p-4 rounded-lg">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <span className="text-xs sm:text-sm font-medium text-gray-600">Take-Home Profit</span>
                              <span className={`text-base sm:text-xl font-bold ${netProfitValue >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                ${safeToLocaleString(netProfitValue)}
                              </span>
                            </div>
                            <div className="text-[10px] sm:text-xs text-gray-500">{expenseAnalysisView === 'all_time' ? 'All time cumulative' : `For this ${expenseAnalysisView === 'weekly' ? 'week' : expenseAnalysisView === 'monthly' ? 'month' : 'year'} only`}</div>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="bg-red-50 p-2 sm:p-4 rounded-lg">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <span className="text-xs sm:text-sm font-medium text-gray-600">Total Expenses:</span>
                              <span className="text-base sm:text-xl font-bold text-red-600">
                                ${(() => {
                                  const customAmt = Number((selectedPeriodData as any).custom) || 0
                                  if (pd.total_expenses !== undefined && pd.total_expenses > 0) {
                                    return Math.max(0, pd.total_expenses - customAmt)
                                  }
                                  const sum = (
                                    (Number(pd.fuel) || 0) +
                                    (Number(pd.tolls) || 0) +
                                    (Number(pd.dispatch_fee) || 0) +
                                    (Number(pd.deduct) || 0) +
                                    (Number(pd.insurance) || 0) +
                                    (Number(pd.safety) || 0) +
                                    (Number(pd.prepass) || 0) +
                                    (Number(pd.ifta) || 0) +
                                    (Number(pd.loan_interest) || 0) +
                                    (Number(pd.truck_parking) || 0) +
                                    (Number(pd.driver_pay) || 0) +
                                    (Number(pd.payroll_fee) || 0) +
                                    (expenseAnalysisView === 'yearly' || expenseAnalysisView === 'monthly' || expenseAnalysisView === 'all_time' ? (Number(pd.repairs) || 0) : 0)
                                  )
                                  return isNaN(sum) ? 0 : Math.max(0, sum - customAmt)
                                })().toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </span>
                            </div>
                            <div className="text-[10px] sm:text-xs text-gray-500">{expenseAnalysisView === 'all_time' ? 'All time cumulative' : `For this ${expenseAnalysisView === 'weekly' ? 'week' : expenseAnalysisView === 'monthly' ? 'month' : 'year'} only`}</div>
                          </div>
                          <div className="bg-green-50 p-2 sm:p-4 rounded-lg">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <span className="text-xs sm:text-sm font-medium text-gray-600">Settlement Net Profit</span>
                              <span className={`text-base sm:text-xl font-bold ${grossSettlementProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                ${safeToLocaleString(grossSettlementProfit)}
                              </span>
                            </div>
                            <div className="text-[10px] sm:text-xs text-gray-500">{expenseAnalysisView === 'all_time' ? 'All time cumulative' : `For this ${expenseAnalysisView === 'weekly' ? 'week' : expenseAnalysisView === 'monthly' ? 'month' : 'year'} only`}</div>
                          </div>
                        </>
                      )}
                    </div>

                    {vehicleTypeFilter === 'trucks' && involvedTruckNames.length > 0 && (
                      <div className="mb-4 sm:mb-6 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 sm:px-4 sm:py-3">
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                          <div className="md:flex-1">
                            <div className="text-[10px] sm:text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                              {involvedTrucksLabel}
                            </div>
                            <div className="mt-1 text-sm sm:text-base text-slate-700">
                              {involvedTruckNames.join(', ')}
                            </div>
                          </div>
                          <div className="border-t border-slate-200 pt-3 md:w-72 md:flex-shrink-0 md:border-t-0 md:pt-0 md:pl-4 md:text-right">
                            <div className="text-[10px] sm:text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                              {dieselBenchmarkLabel}
                            </div>
                            {dieselBenchmarkLoading && dieselBenchmarkPrice <= 0 ? (
                              <div className="mt-2 space-y-2 md:ml-auto md:w-52">
                                <div className="text-sm sm:text-base font-medium text-slate-500">Loading diesel benchmark...</div>
                                <div className="h-10 animate-pulse rounded bg-slate-100" />
                              </div>
                            ) : dieselBenchmarkPrice > 0 ? (
                              <>
                                <div className="mt-1 text-sm sm:text-base font-medium text-slate-700">
                                  {formatDieselMetricValue(dieselBenchmarkPrice)}
                                </div>
                                <div className="mt-3 flex flex-col gap-3 md:items-end">
                                  {dieselBenchmarkTrendPoints.length > 1 && (
                                    <div className="md:w-52">
                                      <MetricSparkline
                                        points={dieselBenchmarkTrendPoints}
                                        strokeColor="#2563eb"
                                        fillColor="rgba(59, 130, 246, 0.16)"
                                        valueFormatter={formatDieselMetricValue}
                                      />
                                    </div>
                                  )}
                                  <div className="md:text-right">
                                    {renderDieselBenchmarkTrend(
                                      dieselBenchmarkPrice > 0 ? dieselBenchmarkPrice : null,
                                      previousDieselBenchmarkInfo?.value ?? null,
                                    )}
                                  </div>
                                </div>
                              </>
                            ) : (
                              <div className="mt-2 text-sm text-slate-500">Diesel benchmark unavailable.</div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                    {vehicleTypeFilter === 'trucks' && <div className={`grid grid-cols-1 md:grid-cols-2 gap-2 sm:gap-4 mb-6 ${repairsForPeriod > 0 ? 'xl:grid-cols-5' : 'xl:grid-cols-4'}`}>

                      <div className="bg-slate-50 p-3 sm:p-4 rounded-lg border border-slate-200 md:min-h-[120px]">
                        <div className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Miles</div>
                        <div className="text-base sm:text-xl font-bold text-slate-700">
                          {milesDriven > 0 ? `${safeToLocaleString(milesDriven, { minimumFractionDigits: 0, maximumFractionDigits: 2 })} mi` : '—'}
                        </div>
                        {renderMetricTrendSparkline(totalMilesTrendPoints, '#475569', 'rgba(148, 163, 184, 0.18)', formatMilesMetricValue)}
                        {renderMetricTrend(milesDriven > 0 ? milesDriven : null, previousPeriodMetrics.totalMiles, false, formatMilesMetricDelta)}
                      </div>
                      <div className="bg-cyan-50 p-3 sm:p-4 rounded-lg border border-cyan-200 md:min-h-[120px]">
                        <div className="text-xs sm:text-sm font-medium text-gray-600 mb-1">
                          <MetricLabelWithTooltip label="Revenue / Mile" description={revenuePerMileDescription} />
                        </div>
                        <div className="text-base sm:text-xl font-bold text-cyan-700">
                          {formatCurrencyMetric(revenuePerMile)}
                        </div>
                        <div className="mt-1 text-[10px] sm:text-xs text-gray-500 md:hidden">
                          {revenuePerMileDescription}
                        </div>
                        {renderMetricTrendSparkline(revenuePerMileTrendPoints, '#0891b2', 'rgba(34, 211, 238, 0.2)', formatCurrencyMetric)}
                        {renderMetricTrend(revenuePerMile, previousPeriodMetrics.revenuePerMile, false)}
                      </div>
                      <div className="bg-indigo-50 p-3 sm:p-4 rounded-lg border border-indigo-200 md:min-h-[120px]">
                        <div className="text-xs sm:text-sm font-medium text-gray-600 mb-1">
                          <MetricLabelWithTooltip label="Pre-Dispatch Gross / Mile" description={rawGrossPerMileDescription} />
                        </div>
                        <div className="text-base sm:text-xl font-bold text-indigo-700">
                          {formatCurrencyMetric(rawGrossPerMile)}
                        </div>
                        <div className="mt-1 text-[10px] sm:text-xs text-gray-500 md:hidden">
                          {rawGrossPerMileDescription}
                        </div>
                        {renderMetricTrend(rawGrossPerMile, previousPeriodMetrics.rawGrossPerMile, false)}
                      </div>
                      <div className="bg-amber-50 p-3 sm:p-4 rounded-lg border border-amber-200 md:min-h-[120px]">
                        <div className="text-xs sm:text-sm font-medium text-gray-600 mb-1">
                          <MetricLabelWithTooltip label="Settlement Cost / Mile" description={settlementCostPerMileDescription} />
                        </div>
                        <div className="text-base sm:text-xl font-bold text-amber-700">
                          {formatCurrencyMetric(settlementCostPerMile)}
                        </div>
                        <div className="mt-1 text-[10px] sm:text-xs text-gray-500 md:hidden">
                          {settlementCostPerMileDescription}
                        </div>
                        {renderMetricTrendSparkline(settlementCostTrendPoints, '#d97706', 'rgba(251, 191, 36, 0.22)', formatCurrencyMetric)}
                        {renderMetricTrend(settlementCostPerMile, previousPeriodMetrics.settlementCostPerMile, true)}
                      </div>
                      {repairsForPeriod > 0 && (
                        <div className="bg-rose-50 p-3 sm:p-4 rounded-lg border border-rose-200 md:min-h-[120px]">
                          <div className="text-xs sm:text-sm font-medium text-gray-600 mb-1">
                            <MetricLabelWithTooltip label="All-In Cost / Mile" description={allInCostPerMileDescription} />
                          </div>
                          <div className="text-base sm:text-xl font-bold text-rose-700">
                            {formatCurrencyMetric(allInCostPerMile)}
                          </div>
                          <div className="mt-1 text-[10px] sm:text-xs text-gray-500 md:hidden">
                            {allInCostPerMileDescription}
                          </div>
                          {renderMetricTrend(allInCostPerMile, previousPeriodMetrics.allInCostPerMile, true)}
                        </div>
                      )}
                    </div>}
                    {showCostPerMileParityNote && (
                      <div className="mb-6 inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">
                        No repairs in this period. Settlement and all-in cost per mile are equal.
                      </div>
                    )}
                  </>
                )
              })()}

              {/* Net Profit Details & Repair Expenses - Only show for trucks in weekly/monthly/yearly view */}
              {vehicleTypeFilter === 'trucks' && (expenseAnalysisView === 'weekly' || expenseAnalysisView === 'monthly' || expenseAnalysisView === 'yearly') && selectedPeriodData && (() => {
                const periodLabel = expenseAnalysisView === 'weekly' 
                  ? ((selectedPeriodData as any).week_label || 'Selected Week')
                  : expenseAnalysisView === 'monthly'
                  ? ((selectedPeriodData as any).month_label || 'Selected Month')
                  : ((selectedPeriodData as any).year_label || 'Selected Year')
                const loanInterest = Number((selectedPeriodData as any).loan_interest) || 0
                const netProfitValue = Number(selectedPeriodData.net_profit) || 0
                const trailerSplitThisPeriod = Number((selectedPeriodData as any).trailer_income_split_amount) || 0
                const repairReserveThisPeriod = Number((selectedPeriodData as any).repair_reserve_amount) || 0
                const settlementNetProfitBeforeDeductions = netProfitValue + loanInterest + trailerSplitThisPeriod + repairReserveThisPeriod
                const cumulativeTrailerContribution = selectedTrailerContributionTotal
                const reserveDepositsToDate = detailReserveDepositsToDate
                const reserveWithdrawalsToDate = detailReserveWithdrawalsToDate
                const reserveAdjustmentsToDate = detailReserveAdjustmentsToDate
                const reserveCushionToDate = detailReserveBalance
                
                // Filter repairs for the selected period
                const repairsForPeriod = getRepairsForSelectedPeriod(selectedPeriodData)
                
                const reserveFundedRepairs = repairsForPeriod.reduce((sum, repair) => sum + (Number(repair.cost) || 0), 0)
                const takeHomeProfit = netProfitValue
                return (
                  <div className="mb-6 bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">
                      Settlement Breakdown — {periodLabel}
                    </h3>

                    <div className="mb-6 space-y-3">
                      {/* Gross settlement profit before any internal deductions */}
                      <div className="flex justify-between items-center py-2 border-b border-gray-200">
                        <span className="text-sm font-medium text-gray-700">Gross Settlement Profit</span>
                        <span className="text-sm font-semibold text-gray-900">
                          ${safeToLocaleString(settlementNetProfitBeforeDeductions)}
                        </span>
                      </div>

                      {/* Loan interest: truly gone — financing cost */}
                      {loanInterest > 0 && (
                        <div className="flex justify-between items-center py-2 border-b border-gray-200">
                          <span className="text-sm text-gray-600">Less: Loan Interest <span className="text-xs text-gray-400">(financing cost — gone)</span></span>
                          <span className="text-sm font-medium text-red-600">
                            −${safeToLocaleString(loanInterest)}
                          </span>
                        </div>
                      )}

                      {/* Trailer recoupment: stays in your ledger */}
                      {trailerSplitThisPeriod > 0 && (
                        <div className="flex justify-between items-center py-2 border-b border-gray-200">
                          <span className="text-sm text-gray-600">Less: Trailer Depreciation Recoupment <span className="text-xs text-gray-400">(earmarked — stays yours)</span></span>
                          <span className="text-sm font-medium text-purple-600">
                            −${safeToLocaleString(trailerSplitThisPeriod)}
                          </span>
                        </div>
                      )}

                      {/* Repair reserve: stays in your reserve fund */}
                      {repairReserveThisPeriod > 0 && (
                        <div className="flex justify-between items-center py-2 border-b border-gray-200">
                          <span className="text-sm text-gray-600">Less: Repair Reserve <span className="text-xs text-gray-400">(earmarked — stays yours)</span></span>
                          <span className="text-sm font-medium text-amber-600">
                            −${safeToLocaleString(repairReserveThisPeriod)}
                          </span>
                        </div>
                      )}

                      {/* Take-Home Profit: reconciles to the Settlement Net Profit card */}
                      <div className="pt-2">
                        <div className="flex justify-between items-center">
                          <span className="text-base font-semibold text-gray-900">Take-Home Profit</span>
                          <span className={`text-xl font-bold ${takeHomeProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            ${safeToLocaleString(takeHomeProfit)}
                          </span>
                        </div>
                        <div className="mt-1 text-xs text-gray-500">Reconciles to Settlement Net Profit above.</div>
                      </div>

                      {/* Reserve-funded repairs: informational — repairs covered by reserve this period */}
                      {reserveFundedRepairs > 0 && (
                        <div className="flex justify-between items-center py-2 mt-2 border-t border-gray-100 bg-blue-50 -mx-2 px-2 rounded-sm">
                          <span className="text-sm text-gray-700">Reserve-Funded Repairs <span className="text-xs text-gray-400">(paid from reserve, not from take-home)</span></span>
                          <span className="text-sm font-medium text-blue-700">
                            ${safeToLocaleString(reserveFundedRepairs)}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="mb-6 rounded-lg bg-blue-50 border border-blue-200 p-4">
                      <div className="rounded-md border border-blue-200 bg-white/70 px-3 py-3">
                        <button
                          type="button"
                          onClick={() => setCumulativePositionExpanded(!cumulativePositionExpanded)}
                          className="w-full flex items-center justify-between text-left"
                        >
                          <div>
                            <div className="text-sm font-semibold text-gray-900">To-Date Position</div>
                            <div className="text-xs text-gray-500 mt-1">
                              Cumulative trailer contribution and reserve balance across the 2026 reserve regime.
                            </div>
                          </div>
                          <svg
                            className={`w-5 h-5 text-gray-600 transition-transform ${cumulativePositionExpanded ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                        {cumulativePositionExpanded && (
                          <div className="mt-4 space-y-3 border-t border-blue-100 pt-4">
                            <div className="flex justify-between items-center py-1">
                              <span className="text-sm text-gray-600">Trailer Contribution To Date</span>
                              <span className={`text-sm font-semibold ${cumulativeTrailerContribution >= 0 ? 'text-purple-700' : 'text-red-600'}`}>
                                ${safeToLocaleString(cumulativeTrailerContribution)}
                              </span>
                            </div>
                            <div className="flex justify-between items-center py-1">
                              <span className="text-sm text-gray-600">Reserve Deposits To Date</span>
                              <span className="text-sm font-semibold text-amber-700">
                                ${safeToLocaleString(reserveDepositsToDate)}
                              </span>
                            </div>
                            <div className="flex justify-between items-center py-1">
                              <span className="text-sm text-gray-600">Reserve Withdrawals To Date (Repairs)</span>
                              <span className="text-sm font-semibold text-red-600">
                                ${safeToLocaleString(reserveWithdrawalsToDate)}
                              </span>
                            </div>
                            <div className="flex justify-between items-center py-1">
                              <span className="text-sm text-gray-600">Manual Reserve Adjustments To Date</span>
                              <span className="text-sm font-semibold text-slate-700">
                                ${safeToLocaleString(reserveAdjustmentsToDate)}
                              </span>
                            </div>
                            <div className="flex justify-between items-center py-2 border-t border-blue-200">
                              <span className="text-sm font-semibold text-gray-900">Current Reserve Balance (To Date)</span>
                              <span className={`text-base font-bold ${reserveCushionToDate >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                                ${safeToLocaleString(reserveCushionToDate)}
                              </span>
                            </div>
                            <div className="text-xs text-gray-500">
                              Reserve regime starts 2026-01-01. Current balance = deposits + manual adjustments - withdrawals. Repairs paid from reserve appear under withdrawals.
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="mt-3 text-xs text-gray-500">
                        This section is cumulative to date and intentionally separate from the selected-period profit breakdown above.
                      </div>
                    </div>
                    
                    {/* Repair Expenses Details - Collapsible only when repairs exist */}
                    <div className="mt-6">
                      {repairsForPeriod.length > 0 ? (
                        <>
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
                                          ${(repair.cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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
                                    ${safeToLocaleString(reserveFundedRepairs)}
                                  </span>
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg text-center">
                          <p className="text-sm text-gray-600">
                            No repairs {expenseAnalysisView === 'weekly' ? 'this week' : expenseAnalysisView === 'monthly' ? 'this month' : 'this year'}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })()}

              {/* Trucks Involved - Only show for trucks */}
              {vehicleTypeFilter === 'trucks' && (selectedPeriodData as any).trucks && Array.isArray((selectedPeriodData as any).trucks) && (selectedPeriodData as any).trucks.length > 0 && (
                <div className="mb-4">
                  <div className="text-sm font-medium text-gray-700 mb-2">
                    Vehicles Involved ({expenseAnalysisView === 'all_time' ? 'all time' : expenseAnalysisView === 'weekly' ? 'this week' : expenseAnalysisView === 'monthly' ? 'this month' : 'this year'}):
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

              {/* Settlement Breakdown - Show which settlements contribute - Only for trucks */}
              {vehicleTypeFilter === 'trucks' && expenseAnalysisView === 'monthly' && (selectedPeriodData as any).settlements && Array.isArray((selectedPeriodData as any).settlements) && (selectedPeriodData as any).settlements.length > 0 && (
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
                            <td className="px-2 py-1 text-right">${(settlement.insurance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                            <td className="px-2 py-1 text-right">${(settlement.driver_pay || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
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
                        { key: 'tolls', label: 'Tolls', value: (selectedPeriodData as any).tolls || 0 },
                        { key: 'dispatch_fee', label: 'Dispatch Fee', value: (selectedPeriodData as any).dispatch_fee || 0 },
                        { key: 'deduct', label: 'Deductions', value: (selectedPeriodData as any).deduct || 0 },
                        { key: 'fleet_manager_support', label: 'Fleet Manager Support', value: (selectedPeriodData as any).fleet_manager_support || 0 },
                        { key: 'insurance', label: 'Insurance', value: (selectedPeriodData as any).insurance || 0 },
                        { key: 'safety', label: 'Safety', value: (selectedPeriodData as any).safety || 0 },
                        { key: 'prepass', label: 'Prepass', value: (selectedPeriodData as any).prepass || 0 },
                        { key: 'ifta', label: 'IFTA', value: (selectedPeriodData as any).ifta || 0 },
                        { key: 'loan_interest', label: 'Loan Interest', value: (selectedPeriodData as any).loan_interest || 0 },
                        { key: 'truck_parking', label: 'Truck Parking', value: (selectedPeriodData as any).truck_parking || 0 },
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
                                result += `${param.marker}${seriesName}: $${safeToLocaleString(value)} (${percent}%)<br/>`
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
                          top: isMobile ? 'bottom' : 10,
                          bottom: isMobile ? 0 : 'auto',
                          orient: 'horizontal',
                          type: isMobile ? 'scroll' : 'plain',
                          textStyle: {
                            fontSize: isMobile ? 10 : 12
                          },
                          itemGap: isMobile ? 8 : 20,
                          itemWidth: isMobile ? 12 : 25,
                          itemHeight: isMobile ? 8 : 14
                        },
                        grid: {
                          left: isMobile ? '15%' : '10%',
                          right: isMobile ? '12%' : '8%',
                          bottom: isMobile ? '25%' : '3%',
                          top: isMobile ? '8%' : '15%',
                          containLabel: true
                        },
                        xAxis: {
                          type: 'category',
                          data: sortedLabels,
                          axisLabel: {
                            rotate: isMobile ? 45 : 45,
                            fontSize: isMobile ? 9 : 11,
                            interval: isMobile ? 'auto' : 0,
                            margin: isMobile ? 8 : 10
                          }
                        },
                        yAxis: [
                          {
                            type: 'value',
                            name: 'Amount ($)',
                            position: 'left',
                            nameGap: isMobile ? 50 : 40,
                            nameLocation: 'middle',
                            nameTextStyle: {
                              padding: [0, 0, 0, 0]
                            },
                            axisLabel: {
                              formatter: (value: number) => `$${safeToLocaleString(value, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
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
                          show: !isMobile, // Hide labels on mobile to prevent overlap
                          position: 'top',
                          formatter: (params: any) => {
                            const value = params.value || 0
                            const revenue = selectedPeriodData.gross_revenue || 1
                            const percent = ((value / revenue) * 100).toFixed(1)
                            return value > 0 ? `$${safeToLocaleString(value, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}\n(${percent}%)` : ''
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
                        { key: 'tolls', label: 'Tolls' },
                        { key: 'dispatch_fee', label: 'Dispatch Fee' },
                        { key: 'deduct', label: 'Deductions' },
                        { key: 'insurance', label: 'Insurance' },
                        { key: 'safety', label: 'Safety' },
                        { key: 'prepass', label: 'Prepass' },
                        { key: 'ifta', label: 'IFTA' },
                        { key: 'driver_pay', label: "Driver's Pay" },
                        { key: 'payroll_fee', label: 'Payroll Fee' },
                        { key: 'loan_interest', label: 'Loan Interest' },
                        { key: 'truck_parking', label: 'Truck Parking' },
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
                              ${safeToLocaleString(amount)}
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
                    return `${params.name}<br/>$${safeToLocaleString(value)} (${percent}%)`
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
            repairData.push(repair.cost || 0)
            
            // Create tooltip with repair details
            const isPM = repair.category === 'maintenance'
            const pmIndicator = isPM ? '<br/><span style="color: #3b82f6; font-weight: bold;">🔧 Preventive Maintenance</span>' : ''
            const tooltip = `${repair.truck_name}<br/>${repair.description || 'No description'}${pmIndicator}<br/>$${(repair.cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
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
                    return repairTooltips[index] || `${param.axisValue}<br/>$${safeToLocaleString(param.value)}`
                  },
                  backgroundColor: '#fff',
                  borderColor: '#e5e7eb',
                  borderWidth: 1,
                  borderRadius: 8,
                  padding: [8, 12]
                },
                grid: {
                  left: isMobile ? '15%' : '10%',
                  right: isMobile ? '4%' : '4%',
                  bottom: isMobile ? (xAxisData.length > 10 ? '25%' : '20%') : '10%',
                  top: isMobile ? '5%' : 'auto',
                  containLabel: true
                },
                xAxis: {
                  type: 'category',
                  data: xAxisData,
                  axisLabel: {
                    rotate: isMobile ? (xAxisData.length > 6 ? 45 : 0) : (xAxisData.length > 10 ? 45 : 0),
                    fontSize: isMobile ? 9 : 10,
                    interval: isMobile ? 'auto' : 0,
                    margin: isMobile ? 8 : 10
                  }
                },
                yAxis: {
                  type: 'value',
                  name: 'Cost ($)',
                  nameGap: isMobile ? 50 : 40,
                  nameLocation: 'middle',
                  nameTextStyle: {
                    padding: [0, 0, 0, 0]
                  },
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
                      show: !isMobile, // Hide labels on mobile to prevent overlap
                      position: 'top',
                      formatter: (params: any) => {
                        const value = params.value || 0
                        return value > 0 ? `$${safeToLocaleString(value, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : ''
                      },
                      fontSize: isMobile ? 8 : 9
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
                top: isMobile ? 'bottom' : 30,
                bottom: isMobile ? 0 : 'auto',
                orient: isMobile ? 'horizontal' : 'horizontal',
                type: isMobile ? 'scroll' : 'plain',
                textStyle: {
                  fontSize: isMobile ? 10 : 12
                },
                itemGap: isMobile ? 8 : 20,
                itemWidth: isMobile ? 12 : 25,
                itemHeight: isMobile ? 8 : 14
              },
              grid: {
                left: isMobile ? '15%' : '10%',
                right: isMobile ? '4%' : '4%',
                bottom: isMobile ? (blocksChartData.months.length > 6 ? '25%' : '20%') : '3%',
                top: isMobile ? '8%' : '15%',
                containLabel: true
              },
              xAxis: {
                type: 'category',
                data: blocksChartData.months,
                axisLabel: {
                  rotate: isMobile ? (blocksChartData.months.length > 4 ? 45 : 0) : (blocksChartData.months.length > 6 ? 45 : 0),
                  fontSize: isMobile ? 9 : 11,
                  interval: isMobile ? 'auto' : 0,
                  margin: isMobile ? 8 : 10
                }
              },
              yAxis: {
                type: 'value',
                name: 'Blocks',
                nameGap: isMobile ? 50 : 40,
                nameLocation: 'middle',
                nameTextStyle: {
                  padding: [0, 0, 0, 0]
                },
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
                      fontSize: isMobile ? 9 : 10,
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
                        show: !isMobile, // Hide target label on mobile to prevent overlap
                        position: 'end',
                        formatter: 'Target: 11 blocks',
                        color: '#f59e0b',
                        fontSize: isMobile ? 9 : 11,
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


      {/* Time-Series Charts Section - Only show for trucks */}
      {vehicleTypeFilter === 'trucks' && timeSeriesData && (
        <div className="mt-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-semibold text-gray-900">Time-Series Analytics</h2>
            <div className="inline-flex rounded-md shadow-sm" role="group">
              <button
                type="button"
                onClick={() => setActiveTimeView('weekly')}
                className={`px-2 py-1 text-xs font-medium border rounded-l-lg ${
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
                className={`px-2 py-1 text-xs font-medium border rounded-r-lg ${
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
                        top: isMobile ? 'bottom' : 10,
                        bottom: isMobile ? 0 : 'auto',
                        orient: 'horizontal',
                        type: isMobile ? 'scroll' : 'plain',
                        textStyle: {
                          fontSize: isMobile ? 10 : 12
                        },
                        itemGap: isMobile ? 8 : 20,
                        itemWidth: isMobile ? 12 : 25,
                        itemHeight: isMobile ? 8 : 14
                      },
                      grid: {
                        left: isMobile ? '15%' : '10%',
                        right: isMobile ? '4%' : '4%',
                        bottom: isMobile ? (currentData.labels.length > 10 ? '25%' : '20%') : '3%',
                        top: isMobile ? '8%' : '15%',
                        containLabel: true
                      },
                      xAxis: {
                        type: 'category',
                        data: currentData.labels,
                        axisLabel: {
                          rotate: isMobile ? (currentData.labels.length > 6 ? 45 : 0) : (currentData.labels.length > 10 ? 45 : 0),
                          fontSize: isMobile ? 9 : 11,
                          interval: isMobile ? 'auto' : 0,
                          margin: isMobile ? 8 : 10
                        }
                      },
                      yAxis: {
                        type: 'value',
                        name: 'Amount ($)',
                        nameGap: isMobile ? 50 : 40,
                        nameLocation: 'middle',
                        nameTextStyle: {
                          padding: [0, 0, 0, 0]
                        },
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
                        top: isMobile ? 'bottom' : 10,
                        bottom: isMobile ? 0 : 'auto',
                        orient: 'horizontal',
                        type: isMobile ? 'scroll' : 'plain',
                        textStyle: {
                          fontSize: isMobile ? 10 : 12
                        },
                        itemGap: isMobile ? 8 : 20,
                        itemWidth: isMobile ? 12 : 25,
                        itemHeight: isMobile ? 8 : 14
                      },
                      grid: {
                        left: isMobile ? '15%' : '10%',
                        right: isMobile ? '4%' : '4%',
                        bottom: isMobile ? (currentData.labels.length > 10 ? '25%' : '20%') : '3%',
                        top: isMobile ? '8%' : '15%',
                        containLabel: true
                      },
                      xAxis: {
                        type: 'category',
                        data: currentData.labels,
                        axisLabel: {
                          rotate: isMobile ? (currentData.labels.length > 6 ? 45 : 0) : (currentData.labels.length > 10 ? 45 : 0),
                          fontSize: isMobile ? 9 : 11,
                          interval: isMobile ? 'auto' : 0,
                          margin: isMobile ? 8 : 10
                        }
                      },
                      yAxis: {
                        type: 'value',
                        name: 'Amount ($)',
                        nameGap: isMobile ? 50 : 40,
                        nameLocation: 'middle',
                        nameTextStyle: {
                          padding: [0, 0, 0, 0]
                        },
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
                      data: ['Fuel', 'Tolls', 'Dispatch Fee', 'Deductions', 'Insurance', 'Safety', 'Prepass', 'IFTA', 'Truck Parking'],
                      top: isMobile ? 'bottom' : 10,
                      bottom: isMobile ? 0 : 'auto',
                      type: 'scroll',
                      orient: 'horizontal',
                      textStyle: {
                        fontSize: isMobile ? 10 : 12
                      },
                      itemGap: isMobile ? 8 : 20,
                      itemWidth: isMobile ? 12 : 25,
                      itemHeight: isMobile ? 8 : 14
                    },
                    grid: {
                      left: isMobile ? '15%' : '10%',
                      right: isMobile ? '4%' : '4%',
                      bottom: isMobile ? (currentData.labels.length > 10 ? '30%' : '25%') : '15%',
                      top: isMobile ? '8%' : '20%',
                      containLabel: true
                    },
                    xAxis: {
                      type: 'category',
                      data: currentData.labels,
                      axisLabel: {
                        rotate: isMobile ? (currentData.labels.length > 6 ? 45 : 0) : (currentData.labels.length > 10 ? 45 : 0),
                        fontSize: isMobile ? 9 : 11,
                        interval: isMobile ? 'auto' : 0,
                        margin: isMobile ? 8 : 10
                      }
                    },
                    yAxis: {
                      type: 'value',
                      name: 'Amount ($)',
                      nameGap: isMobile ? 50 : 40,
                      nameLocation: 'middle',
                      nameTextStyle: {
                        padding: [0, 0, 0, 0]
                      },
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
                            name: 'Tolls',
                            type: 'line',
                            smooth: true,
                            data: currentData.expenses?.tolls || [],
                            itemStyle: { color: '#14b8a6' }
                          },
                          {
                            name: 'Dispatch Fee',
                            type: 'line',
                            smooth: true,
                            data: currentData.expenses?.dispatch_fee || [],
                            itemStyle: { color: '#f59e0b' }
                          },
                          {
                            name: 'Deductions',
                            type: 'line',
                            smooth: true,
                            data: currentData.expenses?.deduct || [],
                            itemStyle: { color: '#6366f1' }
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
