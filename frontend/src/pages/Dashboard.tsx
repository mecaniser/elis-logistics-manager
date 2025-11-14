import { useEffect, useState } from 'react'
import { analyticsApi, trucksApi, Truck } from '../services/api'
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'

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
          <div className="bg-white p-4 sm:p-6 rounded-lg shadow">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Expenses by Category</h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={expenseCategoriesData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {expenseCategoriesData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {truckProfitsData.length > 0 && (
          <div className="bg-white p-4 sm:p-6 rounded-lg shadow">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Profit by Truck</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={truckProfitsData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="truck_name" />
                <YAxis />
                <Tooltip formatter={(value: number) => `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                <Bar dataKey="net_profit" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
