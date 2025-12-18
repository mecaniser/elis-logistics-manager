import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { analyticsApi, trucksApi, repairsApi, Truck, VehicleROI, Repair } from '../services/api'
import Toast from '../components/Toast'
import { useMobile } from '../utils/useMobile'
import { useTenant } from '../contexts/TenantContext'

// Helper function to safely format numbers (handles null/undefined)
const safeToLocaleString = (value: number | null | undefined, options?: Intl.NumberFormatOptions): string => {
  if (value == null || isNaN(value)) return '0.00'
  return value.toLocaleString(undefined, options || { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function VehicleDetail() {
  const isMobile = useMobile()
  const { currentTenant } = useTenant()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [vehicle, setVehicle] = useState<Truck | null>(null)
  const [roiData, setRoiData] = useState<VehicleROI | null>(null)
  const [repairs, setRepairs] = useState<Repair[]>([])
  const [loading, setLoading] = useState(true)
  const [investmentExpanded, setInvestmentExpanded] = useState(!isMobile)
  const [vehicleInfoExpanded, setVehicleInfoExpanded] = useState(!isMobile)
  const [depreciationExpanded, setDepreciationExpanded] = useState(true)
  const [repairsExpanded, setRepairsExpanded] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean }>({
    message: '',
    type: 'info',
    isVisible: false
  })

  useEffect(() => {
    if (id) {
      setVehicle(null)
      setRoiData(null)
      loadVehicleData()
    }
  }, [id, currentTenant?.id])

  const loadVehicleData = async () => {
    if (!id) return
    
    try {
      setLoading(true)
      const [vehicleResponse, roiResponse, repairsResponse] = await Promise.all([
        trucksApi.getById(parseInt(id)),
        analyticsApi.getVehicleROI(parseInt(id)),
        repairsApi.getAll(parseInt(id))
      ])
      setVehicle(vehicleResponse.data)
      setRoiData(roiResponse.data)
      setRepairs(repairsResponse.data || [])
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

  // Use cash recovery metrics for Investment Recovery section
  const cashRecoveryPercentage = roiData.cash_recovery_percentage ?? 0
  const cashRecoveryAmount = roiData.cash_recovery_amount ?? 0
  const isCashRecovered = roiData.cash_recovery_achieved ?? false
  const remainingToCashRecovery = roiData.remaining_to_cash_recovery ?? 0

  return (
    <div>
      <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
        <button
          onClick={() => navigate('/trucks')}
          className={`${isMobile ? 'px-3 py-2' : 'px-4 py-2'} border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors flex items-center gap-2 flex-shrink-0`}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          {isMobile ? (
            <span className="text-sm">Back</span>
          ) : (
            <span>Back to Vehicles</span>
          )}
        </button>
        <button
          onClick={() => setVehicleInfoExpanded(!vehicleInfoExpanded)}
          className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-900 hover:text-gray-700 transition-colors flex items-center gap-2 cursor-pointer"
          title="Click to view vehicle details"
        >
          {vehicle.name} - {vehicle.vehicle_type === 'truck' ? 'Truck' : vehicle.vehicle_type === 'suv' ? 'SUV' : 'Trailer'}
          <svg
            className="w-4 h-4 text-gray-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <svg
            className={`w-5 h-5 text-gray-500 transition-transform ${vehicleInfoExpanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Vehicle Information */}
      {vehicleInfoExpanded && (
        <div className="flex flex-wrap gap-3 sm:gap-4 mb-4 sm:mb-6">
        {vehicle.vin && (
          <div className="bg-white shadow rounded-lg p-3 sm:p-4 flex-[2] min-w-[140px] flex items-center gap-2">
            <span className="text-xs font-medium text-gray-600">VIN:</span>
            <span className="text-xs text-gray-900 font-medium break-words">{vehicle.vin}</span>
          </div>
        )}
        {(vehicle.vehicle_type === 'truck' || vehicle.vehicle_type === 'suv') && vehicle.license_plate && (
          <div className="bg-white shadow rounded-lg p-3 sm:p-4 flex-1 min-w-[120px] flex items-center gap-2">
            <span className="text-xs font-medium text-gray-600">Plate:</span>
            <span className="text-xs text-gray-900 font-medium break-words">{vehicle.license_plate}</span>
          </div>
        )}
        {vehicle.vehicle_type === 'trailer' && vehicle.tag_number && (
          <div className="bg-white shadow rounded-lg p-3 sm:p-4 flex-1 min-w-[120px] flex items-center gap-2">
            <span className="text-xs font-medium text-gray-600">Tag Number:</span>
            <span className="text-xs text-gray-900 font-medium break-words">{vehicle.tag_number}</span>
          </div>
        )}
        </div>
      )}

      {/* ROI Metrics - Only for trucks and trailers (revenue-generating vehicles) */}
      {vehicle.vehicle_type !== 'suv' && roiData.cash_investment && roiData.cash_investment > 0 && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-900">ROI Metrics</h2>
          
          {/* Cumulative Net Profit */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-medium text-gray-600">Cumulative Net Profit</span>
              <span className={`text-2xl font-bold ${
                roiData.cumulative_net_profit >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                ${safeToLocaleString(roiData.cumulative_net_profit)}
              </span>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Revenue</span>
                <span className="text-sm font-semibold text-gray-900">
                  ${safeToLocaleString(roiData.cumulative_revenue)}
                </span>
              </div>
              <div className="border-t border-gray-200 pt-2">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-gray-600">Total Expenses</span>
                  <span className="text-sm font-semibold text-red-600">
                    ${safeToLocaleString((roiData.cumulative_settlement_expenses || 0) + (roiData.cumulative_repair_costs || 0) + (roiData.cumulative_loan_interest || 0))}
                  </span>
                </div>
                <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-3'} gap-2 mt-2 pl-2 border-l-2 border-gray-200`}>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Settlement</span>
                    <span className="text-xs font-medium text-gray-700">
                      ${safeToLocaleString(roiData.cumulative_settlement_expenses)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Repairs</span>
                    <span className="text-xs font-medium text-gray-700">
                      ${safeToLocaleString(roiData.cumulative_repair_costs)}
                    </span>
                  </div>
                  {roiData.cumulative_loan_interest > 0 && (
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-gray-500">Interest</span>
                      <span className="text-xs font-medium text-gray-700">
                        ${safeToLocaleString(roiData.cumulative_loan_interest)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Investment Recovery */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-600">Investment Recovery</span>
              <span className={`text-2xl font-bold ${
                isCashRecovered ? 'text-green-600' : 'text-blue-600'
              }`}>
                {cashRecoveryPercentage.toFixed(2)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-4 mb-2">
              <div
                className={`h-4 rounded-full transition-all ${
                  isCashRecovered ? 'bg-green-600' : 'bg-blue-600'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, cashRecoveryPercentage))}%` }}
              />
            </div>
            <div className="text-xs text-gray-500">
              {isCashRecovered ? (
                <span className="text-green-600 font-medium">✓ Cash investment fully recovered!</span>
              ) : (
                <span>Recovered ${safeToLocaleString(cashRecoveryAmount)} of ${safeToLocaleString(roiData.cash_investment)}</span>
              )}
            </div>
          </div>

          {/* Remaining to Cash Recovery */}
          {!isCashRecovered && roiData.cash_investment && roiData.cash_investment > 0 && (
            <div className="mb-4">
              <span className="text-sm font-medium text-gray-600">Remaining to Cash Recovery</span>
              <p className="text-xl font-semibold text-orange-600 mt-1">
                ${safeToLocaleString(remainingToCashRecovery)}
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
                  ${safeToLocaleString(roiData.current_loan_balance)}
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
                      <span className="font-medium">${safeToLocaleString((roiData.loan_amount || 0) - (roiData.current_loan_balance || 0))}</span>
                    ) : null}
                    {roiData.current_loan_balance < roiData.loan_amount && (
                      <span> paid of ${safeToLocaleString(roiData.loan_amount)} total</span>
                    )}
                  </div>
                </>
              )}
              {roiData.current_loan_balance === 0 && (
                <div className="text-xs text-green-600 font-medium">
                  ✓ Loan fully paid off
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* SUV Expense Tracking - Only for SUVs */}
      {vehicle.vehicle_type === 'suv' && (
        <>
          {/* Depreciation Summary */}
          <div className="bg-white shadow rounded-lg p-4 sm:p-6 mb-6">
            <button
              onClick={() => setDepreciationExpanded(!depreciationExpanded)}
              className="w-full flex items-center justify-between mb-2"
            >
              <h2 className="text-base sm:text-lg font-semibold text-gray-900">Depreciation & Tax Write-off</h2>
              <svg
                className={`w-5 h-5 text-gray-600 transition-transform ${depreciationExpanded ? 'transform rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {depreciationExpanded && (
              <div className="space-y-4">
                {/* Method & Purchase Info */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <span className="text-xs font-medium text-gray-600">Method</span>
                    <p className="text-sm font-semibold text-gray-900 mt-1">
                      {vehicle.depreciation_method === 'MACRS_5' ? 'MACRS 5-Year' : 
                       vehicle.depreciation_method === 'straight_line' ? 'Straight-Line' : 'None'}
                    </p>
                  </div>
                  {vehicle.purchase_date && (
                    <div className="bg-gray-50 rounded-lg p-3">
                      <span className="text-xs font-medium text-gray-600">Purchase Date</span>
                      <p className="text-sm font-semibold text-gray-900 mt-1">
                        {new Date(vehicle.purchase_date).toLocaleDateString()}
                      </p>
                    </div>
                  )}
                  <div className="bg-gray-50 rounded-lg p-3">
                    <span className="text-xs font-medium text-gray-600">Total Cost</span>
                    <p className="text-sm font-semibold text-gray-900 mt-1">
                      ${safeToLocaleString(vehicle.total_cost)}
                    </p>
                  </div>
                </div>

                {/* Deductions */}
                <div className="border-t pt-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">First-Year Deductions</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                    {vehicle.section_179_deduction && parseFloat(vehicle.section_179_deduction.toString()) > 0 && (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                        <span className="text-xs font-medium text-green-700">Section 179</span>
                        <p className="text-lg font-bold text-green-700 mt-1">
                          ${safeToLocaleString(vehicle.section_179_deduction)}
                        </p>
                      </div>
                    )}
                    {vehicle.bonus_depreciation && parseFloat(vehicle.bonus_depreciation.toString()) > 0 && (
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                        <span className="text-xs font-medium text-blue-700">Bonus Depreciation</span>
                        <p className="text-lg font-bold text-blue-700 mt-1">
                          {vehicle.bonus_depreciation}%
                        </p>
                      </div>
                    )}
                    <div className="bg-gray-50 rounded-lg p-3">
                      <span className="text-xs font-medium text-gray-600">Cost Basis</span>
                      <p className="text-lg font-semibold text-gray-900 mt-1">
                        ${safeToLocaleString(vehicle.cost_basis)}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">Remaining depreciable amount</p>
                    </div>
                  </div>
                </div>

                {/* Total Deduction Summary */}
                <div className="bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-lg p-4">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-gray-700">Total Tax Deduction (First Year)</span>
                    <span className="text-xl font-bold text-green-700">
                      ${safeToLocaleString(
                        (vehicle.section_179_deduction ? parseFloat(vehicle.section_179_deduction.toString()) : 0) +
                        (vehicle.bonus_depreciation && vehicle.cost_basis 
                          ? (parseFloat(vehicle.bonus_depreciation.toString()) / 100) * parseFloat(vehicle.cost_basis.toString())
                          : 0)
                      )}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Repairs & Maintenance */}
          <div className="bg-white shadow rounded-lg p-4 sm:p-6 mb-6">
            <button
              onClick={() => setRepairsExpanded(!repairsExpanded)}
              className="w-full flex items-center justify-between mb-2"
            >
              <h2 className="text-base sm:text-lg font-semibold text-gray-900">
                Operating Expenses
                {repairs.length > 0 && (
                  <span className="ml-2 text-sm font-normal text-gray-500">
                    ({repairs.length} repair{repairs.length !== 1 ? 's' : ''})
                  </span>
                )}
              </h2>
              <svg
                className={`w-5 h-5 text-gray-600 transition-transform ${repairsExpanded ? 'transform rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {repairsExpanded && (
              <div className="space-y-4">
                {/* Summary */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <span className="text-xs font-medium text-red-700">Total Repair Costs</span>
                    <p className="text-2xl font-bold text-red-700 mt-1">
                      ${safeToLocaleString(repairs.reduce((sum, r) => sum + (r.total_cost || 0), 0))}
                    </p>
                    <p className="text-xs text-red-600 mt-1">Deductible business expense</p>
                  </div>
                  <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                    <span className="text-xs font-medium text-orange-700">Registration Fee</span>
                    <p className="text-2xl font-bold text-orange-700 mt-1">
                      ${safeToLocaleString(vehicle.registration_fee)}
                    </p>
                    <p className="text-xs text-orange-600 mt-1">Annual deductible expense</p>
                  </div>
                </div>

                {/* Repair List */}
                {repairs.length > 0 ? (
                  <div className="border-t pt-4">
                    <h3 className="text-sm font-medium text-gray-700 mb-3">Repair History</h3>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {repairs.map((repair) => (
                        <div key={repair.id} className="flex justify-between items-center bg-gray-50 rounded-lg p-3">
                          <div>
                            <p className="text-sm font-medium text-gray-900">{repair.description}</p>
                            <p className="text-xs text-gray-500">
                              {repair.repair_date ? new Date(repair.repair_date).toLocaleDateString() : 'No date'}
                              {repair.vendor && ` • ${repair.vendor}`}
                            </p>
                          </div>
                          <span className="text-sm font-semibold text-red-600">
                            ${safeToLocaleString(repair.total_cost)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-6 text-gray-500">
                    <p>No repairs recorded yet</p>
                    <button
                      onClick={() => navigate('/repairs')}
                      className="mt-2 text-sm text-blue-600 hover:text-blue-800"
                    >
                      Add a repair →
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* Investment Information */}
      {(roiData.cash_investment || roiData.total_cost || vehicle.registration_fee) && (
        <div className="bg-white shadow rounded-lg p-4 sm:p-6 mb-6">
          <button
            onClick={() => setInvestmentExpanded(!investmentExpanded)}
            className="w-full flex items-center justify-between mb-2"
          >
            <h2 className="text-base sm:text-lg font-semibold text-gray-900">Investment Information</h2>
            <svg
              className={`w-5 h-5 text-gray-600 transition-transform ${investmentExpanded ? 'transform rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {investmentExpanded && (
            <div className="space-y-2 sm:space-y-0 sm:grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 sm:gap-4 sm:items-start">
              {/* Cash Investment */}
              <div className={`flex flex-col ${isMobile ? 'bg-gray-50 rounded-lg p-3' : ''}`}>
                <span className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Cash Investment</span>
                <p className={`${isMobile ? 'text-base' : 'text-xl'} font-semibold text-gray-900`}>
                  ${safeToLocaleString(roiData.cash_investment)}
                </p>
              </div>
              
              {/* Loan Information - Only for trucks */}
              {vehicle.vehicle_type === 'truck' && roiData.loan_amount && (
                <>
                  <div className={`flex flex-col ${isMobile ? 'bg-gray-50 rounded-lg p-3' : ''}`}>
                    <span className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Original Loan</span>
                    <p className={`${isMobile ? 'text-base' : 'text-xl'} font-semibold text-gray-900`}>
                      ${safeToLocaleString(roiData.loan_amount)}
                    </p>
                  </div>
                  
                  {roiData.current_loan_balance !== null && roiData.current_loan_balance !== undefined && (
                    <div className={`flex flex-col ${isMobile ? 'bg-gray-50 rounded-lg p-3' : ''}`}>
                      <span className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Remaining Balance</span>
                      <p className={`${isMobile ? 'text-base' : 'text-xl'} font-semibold ${
                        roiData.current_loan_balance === 0 ? 'text-green-600' : 
                        roiData.current_loan_balance < roiData.loan_amount ? 'text-orange-600' : 
                        'text-gray-900'
                      }`}>
                        ${safeToLocaleString(roiData.current_loan_balance)}
                      </p>
                      {roiData.current_loan_balance < roiData.loan_amount && roiData.current_loan_balance > 0 && (
                        <p className="text-xs text-gray-500 mt-1">
                          ${safeToLocaleString((roiData.loan_amount || 0) - (roiData.current_loan_balance || 0))} principal paid
                        </p>
                      )}
                      {roiData.current_loan_balance === 0 && (
                        <p className="text-xs text-green-600 font-medium mt-1">✓ Loan fully paid off!</p>
                      )}
                    </div>
                  )}
                  
                  <div className={`flex flex-col ${isMobile ? 'bg-gray-50 rounded-lg p-3' : ''}`}>
                    <span className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Interest Rate</span>
                    <p className={`${isMobile ? 'text-base' : 'text-xl'} font-semibold text-gray-900`}>
                      {(roiData.interest_rate * 100).toFixed(2)}%
                    </p>
                  </div>
                </>
              )}
              
              {/* Registration Fee */}
              <div className={`flex flex-col ${isMobile ? 'bg-gray-50 rounded-lg p-3' : ''}`}>
                <span className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Registration Fee</span>
                <p className={`${isMobile ? 'text-base' : 'text-xl'} font-semibold text-gray-900`}>
                  ${safeToLocaleString(vehicle.registration_fee)}
                </p>
              </div>
              
              {/* Total Cost - Highlighted on mobile */}
              <div className={`flex flex-col ${isMobile ? 'bg-blue-50 border-2 border-blue-200 rounded-lg p-3' : ''}`}>
                <span className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Total Cost</span>
                <p className={`${isMobile ? 'text-base' : 'text-xl'} font-bold ${isMobile ? 'text-blue-700' : 'text-gray-900'}`}>
                  ${safeToLocaleString(roiData.total_cost)}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      <Toast
        message={toast.message}
        type={toast.type}
        isVisible={toast.isVisible}
        onClose={() => setToast({ ...toast, isVisible: false })}
      />
    </div>
  )
}

