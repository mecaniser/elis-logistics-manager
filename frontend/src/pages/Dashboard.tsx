import { useEffect, useState } from 'react'
import { analyticsApi, trucksApi, Truck } from '../services/api'
import ReactECharts from 'echarts-for-react'

export default function Dashboard() {
  const [data, setData] = useState<any>(null)
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [selectedTruck, setSelectedTruck] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTrucks()
    loadDashboard()
  }, [selectedTruck])

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
  ].filter(item => item.value > 0) : []

  const truckProfitsData = data.truck_profits || []
  const blocksByTruckMonth = data.blocks_by_truck_month || []
  const repairsByMonth = data.repairs_by_month || []

  // Identify months with PM (preventive maintenance) repairs by truck
  const getPMMonthsByTruck = () => {
    const pmMonths: { [truckId: number]: Set<string> } = {}
    
    repairsByMonth.forEach(repair => {
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
    blocksByTruckMonth.forEach(item => {
      monthSet.add(item.month_key)
    })
    const months = Array.from(monthSet).sort()
    
    // Get all unique trucks
    const truckSet = new Set<number>()
    blocksByTruckMonth.forEach(item => {
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
          d => d.truck_id === truckId && d.month_key === monthKey
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
      const monthData = blocksByTruckMonth.filter(d => d.month_key === monthKey)
      if (monthData.length === 0) return 0
      const totalBlocks = monthData.reduce((sum, d) => sum + d.blocks, 0)
      const avgBlocks = totalBlocks / monthData.length
      return Math.round(avgBlocks * 100) / 100 // Round to 2 decimal places
    })
    
    // Format month labels
    const monthLabels = months.map(monthKey => {
      const item = blocksByTruckMonth.find(d => d.month_key === monthKey)
      return item ? item.month : monthKey
    })
    
    return { months: monthLabels, series, averageLine }
  }

  const blocksChartData = processBlocksData()
  const pmStatus = data.pm_status || []

  // Filter PM status by selected truck if applicable
  const filteredPMStatus = selectedTruck 
    ? pmStatus.filter(pm => pm.truck_id === selectedTruck)
    : pmStatus

  // Separate trucks due vs not due
  const trucksDueForPM = filteredPMStatus.filter(pm => pm.is_due)
  const trucksNotDueForPM = filteredPMStatus.filter(pm => !pm.is_due)

  return (
    <div>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-0 mb-4 sm:mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Dashboard</h1>
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
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {expenseCategoriesData.length > 0 && (
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Expenses by Category</h2>
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
                  }
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
            />
          </div>
        )}

        {truckProfitsData.length > 0 && (
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Profit by Truck</h2>
            <ReactECharts
              option={{
                tooltip: {
                  trigger: 'axis',
                  axisPointer: {
                    type: 'shadow'
                  },
                  formatter: (params: any) => {
                    const value = params[0]?.value || 0
                    return `${params[0]?.name}<br/>$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
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
                  bottom: '3%',
                  containLabel: true
                },
                xAxis: {
                  type: 'category',
                  data: truckProfitsData.map(item => item.truck_name),
                  axisLabel: {
                    rotate: truckProfitsData.length > 5 ? 45 : 0,
                    fontSize: 11
                  }
                },
                yAxis: {
                  type: 'value',
                  axisLabel: {
                    formatter: (value: number) => `$${value.toLocaleString()}`
                  }
                },
                series: [
                  {
                    name: 'Net Profit',
                    type: 'bar',
                    data: truckProfitsData.map(item => item.net_profit),
                    itemStyle: {
                      color: (params: any) => {
                        return params.value >= 0 ? '#10b981' : '#ef4444'
                      },
                      borderRadius: [4, 4, 0, 0]
                    },
                    label: {
                      show: true,
                      position: 'top',
                      formatter: (params: any) => {
                        const value = params.value || 0
                        return `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
                      },
                      fontSize: 10
                    }
                  }
                ]
              }}
              style={{ height: '400px', width: '100%' }}
              opts={{ renderer: 'svg' }}
            />
          </div>
        )}
      </div>

      {repairsByMonth.length > 0 && (() => {
        // Group repairs by month
        const repairsByMonthGrouped: { [key: string]: any[] } = {}
        repairsByMonth.forEach(repair => {
          if (!repairsByMonthGrouped[repair.month_key]) {
            repairsByMonthGrouped[repair.month_key] = []
          }
          repairsByMonthGrouped[repair.month_key].push(repair)
        })
        
        // Get unique months sorted
        const uniqueMonths = Array.from(new Set(repairsByMonth.map(r => r.month_key))).sort()
        
        // Create x-axis categories: each repair gets its own position, grouped by month
        const xAxisData: string[] = []
        const repairData: number[] = []
        const repairTooltips: string[] = []
        const repairColors: string[] = []
        
        uniqueMonths.forEach(monthKey => {
          const repairsInMonth = repairsByMonthGrouped[monthKey] || []
          const firstRepair = repairsInMonth[0]
          const monthLabel = firstRepair ? firstRepair.month : monthKey
          
          repairsInMonth.forEach((repair, idx) => {
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
                    blocksChartData.months.forEach((monthLabel, index) => {
                      // Extract month_key from month label or use index
                      const monthKey = blocksByTruckMonth.find(
                        d => d.month === monthLabel && d.truck_name === series.name
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

      {/* Net Profit vs Repair Costs Chart */}
      {truckProfitsData.length > 0 && (
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">Net Profit vs Repair Costs by Truck</h2>
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
                    const value = param.value || 0
                    const formatted = `$${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                    result += `${param.marker}${param.seriesName}: ${formatted}<br/>`
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
                data: ['Net Profit', 'Repair Costs'],
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
                data: truckProfitsData.map(t => t.truck_name),
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
                  name: 'Net Profit',
                  type: 'bar',
                  data: truckProfitsData.map(t => t.net_profit),
                  itemStyle: {
                    color: (params: any) => {
                      return params.value >= 0 ? '#10b981' : '#ef4444'
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
                      return params.value >= 0 ? '#10b981' : '#ef4444'
                    }
                  }
                },
                {
                  name: 'Repair Costs',
                  type: 'bar',
                  data: truckProfitsData.map(t => t.repair_costs || 0),
                  itemStyle: {
                    color: '#f97316',
                    borderRadius: [4, 4, 0, 0]
                  },
                  label: {
                    show: true,
                    position: 'top',
                    formatter: (params: any) => {
                      const value = params.value || 0
                      return value > 0 ? `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : ''
                    },
                    fontSize: 9,
                    color: '#f97316'
                  }
                }
              ]
            }}
            style={{ height: '450px', width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
        </div>
      )}
    </div>
  )
}
