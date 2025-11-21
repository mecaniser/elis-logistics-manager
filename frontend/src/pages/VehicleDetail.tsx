import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { analyticsApi, trucksApi, Truck, VehicleROI } from '../services/api'
import Toast from '../components/Toast'

export default function VehicleDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [vehicle, setVehicle] = useState<Truck | null>(null)
  const [roiData, setRoiData] = useState<VehicleROI | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean }>({
    message: '',
    type: 'info',
    isVisible: false
  })

  useEffect(() => {
    if (id) {
      loadVehicleData()
    }
  }, [id])

  const loadVehicleData = async () => {
    if (!id) return
    
    try {
      setLoading(true)
      const [vehicleResponse, roiResponse] = await Promise.all([
        trucksApi.getById(parseInt(id)),
        analyticsApi.getVehicleROI(parseInt(id))
      ])
      setVehicle(vehicleResponse.data)
      setRoiData(roiResponse.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load vehicle data')
      showToast('Failed to load vehicle data', 'error')
    } finally {
      setLoading(false)
    }
  }

  const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info') => {
    setToast({ message, type, isVisible: true })
  }

  if (loading) return <div className="text-center py-8">Loading vehicle details...</div>
  if (error || !vehicle || !roiData) {
    return (
      <div className="text-center py-8">
        <p className="text-red-600 mb-4">{error || 'Vehicle not found'}</p>
        <button
          onClick={() => navigate('/trucks')}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Back to Vehicles
        </button>
      </div>
    )
  }

  const recoveryPercentage = roiData.investment_recovery_percentage ?? 0
  const isBreakEven = roiData.break_even_achieved
  const remaining = roiData.remaining_to_break_even ?? 0

  return (
    <div>
      <div className="mb-6">
        <button
          onClick={() => navigate('/trucks')}
          className="text-blue-600 hover:text-blue-800 mb-4 flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Vehicles
        </button>
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
          {vehicle.name} - {vehicle.vehicle_type === 'truck' ? 'Truck' : 'Trailer'}
        </h1>
      </div>

      {/* Vehicle Information */}
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-900">Vehicle Information</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {vehicle.vin && (
            <div>
              <span className="text-sm font-medium text-gray-600">VIN:</span>
              <span className="ml-2 text-sm text-gray-900">{vehicle.vin}</span>
            </div>
          )}
          {vehicle.vehicle_type === 'truck' && vehicle.license_plate && (
            <div>
              <span className="text-sm font-medium text-gray-600">License Plate:</span>
              <span className="ml-2 text-sm text-gray-900">{vehicle.license_plate}</span>
            </div>
          )}
          {vehicle.vehicle_type === 'trailer' && vehicle.tag_number && (
            <div>
              <span className="text-sm font-medium text-gray-600">Tag Number:</span>
              <span className="ml-2 text-sm text-gray-900">{vehicle.tag_number}</span>
            </div>
          )}
        </div>
      </div>

      {/* Investment Information */}
      {(roiData.cash_investment || roiData.total_cost || vehicle.registration_fee) && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-900">Investment Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            <div>
              <span className="text-sm font-medium text-gray-600">Cash Investment</span>
              <p className="text-xl font-semibold text-gray-900 mt-1">
                ${roiData.cash_investment?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
              </p>
            </div>
            {vehicle.vehicle_type === 'truck' && roiData.loan_amount && (
              <>
                <div>
                  <span className="text-sm font-medium text-gray-600">Original Loan Amount</span>
                  <p className="text-xl font-semibold text-gray-900 mt-1">
                    ${roiData.loan_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
                {roiData.current_loan_balance !== null && roiData.current_loan_balance !== undefined && (
                  <div>
                    <span className="text-sm font-medium text-gray-600">Remaining Loan Balance</span>
                    <p className={`text-xl font-semibold mt-1 ${
                      roiData.current_loan_balance === 0 ? 'text-green-600' : 
                      roiData.current_loan_balance < roiData.loan_amount ? 'text-orange-600' : 
                      'text-gray-900'
                    }`}>
                      ${roiData.current_loan_balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                    {roiData.current_loan_balance < roiData.loan_amount && roiData.current_loan_balance > 0 && (
                      <p className="text-xs text-gray-500 mt-1">
                        ${(roiData.loan_amount - roiData.current_loan_balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} principal paid
                      </p>
                    )}
                    {roiData.current_loan_balance === 0 && (
                      <p className="text-xs text-green-600 font-medium mt-1">✓ Loan fully paid off!</p>
                    )}
                  </div>
                )}
                <div>
                  <span className="text-sm font-medium text-gray-600">Interest Rate</span>
                  <p className="text-xl font-semibold text-gray-900 mt-1">
                    {(roiData.interest_rate * 100).toFixed(2)}%
                  </p>
                </div>
              </>
            )}
            <div>
              <span className="text-sm font-medium text-gray-600">Registration Fee</span>
              <p className="text-xl font-semibold text-gray-900 mt-1">
                ${vehicle.registration_fee?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
              </p>
            </div>
            <div>
              <span className="text-sm font-medium text-gray-600">Total Cost</span>
              <p className="text-xl font-semibold text-gray-900 mt-1">
                ${roiData.total_cost?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ROI Metrics */}
      {roiData.cash_investment && roiData.cash_investment > 0 && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-900">ROI Metrics</h2>
          
          {/* Cumulative Net Profit */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-600">Cumulative Net Profit</span>
              <span className={`text-2xl font-bold ${
                roiData.cumulative_net_profit >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                ${roiData.cumulative_net_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="text-xs text-gray-500">
              Revenue: ${roiData.cumulative_revenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} - 
              Expenses: ${(roiData.cumulative_settlement_expenses + roiData.cumulative_repair_costs + roiData.cumulative_loan_interest).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              {roiData.cumulative_loan_interest > 0 && (
                <span> (Settlement: ${roiData.cumulative_settlement_expenses.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} | Repairs: ${roiData.cumulative_repair_costs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} | Interest: ${roiData.cumulative_loan_interest.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })})</span>
              )}
            </div>
          </div>

          {/* Investment Recovery */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-600">Investment Recovery</span>
              <span className={`text-2xl font-bold ${
                isBreakEven ? 'text-green-600' : 'text-blue-600'
              }`}>
                {recoveryPercentage.toFixed(2)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-4 mb-2">
              <div
                className={`h-4 rounded-full transition-all ${
                  isBreakEven ? 'bg-green-600' : 'bg-blue-600'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, recoveryPercentage))}%` }}
              />
            </div>
            <div className="text-xs text-gray-500">
              {isBreakEven ? (
                <span className="text-green-600 font-medium">✓ Break-even achieved!</span>
              ) : (
                <span>Recovered ${roiData.cumulative_net_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} of ${roiData.cash_investment.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              )}
            </div>
          </div>

          {/* Remaining to Break-Even */}
          {!isBreakEven && (
            <div className="mb-4">
              <span className="text-sm font-medium text-gray-600">Remaining to Break-Even</span>
              <p className="text-xl font-semibold text-orange-600 mt-1">
                ${remaining.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          )}

          {/* Loan Balance After Cash Recovery */}
          {vehicle.vehicle_type === 'truck' && roiData.loan_amount && roiData.current_loan_balance !== null && roiData.current_loan_balance !== undefined && (
            <div className={`mt-4 p-4 rounded-lg ${
              roiData.current_loan_balance === 0 ? 'bg-green-50 border-2 border-green-200' :
              roiData.current_loan_balance < roiData.loan_amount ? 'bg-orange-50 border-2 border-orange-200' :
              'bg-gray-50 border-2 border-gray-200'
            }`}>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium text-gray-700">Loan Balance After Cash Recovery</span>
                <span className={`text-2xl font-bold ${
                  roiData.current_loan_balance === 0 ? 'text-green-600' :
                  roiData.current_loan_balance < roiData.loan_amount ? 'text-orange-600' :
                  'text-gray-900'
                }`}>
                  ${roiData.current_loan_balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              {roiData.current_loan_balance > 0 && (
                <>
                  <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
                    <div
                      className={`h-3 rounded-full transition-all ${
                        roiData.current_loan_balance === 0 ? 'bg-green-600' :
                        roiData.current_loan_balance < roiData.loan_amount ? 'bg-orange-600' :
                        'bg-gray-400'
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, ((roiData.loan_amount - roiData.current_loan_balance) / roiData.loan_amount) * 100))}%` }}
                    />
                  </div>
                  <div className="text-xs text-gray-600">
                    {roiData.current_loan_balance < roiData.loan_amount ? (
                      <>
                        <span className="font-medium">${(roiData.loan_amount - roiData.current_loan_balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span> principal paid of ${roiData.loan_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} total
                        <br />
                        <span className="text-gray-500">Principal payments start after cash investment is 100% recovered</span>
                      </>
                    ) : (
                      <span className="text-gray-500">Cash investment not yet recovered - no principal payments applied</span>
                    )}
                  </div>
                </>
              )}
              {roiData.current_loan_balance === 0 && (
                <div className="text-xs text-green-600 font-medium">
                  ✓ Loan fully paid off! All excess profit after cash recovery was applied to principal.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Financial Summary */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-900">Financial Summary</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-blue-50 p-4 rounded-lg">
            <div className="text-sm font-medium text-gray-600">Total Revenue</div>
            <div className="text-2xl font-bold text-blue-600 mt-1">
              ${roiData.cumulative_revenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
          <div className="bg-red-50 p-4 rounded-lg">
            <div className="text-sm font-medium text-gray-600">Total Expenses</div>
            <div className="text-2xl font-bold text-red-600 mt-1">
              ${(roiData.cumulative_settlement_expenses + roiData.cumulative_repair_costs + roiData.cumulative_loan_interest).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Settlement: ${roiData.cumulative_settlement_expenses.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} | 
              Repairs: ${roiData.cumulative_repair_costs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              {roiData.cumulative_loan_interest > 0 && (
                <span> | Interest: ${roiData.cumulative_loan_interest.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              )}
            </div>
          </div>
          <div className={`p-4 rounded-lg ${
            roiData.cumulative_net_profit >= 0 ? 'bg-green-50' : 'bg-red-50'
          }`}>
            <div className="text-sm font-medium text-gray-600">Net Profit</div>
            <div className={`text-2xl font-bold mt-1 ${
              roiData.cumulative_net_profit >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              ${roiData.cumulative_net_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
        </div>
      </div>

      <Toast
        message={toast.message}
        type={toast.type}
        isVisible={toast.isVisible}
        onClose={() => setToast({ ...toast, isVisible: false })}
      />
    </div>
  )
}

