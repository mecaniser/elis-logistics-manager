import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { trucksApi, analyticsApi, Truck, PMStatus } from '../services/api'
import Toast from '../components/Toast'
import ConfirmModal from '../components/ConfirmModal'
import { useMobile } from '../utils/useMobile'
import { useTenant } from '../contexts/TenantContext'

export default function Trucks() {
  const isMobile = useMobile()
  const { currentTenant } = useTenant()
  const navigate = useNavigate()
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [pmStatus, setPmStatus] = useState<PMStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingTruck, setEditingTruck] = useState<Truck | null>(null)
  const [vehicleTypeFilter, setVehicleTypeFilter] = useState<'all' | 'truck' | 'trailer' | 'suv'>('all')
  const [formData, setFormData] = useState({ 
    name: '', 
    vehicle_type: 'truck' as 'truck' | 'trailer' | 'suv',
    vin: '', 
    license_plate: '',
    tag_number: '',
    cash_investment: '',
    loan_amount: '',
    interest_rate: '0.07',
    total_cost: '',
    registration_fee: '',
    purchase_date: '',
    depreciation_method: 'MACRS_5' as 'MACRS_5' | 'straight_line' | 'none',
    cost_basis: '',
    section_179_deduction: '',
    bonus_depreciation: ''
  })
  const [truckToDelete, setTruckToDelete] = useState<number | null>(null)
  const [truckToDeleteName, setTruckToDeleteName] = useState<string>('')
  const [expandedPMStatus, setExpandedPMStatus] = useState<Set<number>>(new Set())
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean }>({
    message: '',
    type: 'info',
    isVisible: false
  })

  useEffect(() => {
    // Reset state when tenant changes
    setTrucks([])
    setPmStatus([])
    loadTrucks()
    loadPMStatus()
  }, [vehicleTypeFilter, currentTenant?.id])

  const loadPMStatus = async () => {
    try {
      const response = await analyticsApi.getPMStatus()
      setPmStatus(response.data.pm_status || [])
    } catch (err) {
      // Silently fail - PM status is not critical
      console.error('Failed to load PM status:', err)
      setPmStatus([])
    }
  }

  // Auto-calculate total cost when investment fields change
  useEffect(() => {
    const cash = parseFloat(formData.cash_investment) || 0
    const loan = (formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') ? (parseFloat(formData.loan_amount) || 0) : 0
    const registration = parseFloat(formData.registration_fee) || 0
    const total = cash + loan + registration
    
    if (total > 0) {
      setFormData(prev => ({ ...prev, total_cost: total.toFixed(2) }))
    } else {
      setFormData(prev => ({ ...prev, total_cost: '' }))
    }
  }, [formData.cash_investment, formData.loan_amount, formData.registration_fee, formData.vehicle_type])

  // Auto-calculate cost basis when total cost or deductions change
  useEffect(() => {
    const totalCost = parseFloat(formData.total_cost) || 0
    const section179 = parseFloat(formData.section_179_deduction) || 0
    const bonusPct = parseFloat(formData.bonus_depreciation) || 0
    
    if (totalCost > 0) {
      const remainingAfter179 = totalCost - section179
      const bonusAmount = remainingAfter179 * (bonusPct / 100)
      const costBasis = totalCost - section179 - bonusAmount
      
      // Only auto-calculate if cost_basis is empty (user hasn't manually set it)
      if (!formData.cost_basis && costBasis > 0) {
        setFormData(prev => ({ ...prev, cost_basis: Math.max(0, costBasis).toFixed(2) }))
      }
    }
  }, [formData.total_cost, formData.section_179_deduction, formData.bonus_depreciation])

  const loadTrucks = async () => {
    try {
      setLoading(true)
      const response = await trucksApi.getAll(
        vehicleTypeFilter !== 'all' ? vehicleTypeFilter : undefined
      )
      setTrucks(Array.isArray(response.data) ? response.data : [])
    } catch (err: any) {
      setError(err.message || 'Failed to load vehicles')
      setTrucks([])
    } finally {
      setLoading(false)
    }
  }

  const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info') => {
    setToast({ message, type, isVisible: true })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const vehicleLabel = formData.vehicle_type === 'truck' ? 'Truck' : formData.vehicle_type === 'suv' ? 'SUV' : 'Trailer'
      
      const investmentData: any = {}
      if (formData.cash_investment) {
        investmentData.cash_investment = parseFloat(formData.cash_investment)
      }
      if ((formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') && formData.loan_amount) {
        investmentData.loan_amount = parseFloat(formData.loan_amount)
      } else if (formData.vehicle_type === 'trailer') {
        investmentData.loan_amount = null
      }
      if (formData.total_cost) {
        investmentData.total_cost = parseFloat(formData.total_cost)
      }
      if (formData.registration_fee) {
        investmentData.registration_fee = parseFloat(formData.registration_fee)
      }
      // Handle interest_rate - can be cleared (empty string) or set to a value
      if (formData.interest_rate === '') {
        investmentData.interest_rate = undefined  // Clear/delete interest rate
      } else if (formData.interest_rate) {
        investmentData.interest_rate = parseFloat(formData.interest_rate)
      }
      
      // Depreciation fields
      if (formData.purchase_date) {
        investmentData.purchase_date = formData.purchase_date
      }
      if (formData.depreciation_method) {
        investmentData.depreciation_method = formData.depreciation_method
      }
      if (formData.cost_basis) {
        investmentData.cost_basis = parseFloat(formData.cost_basis)
      }
      if (formData.section_179_deduction) {
        investmentData.section_179_deduction = parseFloat(formData.section_179_deduction)
      }
      if (formData.bonus_depreciation) {
        investmentData.bonus_depreciation = parseFloat(formData.bonus_depreciation)
      }

      if (editingTruck) {
        await trucksApi.update(editingTruck.id, {
          name: formData.name,
          vehicle_type: formData.vehicle_type,
          vin: formData.vin || undefined,
          license_plate: (formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') ? (formData.license_plate || undefined) : undefined,
          tag_number: formData.vehicle_type === 'trailer' ? (formData.tag_number || undefined) : undefined,
          ...investmentData
        })
        showToast(`${vehicleLabel} updated successfully!`, 'success')
      } else {
        await trucksApi.create({
          name: formData.name,
          vehicle_type: formData.vehicle_type,
          vin: formData.vin || undefined,
          license_plate: (formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') ? (formData.license_plate || undefined) : undefined,
          tag_number: formData.vehicle_type === 'trailer' ? (formData.tag_number || undefined) : undefined,
          ...investmentData
        })
        showToast(`${vehicleLabel} created successfully!`, 'success')
      }
      setShowForm(false)
      setEditingTruck(null)
      resetForm()
      loadTrucks()
    } catch (err: any) {
      const vehicleLabel = formData.vehicle_type === 'truck' ? 'truck' : 'trailer'
      showToast(err.response?.data?.detail || err.message || `Failed to save ${vehicleLabel}`, 'error')
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      vehicle_type: 'truck',
      vin: '',
      license_plate: '',
      tag_number: '',
      cash_investment: '',
      loan_amount: '',
      interest_rate: '0.07',
      total_cost: '',
      registration_fee: '',
      purchase_date: '',
      depreciation_method: 'MACRS_5',
      cost_basis: '',
      section_179_deduction: '',
      bonus_depreciation: ''
    })
  }

  const handleDelete = async () => {
    if (!truckToDelete) return
    try {
      await trucksApi.delete(truckToDelete)
      showToast(`Vehicle "${truckToDeleteName}" deleted successfully!`, 'success')
      setTruckToDelete(null)
      setTruckToDeleteName('')
      loadTrucks()
    } catch (err: any) {
      showToast(err.response?.data?.detail || err.message || 'Failed to delete vehicle', 'error')
      setTruckToDelete(null)
      setTruckToDeleteName('')
    }
  }

  const filteredTrucks = trucks.filter(truck => {
    if (vehicleTypeFilter === 'all') return true
    return truck.vehicle_type === vehicleTypeFilter
  })

  const trucksList = filteredTrucks.filter(t => t.vehicle_type === 'truck')
  const trailersList = filteredTrucks.filter(t => t.vehicle_type === 'trailer')
  const suvsList = filteredTrucks.filter(t => t.vehicle_type === 'suv')

  // Calculate total investments
  const totalTrucksInvestment = trucksList.reduce((sum, truck) => {
    const total = truck.total_cost || 
      ((truck.cash_investment || 0) + (truck.loan_amount || 0) + (truck.registration_fee || 0))
    return sum + total
  }, 0)

  const totalSuvsInvestment = suvsList.reduce((sum, suv) => {
    const total = suv.total_cost || 
      ((suv.cash_investment || 0) + (suv.loan_amount || 0) + (suv.registration_fee || 0))
    return sum + total
  }, 0)
  
  const totalTrailersInvestment = trailersList.reduce((sum, trailer) => {
    const total = trailer.total_cost || 
      ((trailer.cash_investment || 0) + (trailer.registration_fee || 0))
    return sum + total
  }, 0)

  if (loading) return <div className="text-center py-8">Loading vehicles...</div>
  if (error) return <div className="text-center py-8 text-red-600">{error}</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Vehicles</h1>
        <button
          onClick={() => {
            setEditingTruck(null)
            resetForm()
            setShowForm(true)
          }}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Add Vehicle
        </button>
      </div>

      {/* Total Investments Display */}
      {(totalTrucksInvestment > 0 || totalTrailersInvestment > 0 || totalSuvsInvestment > 0) && (
        <div className="mb-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {totalTrucksInvestment > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="text-sm font-medium text-gray-600 mb-1">
                {trucksList.length === 1 ? 'Total Vehicle Investment' : `Total Vehicles Investment (${trucksList.length})`}
              </div>
              <div className="text-2xl font-bold text-blue-700">
                ${totalTrucksInvestment.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
          )}
          {totalSuvsInvestment > 0 && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="text-sm font-medium text-gray-600 mb-1">
                {suvsList.length === 1 ? 'Total SUV Investment' : `Total SUVs Investment (${suvsList.length})`}
              </div>
              <div className="text-2xl font-bold text-green-700">
                ${totalSuvsInvestment.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
          )}
          {totalTrailersInvestment > 0 && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <div className="text-sm font-medium text-gray-600 mb-1">
                {trailersList.length === 1 ? 'Total Trailer Investment' : `Total Trailers Investment (${trailersList.length})`}
              </div>
              <div className="text-2xl font-bold text-purple-700">
                ${totalTrailersInvestment.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Filter */}
      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setVehicleTypeFilter('all')}
          className={`px-4 py-2 rounded-md ${
            vehicleTypeFilter === 'all'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          All
        </button>
        <button
          onClick={() => setVehicleTypeFilter('truck')}
          className={`px-4 py-2 rounded-md ${
            vehicleTypeFilter === 'truck'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          Vehicles
        </button>
        <button
          onClick={() => setVehicleTypeFilter('suv')}
          className={`px-4 py-2 rounded-md ${
            vehicleTypeFilter === 'suv'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          SUVs
        </button>
        <button
          onClick={() => setVehicleTypeFilter('trailer')}
          className={`px-4 py-2 rounded-md ${
            vehicleTypeFilter === 'trailer'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          Trailers
        </button>
      </div>

      {showForm && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            {editingTruck ? `Edit ${editingTruck.vehicle_type === 'truck' ? 'Truck' : editingTruck.vehicle_type === 'suv' ? 'SUV' : 'Trailer'}` : 'Add Vehicle'}
          </h2>
          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Vehicle Type *</label>
              <select
                value={formData.vehicle_type}
                onChange={(e) => {
                  const newType = e.target.value as 'truck' | 'trailer' | 'suv'
                  setFormData({ 
                    ...formData, 
                    vehicle_type: newType,
                    license_plate: newType === 'trailer' ? '' : formData.license_plate,
                    tag_number: (newType === 'truck' || newType === 'suv') ? '' : formData.tag_number
                  })
                }}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="truck">Truck</option>
                <option value="suv">SUV</option>
                <option value="trailer">Trailer</option>
              </select>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {(formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">License Plate</label>
                <input
                  type="text"
                  value={formData.license_plate}
                  onChange={(e) => setFormData({ ...formData, license_plate: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
            {formData.vehicle_type === 'trailer' && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Tag Number</label>
                <input
                  type="text"
                  value={formData.tag_number}
                  onChange={(e) => setFormData({ ...formData, tag_number: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">VIN</label>
              <input
                type="text"
                value={formData.vin}
                onChange={(e) => setFormData({ ...formData, vin: e.target.value })}
                placeholder="Enter 17-character VIN"
                maxLength={17}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            {/* Investment Fields */}
            <div className="mb-4 border-t pt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Investment Information</h3>
              <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                <div className="md:col-span-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Cash Investment ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.cash_investment}
                    onChange={(e) => setFormData({ ...formData, cash_investment: e.target.value })}
                    placeholder="0.00"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                {(formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') && (
                  <>
                    <div className="md:col-span-3">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Loan Amount ($)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.loan_amount}
                        onChange={(e) => setFormData({ ...formData, loan_amount: e.target.value })}
                        placeholder="0.00"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div className="md:col-span-3">
                      <div className="flex items-center justify-between mb-1">
                        <label className="block text-sm font-medium text-gray-700">Interest Rate (%)</label>
                        {formData.interest_rate && formData.interest_rate !== '' && formData.interest_rate !== '0.07' && (
                          <button
                            type="button"
                            onClick={() => setFormData({ ...formData, interest_rate: '' })}
                            className="text-xs text-red-600 hover:text-red-800"
                            title="Clear interest rate"
                          >
                            Clear
                          </button>
                        )}
                      </div>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="100"
                        value={formData.interest_rate ? (parseFloat(formData.interest_rate) * 100).toFixed(2) : ''}
                        onChange={(e) => {
                          const value = e.target.value
                          if (value === '') {
                            setFormData({ ...formData, interest_rate: '' })
                          } else {
                            const percentValue = parseFloat(value) || 0
                            const decimalValue = (percentValue / 100).toFixed(4)
                            setFormData({ ...formData, interest_rate: decimalValue })
                          }
                        }}
                        placeholder="7.00"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                      <p className="text-xs text-gray-500 mt-1">Annual interest rate (e.g., 7.00 for 7%). Leave empty to remove.</p>
                    </div>
                  </>
                )}
                <div className={formData.vehicle_type === 'truck' ? 'md:col-span-3' : 'md:col-span-6'}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Total Cost ($)</label>
                  <input
                    type="text"
                    value={formData.total_cost}
                    readOnly
                    placeholder="Auto-calculated"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-700 cursor-not-allowed"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    {formData.vehicle_type === 'truck' 
                      ? 'Cash + Loan + Registration'
                      : 'Cash + Registration'}
                  </p>
                </div>
                <div className={formData.vehicle_type === 'truck' ? 'md:col-span-3' : 'md:col-span-6'}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Registration Fee ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.registration_fee}
                    onChange={(e) => setFormData({ ...formData, registration_fee: e.target.value })}
                    placeholder="0.00"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            </div>
            
            {/* Depreciation Fields */}
            <div className="mb-4 border-t pt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Depreciation Settings</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Purchase Date</label>
                  <input
                    type="date"
                    value={formData.purchase_date}
                    onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Date vehicle was purchased/placed in service</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Depreciation Method</label>
                  <select
                    value={formData.depreciation_method}
                    onChange={(e) => setFormData({ ...formData, depreciation_method: e.target.value as 'MACRS_5' | 'straight_line' | 'none' })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="MACRS_5">MACRS 5-Year (IRS Standard)</option>
                    <option value="straight_line">Straight-Line</option>
                    <option value="none">None</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">Method for calculating depreciation</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Cost Basis ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.cost_basis}
                    onChange={(e) => setFormData({ ...formData, cost_basis: e.target.value })}
                    placeholder="Auto-calculated from total cost"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Depreciable amount (total cost - Section 179 - bonus depreciation)</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Section 179 Deduction ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.section_179_deduction}
                    onChange={(e) => setFormData({ ...formData, section_179_deduction: e.target.value })}
                    placeholder="0.00"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">First-year Section 179 deduction (if applicable)</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Bonus Depreciation (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.bonus_depreciation}
                    onChange={(e) => setFormData({ ...formData, bonus_depreciation: e.target.value })}
                    placeholder="0.00"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Bonus depreciation percentage (e.g., 100 for 100%)</p>
                </div>
              </div>
            </div>
            
            <div className="flex gap-3">
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                {editingTruck ? 'Update' : 'Create'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false)
                  setEditingTruck(null)
                  resetForm()
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Trucks Section */}
      {vehicleTypeFilter !== 'trailer' && trucksList.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-3 text-gray-900">Vehicles</h2>
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {trucksList.map((truck) => (
                <li key={truck.id} className="px-6 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">{truck.name}</h3>
                      {truck.vin && <p className="text-sm text-gray-500">VIN: {truck.vin}</p>}
                      {truck.license_plate && (
                        <p className="text-sm text-gray-500">License Plate: {truck.license_plate}</p>
                      )}
                      {/* Hide license plate history on mobile */}
                      {!isMobile && truck.license_plate_history && truck.license_plate_history.length > 0 && (
                        <p className="text-xs text-gray-400">
                          History: {truck.license_plate_history.join(', ')}
                        </p>
                      )}
                      {/* Hide investment details on mobile */}
                      {!isMobile && (truck.cash_investment || truck.total_cost || truck.registration_fee) && (
                        <div className="mt-2 text-xs text-gray-600">
                          <span className="font-medium">Investment: </span>
                          {truck.cash_investment && (
                            <span>Cash: ${truck.cash_investment.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          )}
                          {truck.loan_amount && truck.loan_amount > 0 && (
                            <span className="ml-2">Loan: ${truck.loan_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          )}
                          {truck.registration_fee && (
                            <span className="ml-2">Registration: ${truck.registration_fee.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          )}
                          {truck.total_cost && (
                            <span className="ml-2">Total: ${truck.total_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          )}
                        </div>
                      )}
                      {/* PM Status - Expandable on mobile */}
                      {(() => {
                        const truckPM = pmStatus.find(pm => pm.truck_id === truck.id)
                        if (!truckPM) return null
                        const isExpanded = expandedPMStatus.has(truck.id)
                        return (
                          <div className={`mt-2 text-xs ${truckPM.is_due ? 'text-red-700' : 'text-green-700'}`}>
                            {isMobile ? (
                              // Mobile: Clickable indicator with expandable details
                              <div>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setExpandedPMStatus(prev => {
                                      const newSet = new Set(prev)
                                      if (newSet.has(truck.id)) {
                                        newSet.delete(truck.id)
                                      } else {
                                        newSet.add(truck.id)
                                      }
                                      return newSet
                                    })
                                  }}
                                  className="flex items-center gap-1 hover:opacity-80 transition-opacity"
                                >
                                  <span>{truckPM.is_due ? '⚠️ PM Due' : '✓ PM OK'}</span>
                                  <svg
                                    className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                  >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                  </svg>
                                </button>
                                {isExpanded && (
                                  <div className="mt-2 pl-4 border-l-2 border-gray-300 space-y-1">
                                    {truckPM.is_due ? (
                                      <>
                                        {truckPM.pm_method === 'mileage' && truckPM.miles_overdue !== null && (
                                          <div className="text-red-600">
                                            {(truckPM.miles_overdue || 0).toLocaleString()} miles overdue
                                          </div>
                                        )}
                                        {truckPM.pm_method === 'time' && truckPM.days_overdue !== null && (
                                          <div className="text-red-600">
                                            {truckPM.days_overdue} days overdue
                                          </div>
                                        )}
                                        {!truckPM.last_pm_date && (
                                          <div className="text-gray-600">No PM recorded</div>
                                        )}
                                        {truckPM.last_pm_date && (
                                          <div className="text-gray-600">
                                            Last PM: {new Date(truckPM.last_pm_date).toLocaleDateString()}
                                          </div>
                                        )}
                                        {truckPM.last_pm_miles !== null && (
                                          <div className="text-gray-600">
                                            Last PM Miles: {(truckPM.last_pm_miles || 0).toLocaleString()}
                                          </div>
                                        )}
                                        {truckPM.current_miles !== null && (
                                          <div className="text-gray-600">
                                            Current Miles: {(truckPM.current_miles || 0).toLocaleString()}
                                          </div>
                                        )}
                                        {truckPM.next_pm_miles !== null && (
                                          <div className="text-gray-500 text-xs">
                                            Next PM Due: {(truckPM.next_pm_miles || 0).toLocaleString()} miles
                                          </div>
                                        )}
                                        {truckPM.pm_method === 'mileage' && (
                                          <div className="text-gray-500 text-xs">
                                            Threshold: {(truckPM.pm_threshold_miles || 0).toLocaleString()} miles
                                          </div>
                                        )}
                                        {truckPM.pm_method === 'time' && (
                                          <div className="text-gray-500 text-xs">
                                            Threshold: {truckPM.pm_threshold_days} days ({Math.round(truckPM.pm_threshold_days / 7)} weeks)
                                          </div>
                                        )}
                                      </>
                                    ) : (
                                      <>
                                        {truckPM.last_pm_date && (
                                          <div className="text-gray-600">
                                            Last PM: {new Date(truckPM.last_pm_date).toLocaleDateString()}
                                          </div>
                                        )}
                                        {truckPM.last_pm_miles !== null && (
                                          <div className="text-gray-600">
                                            Last PM Miles: {(truckPM.last_pm_miles || 0).toLocaleString()}
                                          </div>
                                        )}
                                        {truckPM.current_miles !== null && (
                                          <div className="text-gray-600">
                                            Current Miles: {(truckPM.current_miles || 0).toLocaleString()}
                                          </div>
                                        )}
                                        {truckPM.pm_method === 'mileage' && truckPM.miles_until_due !== null && (
                                          <div className="text-gray-600">
                                            {(truckPM.miles_until_due || 0).toLocaleString()} miles until due
                                          </div>
                                        )}
                                        {truckPM.pm_method === 'time' && truckPM.days_until_due !== null && (
                                          <div className="text-gray-600">
                                            {truckPM.days_until_due} days until due
                                          </div>
                                        )}
                                        {truckPM.pm_method === 'mileage' && (
                                          <div className="text-gray-500 text-xs">
                                            Threshold: {(truckPM.pm_threshold_miles || 0).toLocaleString()} miles
                                          </div>
                                        )}
                                        {truckPM.pm_method === 'time' && (
                                          <div className="text-gray-500 text-xs">
                                            Threshold: {truckPM.pm_threshold_days} days ({Math.round(truckPM.pm_threshold_days / 7)} weeks)
                                          </div>
                                        )}
                                      </>
                                    )}
                                  </div>
                                )}
                              </div>
                            ) : (
                              // Desktop: Full details
                              <>
                                {truckPM.is_due ? (
                                  <span>
                                    ⚠️ PM Due
                                    {truckPM.pm_method === 'mileage' && truckPM.miles_overdue !== null && (
                                      <span> ({truckPM.miles_overdue.toLocaleString()} miles overdue)</span>
                                    )}
                                    {truckPM.pm_method === 'time' && truckPM.days_overdue !== null && (
                                      <span> ({truckPM.days_overdue} days overdue)</span>
                                    )}
                                    {!truckPM.last_pm_date && <span> (No PM recorded)</span>}
                                    {truckPM.last_pm_date && (
                                      <span className="text-gray-600"> • Last PM: {new Date(truckPM.last_pm_date).toLocaleDateString()}</span>
                                    )}
                                    {truckPM.last_pm_miles !== null && (
                                      <span className="text-gray-600"> • Miles: {truckPM.last_pm_miles.toLocaleString()}</span>
                                    )}
                                    {truckPM.current_miles !== null && (
                                      <span className="text-gray-600"> • Current: {truckPM.current_miles.toLocaleString()}</span>
                                    )}
                                  </span>
                                ) : (
                                  <span>
                                    ✓ PM Up to Date
                                    {truckPM.last_pm_date && (
                                      <span className="text-gray-600"> • Last PM: {new Date(truckPM.last_pm_date).toLocaleDateString()}</span>
                                    )}
                                    {truckPM.pm_method === 'mileage' && truckPM.miles_until_due !== null && (
                                      <span className="text-gray-600"> • {truckPM.miles_until_due.toLocaleString()} miles until due</span>
                                    )}
                                    {truckPM.pm_method === 'time' && truckPM.days_until_due !== null && (
                                      <span className="text-gray-600"> • {truckPM.days_until_due} days until due</span>
                                    )}
                                    {truckPM.last_pm_miles !== null && (
                                      <span className="text-gray-600"> • Miles: {truckPM.last_pm_miles.toLocaleString()}</span>
                                    )}
                                  </span>
                                )}
                              </>
                            )}
                          </div>
                        )
                      })()}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigate(`/vehicles/${truck.id}`)}
                        className={`${isMobile ? 'p-2' : 'px-3 py-1.5'} border border-green-600 text-green-600 rounded-md hover:bg-green-50 transition-colors flex items-center justify-center`}
                        title="View Details"
                      >
                        {isMobile ? (
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        ) : (
                          'View Details'
                        )}
                      </button>
                      <button
                        onClick={() => {
                          setEditingTruck(truck)
                          setFormData({ 
                            name: truck.name, 
                            vehicle_type: truck.vehicle_type,
                            vin: truck.vin || '', 
                            license_plate: truck.license_plate || '',
                            tag_number: truck.tag_number || '',
                            cash_investment: truck.cash_investment?.toString() || '',
                            loan_amount: truck.loan_amount?.toString() || '',
                            interest_rate: truck.interest_rate?.toString() || '0.07',
                            total_cost: truck.total_cost?.toString() || '',
                            registration_fee: truck.registration_fee?.toString() || '',
                            purchase_date: truck.purchase_date ? new Date(truck.purchase_date).toISOString().split('T')[0] : '',
                            depreciation_method: (truck.depreciation_method || 'MACRS_5') as 'MACRS_5' | 'straight_line' | 'none',
                            cost_basis: truck.cost_basis?.toString() || '',
                            section_179_deduction: truck.section_179_deduction?.toString() || '',
                            bonus_depreciation: truck.bonus_depreciation?.toString() || ''
                          })
                          setShowForm(true)
                        }}
                        className={`${isMobile ? 'p-2' : 'px-3 py-1.5'} border border-blue-600 text-blue-600 rounded-md hover:bg-blue-50 transition-colors flex items-center justify-center`}
                        title="Edit"
                      >
                        {isMobile ? (
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        ) : (
                          'Edit'
                        )}
                      </button>
                      <button
                        onClick={() => {
                          setTruckToDelete(truck.id)
                          setTruckToDeleteName(truck.name)
                        }}
                        className={`${isMobile ? 'p-2' : 'px-3 py-1.5'} border border-red-600 text-red-600 rounded-md hover:bg-red-50 transition-colors flex items-center justify-center`}
                        title="Delete"
                      >
                        {isMobile ? (
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        ) : (
                          'Delete'
                        )}
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* SUVs Section */}
      {vehicleTypeFilter !== 'truck' && vehicleTypeFilter !== 'trailer' && suvsList.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-3 text-gray-900">SUVs</h2>
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {suvsList.map((suv) => (
                <li key={suv.id} className="px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {suv.name}
                        </p>
                        {suv.license_plate && (
                          <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            {suv.license_plate}
                          </span>
                        )}
                      </div>
                      <div className="mt-1 flex items-center text-sm text-gray-500">
                        {suv.total_cost && (
                          <span className="mr-4">
                            Total Cost: ${parseFloat(suv.total_cost.toString()).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        )}
                        {suv.purchase_date && (
                          <span>
                            Purchased: {new Date(suv.purchase_date).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className={`flex ${isMobile ? 'flex-col' : ''} gap-2 ml-4`}>
                      <button
                        onClick={() => {
                          setEditingTruck(suv)
                          setFormData({ 
                            name: suv.name,
                            vehicle_type: suv.vehicle_type,
                            vin: suv.vin || '',
                            license_plate: suv.license_plate || '',
                            tag_number: '',
                            cash_investment: suv.cash_investment?.toString() || '',
                            loan_amount: suv.loan_amount?.toString() || '',
                            interest_rate: suv.interest_rate?.toString() || '0.07',
                            total_cost: suv.total_cost?.toString() || '',
                            registration_fee: suv.registration_fee?.toString() || '',
                            purchase_date: suv.purchase_date || '',
                            depreciation_method: (suv.depreciation_method || 'MACRS_5') as 'MACRS_5' | 'straight_line' | 'none',
                            cost_basis: suv.cost_basis?.toString() || '',
                            section_179_deduction: suv.section_179_deduction?.toString() || '',
                            bonus_depreciation: suv.bonus_depreciation?.toString() || '',
                          })
                          setShowForm(true)
                        }}
                        className={`${isMobile ? 'p-2' : 'px-3 py-1.5'} border border-blue-600 text-blue-600 rounded-md hover:bg-blue-50 transition-colors flex items-center justify-center`}
                        title="Edit"
                      >
                        {isMobile ? (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        ) : (
                          'Edit'
                        )}
                      </button>
                      <button
                        onClick={() => {
                          setTruckToDelete(suv.id)
                          setTruckToDeleteName(suv.name)
                        }}
                        className={`${isMobile ? 'p-2' : 'px-3 py-1.5'} border border-red-600 text-red-600 rounded-md hover:bg-red-50 transition-colors flex items-center justify-center`}
                        title="Delete"
                      >
                        {isMobile ? (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        ) : (
                          'Delete'
                        )}
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Trailers Section */}
      {vehicleTypeFilter !== 'truck' && vehicleTypeFilter !== 'suv' && trailersList.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-3 text-gray-900">Trailers</h2>
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {trailersList.map((trailer) => (
                <li key={trailer.id} className="px-6 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">{trailer.name}</h3>
                      {trailer.vin && <p className="text-sm text-gray-500">VIN: {trailer.vin}</p>}
                      {trailer.tag_number && (
                        <p className="text-sm text-gray-500">Tag Number: {trailer.tag_number}</p>
                      )}
                      {/* Hide investment details on mobile */}
                      {!isMobile && (trailer.cash_investment || trailer.total_cost || trailer.registration_fee) && (
                        <div className="mt-2 text-xs text-gray-600">
                          <span className="font-medium">Investment: </span>
                          {trailer.cash_investment && (
                            <span>Cash: ${trailer.cash_investment.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          )}
                          {trailer.registration_fee && (
                            <span className="ml-2">Registration: ${trailer.registration_fee.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          )}
                          {trailer.total_cost && (
                            <span className="ml-2">Total: ${trailer.total_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigate(`/vehicles/${trailer.id}`)}
                        className={`${isMobile ? 'p-2' : 'px-3 py-1.5'} border border-green-600 text-green-600 rounded-md hover:bg-green-50 transition-colors flex items-center justify-center`}
                        title="View Details"
                      >
                        {isMobile ? (
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        ) : (
                          'View Details'
                        )}
                      </button>
                      <button
                        onClick={() => {
                          setEditingTruck(trailer)
                          setFormData({ 
                            name: trailer.name, 
                            vehicle_type: trailer.vehicle_type,
                            vin: trailer.vin || '', 
                            license_plate: trailer.license_plate || '',
                            tag_number: trailer.tag_number || '',
                            cash_investment: trailer.cash_investment?.toString() || '',
                            loan_amount: trailer.loan_amount?.toString() || '',
                            interest_rate: trailer.interest_rate?.toString() || '0.07',
                            total_cost: trailer.total_cost?.toString() || '',
                            registration_fee: trailer.registration_fee?.toString() || '',
                            purchase_date: trailer.purchase_date ? new Date(trailer.purchase_date).toISOString().split('T')[0] : '',
                            depreciation_method: (trailer.depreciation_method || 'MACRS_5') as 'MACRS_5' | 'straight_line' | 'none',
                            cost_basis: trailer.cost_basis?.toString() || '',
                            section_179_deduction: trailer.section_179_deduction?.toString() || '',
                            bonus_depreciation: trailer.bonus_depreciation?.toString() || ''
                          })
                          setShowForm(true)
                        }}
                        className={`${isMobile ? 'p-2' : 'px-3 py-1.5'} border border-blue-600 text-blue-600 rounded-md hover:bg-blue-50 transition-colors flex items-center justify-center`}
                        title="Edit"
                      >
                        {isMobile ? (
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        ) : (
                          'Edit'
                        )}
                      </button>
                      <button
                        onClick={() => {
                          setTruckToDelete(trailer.id)
                          setTruckToDeleteName(trailer.name)
                        }}
                        className={`${isMobile ? 'p-2' : 'px-3 py-1.5'} border border-red-600 text-red-600 rounded-md hover:bg-red-50 transition-colors flex items-center justify-center`}
                        title="Delete"
                      >
                        {isMobile ? (
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        ) : (
                          'Delete'
                        )}
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Empty State */}
      {filteredTrucks.length === 0 && (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <div className="px-6 py-4 text-gray-500 text-center">
            No {vehicleTypeFilter === 'all' ? 'vehicles' : vehicleTypeFilter === 'truck' ? 'trucks' : vehicleTypeFilter === 'suv' ? 'SUVs' : 'trailers'} found.
          </div>
        </div>
      )}

      <Toast
        message={toast.message}
        type={toast.type}
        isVisible={toast.isVisible}
        onClose={() => setToast({ ...toast, isVisible: false })}
      />

      <ConfirmModal
        isOpen={truckToDelete !== null}
        onClose={() => {
          setTruckToDelete(null)
          setTruckToDeleteName('')
        }}
        onConfirm={handleDelete}
        title="Delete Vehicle"
        message={truckToDeleteName ? `Are you sure you want to delete "${truckToDeleteName}"? This action cannot be undone and will also delete all associated repairs and settlements.` : "Are you sure you want to delete this vehicle? This action cannot be undone."}
        confirmText="Delete"
        type="danger"
      />
    </div>
  )
}
