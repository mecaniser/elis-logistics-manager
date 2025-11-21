import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { trucksApi, Truck } from '../services/api'
import Toast from '../components/Toast'
import ConfirmModal from '../components/ConfirmModal'

export default function Trucks() {
  const navigate = useNavigate()
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingTruck, setEditingTruck] = useState<Truck | null>(null)
  const [vehicleTypeFilter, setVehicleTypeFilter] = useState<'all' | 'truck' | 'trailer'>('all')
  const [formData, setFormData] = useState({ 
    name: '', 
    vehicle_type: 'truck' as 'truck' | 'trailer',
    vin: '', 
    license_plate: '',
    tag_number: '',
    cash_investment: '',
    loan_amount: '',
    interest_rate: '0.07',
    total_cost: '',
    registration_fee: ''
  })
  const [truckToDelete, setTruckToDelete] = useState<number | null>(null)
  const [truckToDeleteName, setTruckToDeleteName] = useState<string>('')
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean }>({
    message: '',
    type: 'info',
    isVisible: false
  })

  useEffect(() => {
    loadTrucks()
  }, [vehicleTypeFilter])

  // Auto-calculate total cost when investment fields change
  useEffect(() => {
    const cash = parseFloat(formData.cash_investment) || 0
    const loan = formData.vehicle_type === 'truck' ? (parseFloat(formData.loan_amount) || 0) : 0
    const registration = parseFloat(formData.registration_fee) || 0
    const total = cash + loan + registration
    
    if (total > 0) {
      setFormData(prev => ({ ...prev, total_cost: total.toFixed(2) }))
    } else {
      setFormData(prev => ({ ...prev, total_cost: '' }))
    }
  }, [formData.cash_investment, formData.loan_amount, formData.registration_fee, formData.vehicle_type])

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
      const vehicleLabel = formData.vehicle_type === 'truck' ? 'Truck' : 'Trailer'
      
      const investmentData: any = {}
      if (formData.cash_investment) {
        investmentData.cash_investment = parseFloat(formData.cash_investment)
      }
      if (formData.vehicle_type === 'truck' && formData.loan_amount) {
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

      if (editingTruck) {
        await trucksApi.update(editingTruck.id, {
          name: formData.name,
          vehicle_type: formData.vehicle_type,
          vin: formData.vin || undefined,
          license_plate: formData.vehicle_type === 'truck' ? (formData.license_plate || undefined) : undefined,
          tag_number: formData.vehicle_type === 'trailer' ? (formData.tag_number || undefined) : undefined,
          ...investmentData
        })
        showToast(`${vehicleLabel} updated successfully!`, 'success')
      } else {
        await trucksApi.create({
          name: formData.name,
          vehicle_type: formData.vehicle_type,
          vin: formData.vin || undefined,
          license_plate: formData.vehicle_type === 'truck' ? (formData.license_plate || undefined) : undefined,
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
      registration_fee: ''
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

  // Calculate total investments
  const totalTrucksInvestment = trucksList.reduce((sum, truck) => {
    const total = truck.total_cost || 
      ((truck.cash_investment || 0) + (truck.loan_amount || 0) + (truck.registration_fee || 0))
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
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Trucks & Trailers</h1>
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
      {(totalTrucksInvestment > 0 || totalTrailersInvestment > 0) && (
        <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {totalTrucksInvestment > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="text-sm font-medium text-gray-600 mb-1">
                {trucksList.length === 1 ? 'Total Truck Investment' : `Total Trucks Investment (${trucksList.length})`}
              </div>
              <div className="text-2xl font-bold text-blue-700">
                ${totalTrucksInvestment.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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
          Trucks
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
            {editingTruck ? `Edit ${editingTruck.vehicle_type === 'truck' ? 'Truck' : 'Trailer'}` : 'Add Vehicle'}
          </h2>
          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Vehicle Type *</label>
              <select
                value={formData.vehicle_type}
                onChange={(e) => {
                  const newType = e.target.value as 'truck' | 'trailer'
                  setFormData({ 
                    ...formData, 
                    vehicle_type: newType,
                    license_plate: newType === 'trailer' ? '' : formData.license_plate,
                    tag_number: newType === 'truck' ? '' : formData.tag_number
                  })
                }}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="truck">Truck</option>
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
            {formData.vehicle_type === 'truck' && (
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
                {formData.vehicle_type === 'truck' && (
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
                      <label className="block text-sm font-medium text-gray-700 mb-1">Interest Rate (%)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.interest_rate ? (parseFloat(formData.interest_rate) * 100).toFixed(2) : '7.00'}
                        onChange={(e) => {
                          const percentValue = parseFloat(e.target.value) || 0
                          const decimalValue = (percentValue / 100).toFixed(4)
                          setFormData({ ...formData, interest_rate: decimalValue })
                        }}
                        placeholder="7.00"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                      <p className="text-xs text-gray-500 mt-1">Annual interest rate (e.g., 7.00 for 7%)</p>
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
          <h2 className="text-xl font-semibold mb-3 text-gray-900">Trucks</h2>
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
                      {truck.license_plate_history && truck.license_plate_history.length > 0 && (
                        <p className="text-xs text-gray-400">
                          History: {truck.license_plate_history.join(', ')}
                        </p>
                      )}
                      {(truck.cash_investment || truck.total_cost || truck.registration_fee) && (
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
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigate(`/vehicles/${truck.id}`)}
                        className="text-green-600 hover:text-green-800"
                      >
                        View Details
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
                            registration_fee: truck.registration_fee?.toString() || ''
                          })
                          setShowForm(true)
                        }}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => {
                          setTruckToDelete(truck.id)
                          setTruckToDeleteName(truck.name)
                        }}
                        className="text-red-600 hover:text-red-800"
                      >
                        Delete
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
      {vehicleTypeFilter !== 'truck' && trailersList.length > 0 && (
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
                      {(trailer.cash_investment || trailer.total_cost || trailer.registration_fee) && (
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
                        className="text-green-600 hover:text-green-800"
                      >
                        View Details
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
                            registration_fee: trailer.registration_fee?.toString() || ''
                          })
                          setShowForm(true)
                        }}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => {
                          setTruckToDelete(trailer.id)
                          setTruckToDeleteName(trailer.name)
                        }}
                        className="text-red-600 hover:text-red-800"
                      >
                        Delete
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
            No {vehicleTypeFilter === 'all' ? 'vehicles' : vehicleTypeFilter === 'truck' ? 'trucks' : 'trailers'} found.
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
