import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { analyticsApi, trucksApi, repairsApi, settlementsApi, reserveApi, Truck, VehicleROI, Repair, Settlement, ReserveBalance } from '../services/api'
import Toast from '../components/Toast'
import { useMobile } from '../utils/useMobile'
import { useTenant } from '../contexts/TenantContext'

// Helper function to safely format numbers (handles null/undefined)
const safeToLocaleString = (value: number | null | undefined, options?: Intl.NumberFormatOptions): string => {
  if (value == null || isNaN(value)) return '0.00'
  return value.toLocaleString(undefined, options || { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Expense categories - same as in Trucks.tsx
const DEDUCTIBLE_CATEGORIES = ['fuel', 'insurance', 'registration', 'repairs', 'parking', 'car_wash', 'oil_change', 'tires', 'documentation', 'other_deductible']
const CAPITALIZE_CATEGORIES = ['acquisition'] // Added to cost basis, not expensed directly

// Helper to calculate additional expenses totals
const calculateExpenseTotals = (expenses: Array<{category?: string, description: string, amount: number}> | undefined) => {
  if (!expenses || expenses.length === 0) return { deductible: 0, nonDeductible: 0, capitalized: 0, total: 0 }
  
  let deductible = 0
  let nonDeductible = 0
  let capitalized = 0
  
  for (const exp of expenses) {
    const category = exp.category || 'other_deductible' // default to deductible if no category
    if (CAPITALIZE_CATEGORIES.includes(category)) {
      capitalized += exp.amount || 0
    } else if (DEDUCTIBLE_CATEGORIES.includes(category)) {
      deductible += exp.amount || 0
    } else {
      nonDeductible += exp.amount || 0
    }
  }
  
  return { deductible, nonDeductible, capitalized, total: deductible + nonDeductible + capitalized }
}

export default function VehicleDetail() {
  const isMobile = useMobile()
  const { currentTenant } = useTenant()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [vehicle, setVehicle] = useState<Truck | null>(null)
  const [roiData, setRoiData] = useState<VehicleROI | null>(null)
  const [attachedTrailer, setAttachedTrailer] = useState<Truck | null>(null)
  const [attachedTrailerRoi, setAttachedTrailerRoi] = useState<VehicleROI | null>(null)
  const [settlements, setSettlements] = useState<Settlement[]>([])
  const [repairs, setRepairs] = useState<Repair[]>([])
  const [reserveBalance, setReserveBalance] = useState<ReserveBalance | null>(null)
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
      setAttachedTrailer(null)
      setAttachedTrailerRoi(null)
      setSettlements([])
      setReserveBalance(null)
      loadVehicleData()
    }
  }, [id, currentTenant?.id])

  const loadVehicleData = async () => {
    if (!id) return
    
    try {
      setLoading(true)
      const vehicleId = parseInt(id)
      const vehicleResponse = await trucksApi.getById(vehicleId)
      const currentVehicle = vehicleResponse.data

      const [roiResponse, repairsResponse, settlementsResponse] = await Promise.all([
        analyticsApi.getVehicleROI(vehicleId),
        repairsApi.getAll(vehicleId),
        settlementsApi.getAll(vehicleId, 0)
      ])

      let nextAttachedTrailer: Truck | null = null
      let nextAttachedTrailerRoi: VehicleROI | null = null

      if (currentVehicle.vehicle_type === 'truck' && currentVehicle.default_trailer_id) {
        const [trailerResult, trailerRoiResult] = await Promise.allSettled([
          trucksApi.getById(currentVehicle.default_trailer_id),
          analyticsApi.getVehicleROI(currentVehicle.default_trailer_id)
        ])

        if (trailerResult.status === 'fulfilled') {
          nextAttachedTrailer = trailerResult.value.data
        }
        if (trailerRoiResult.status === 'fulfilled') {
          nextAttachedTrailerRoi = trailerRoiResult.value.data
        }
      }

      setVehicle(currentVehicle)
      setRoiData(roiResponse.data)
      setAttachedTrailer(nextAttachedTrailer)
      setAttachedTrailerRoi(nextAttachedTrailerRoi)
      setSettlements(settlementsResponse.data || [])
      setRepairs(repairsResponse.data || [])
      if (currentVehicle.vehicle_type === 'truck') {
        const reserveResponse = await reserveApi.getBalance(vehicleId)
        setReserveBalance(reserveResponse.data)
      }
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
  const showProfitComposition = vehicle.vehicle_type === 'truck' && attachedTrailerRoi !== null
  const trailerContribution = attachedTrailerRoi?.cumulative_net_profit ?? 0
  const combinedTrueNetProfit = roiData.cumulative_net_profit + trailerContribution
  const reserveDeposits = Number(reserveBalance?.deposits_total) || 0
  const reserveWithdrawals = Number(reserveBalance?.withdrawals_total) || 0
  const reserveAdjustments = Number(reserveBalance?.adjustments_total) || 0
  const reserveCushionAvailable = Number(reserveBalance?.balance) || 0
  const reserveDepositedAcrossLoadedSettlements = settlements.reduce(
    (sum, settlement) => sum + (Number(settlement.repair_reserve_amount) || 0),
    0
  )
  const displayInterestRate = (() => {
    if (vehicle.interest_rate == null || Number.isNaN(Number(vehicle.interest_rate))) {
      return roiData.interest_rate
    }
    const normalizedRate = Number(vehicle.interest_rate) > 1
      ? Number(vehicle.interest_rate) / 100
      : Number(vehicle.interest_rate)
    return normalizedRate
  })()
  const displayLoanAmount = vehicle.loan_amount ?? roiData.loan_amount ?? 0
  const showReserveSummary = vehicle.vehicle_type === 'truck' && (
    reserveDeposits > 0 ||
    reserveWithdrawals > 0 ||
    reserveAdjustments > 0 ||
    reserveCushionAvailable > 0 ||
    (vehicle.default_repair_reserve_amount || 0) > 0
  )

  return (
    <div>
      <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
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
            onClick={() => navigate(`/trucks?edit=${vehicle.id}`)}
            className={`${isMobile ? 'px-3 py-2' : 'px-4 py-2'} border border-blue-600 text-blue-600 rounded-md hover:bg-blue-50 transition-colors flex items-center gap-2 flex-shrink-0`}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            {!isMobile && <span>Edit</span>}
          </button>
        </div>
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

          {showProfitComposition && (
            <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">Profit Composition</h3>
                  <p className="text-xs text-gray-600 mt-1">
                    Truck profit stays separate from the attached trailer so you can see the pair and the combined result clearly.
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-xs font-medium text-gray-500">Combined True Net Profit</div>
                  <div className={`text-2xl font-bold ${combinedTrueNetProfit >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                    ${safeToLocaleString(combinedTrueNetProfit)}
                  </div>
                </div>
              </div>

              <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-3'} gap-3`}>
                <div className="rounded-lg bg-white p-4 border border-gray-200">
                  <div className="text-xs font-medium text-gray-500">Truck Net Profit</div>
                  <div className={`text-xl font-bold mt-1 ${roiData.cumulative_net_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ${safeToLocaleString(roiData.cumulative_net_profit)}
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    {vehicle.name} after trailer allocation and repair reserve.
                  </div>
                </div>

                <div className="rounded-lg bg-white p-4 border border-gray-200">
                  <div className="text-xs font-medium text-gray-500">Trailer Contribution</div>
                  <div className={`text-xl font-bold mt-1 ${trailerContribution >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ${safeToLocaleString(trailerContribution)}
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    {attachedTrailer?.name || 'Attached trailer'} including trailer-specific repairs and costs.
                  </div>
                </div>

                <div className="rounded-lg bg-white p-4 border border-gray-200">
                  <div className="text-xs font-medium text-gray-500">Combined True Net Profit</div>
                  <div className={`text-xl font-bold mt-1 ${combinedTrueNetProfit >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                    ${safeToLocaleString(combinedTrueNetProfit)}
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    Truck and trailer together as one earning unit.
                  </div>
                </div>
              </div>
            </div>
          )}

          {showReserveSummary && (
            <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">Repair Reserve Summary</h3>
                  <p className="text-xs text-gray-600 mt-1">
                    Ledger-backed reserve totals for this truck under the 2026 reserve regime.
                  </p>
                </div>
                {vehicle.default_repair_reserve_amount != null && vehicle.default_repair_reserve_amount > 0 && (
                  <div className="text-xs text-amber-700 font-medium">
                    Default weekly reserve: ${safeToLocaleString(vehicle.default_repair_reserve_amount)}
                  </div>
                )}
              </div>

              <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-3'} gap-3`}>
                <div className="rounded-lg bg-white p-4 border border-gray-200">
                  <div className="text-xs font-medium text-gray-500">Reserve Deposits</div>
                  <div className="text-xl font-bold mt-1 text-amber-700">
                    ${safeToLocaleString(reserveDeposits)}
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    Total deposits synced from 2026+ settlements.
                  </div>
                </div>

                <div className="rounded-lg bg-white p-4 border border-gray-200">
                  <div className="text-xs font-medium text-gray-500">Reserve Withdrawals</div>
                  <div className="text-xl font-bold mt-1 text-red-600">
                    ${safeToLocaleString(reserveWithdrawals)}
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    Repairs marked as paid from reserve reduce the balance here.
                  </div>
                </div>

                <div className="rounded-lg bg-white p-4 border border-gray-200">
                  <div className="text-xs font-medium text-gray-500">Reserve Balance</div>
                  <div className={`text-xl font-bold mt-1 ${reserveCushionAvailable >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                    ${safeToLocaleString(reserveCushionAvailable)}
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    Deposits plus manual adjustments minus withdrawals.
                  </div>
                </div>
              </div>
              <div className="mt-3 flex flex-col gap-1 text-xs text-gray-600 sm:flex-row sm:items-center sm:justify-between">
                <span>Loaded settlements on this screen contain ${safeToLocaleString(reserveDepositedAcrossLoadedSettlements)} of reserve deposits.</span>
                <span>Reserve regime starts 2026-01-01. Repairs paid from reserve show under withdrawals; adjustments are manual corrections only.</span>
              </div>
              {reserveAdjustments > 0 && (
                <div className="mt-2 text-xs text-gray-600">
                  Manual reserve adjustments recorded: ${safeToLocaleString(reserveAdjustments)}
                </div>
              )}
            </div>
          )}
          
          {/* Cumulative Net Profit */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-4">
              <span className="text-sm font-medium text-gray-600">
                {showProfitComposition ? 'Truck Cumulative Net Profit' : 'Cumulative Net Profit'}
              </span>
              <span className={`text-2xl font-bold ${
                roiData.cumulative_net_profit >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                ${safeToLocaleString(roiData.cumulative_net_profit)}
              </span>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              {showProfitComposition && (
                <div className="text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded-md px-3 py-2">
                  This truck figure excludes the trailer allocation that is tracked separately on {attachedTrailer?.name || 'the attached trailer'}.
                </div>
              )}
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
                    ${safeToLocaleString((roiData.cumulative_settlement_expenses || 0) + (roiData.cumulative_repair_costs || 0))}
                  </span>
                </div>
                <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-3'} gap-2 mt-2 pl-2 border-l-2 border-gray-200`}>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Settlement (incl. interest)</span>
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
                      <span> paid off ${safeToLocaleString(roiData.loan_amount)} total</span>
                    )}
                  </div>
                </>
              )}
              {roiData.current_loan_balance === 0 && (
                <div className="text-xs text-green-600 font-medium">
                  ✓ Loan fully paid off
                </div>
              )}
              {roiData.loan_payoff_date && (
                <div className="text-xs text-gray-600 mt-2">
                  Paid off date: <span className="font-medium">{new Date(roiData.loan_payoff_date).toLocaleDateString()}</span>
                </div>
              )}
              {roiData.current_loan_balance > 0 && roiData.projected_payoff_date && (
                <div className="mt-3 text-xs text-gray-600 space-y-1">
                  <div>
                    Projected payoff date: <span className="font-medium">{new Date(roiData.projected_payoff_date).toLocaleDateString()}</span>
                  </div>
                  {roiData.estimated_settlements_to_payoff !== null && roiData.estimated_settlements_to_payoff !== undefined && (
                    <div>
                      Estimated settlements remaining: <span className="font-medium">{roiData.estimated_settlements_to_payoff}</span>
                    </div>
                  )}
                  {roiData.average_principal_payment !== null && roiData.average_principal_payment !== undefined && (
                    <div>
                      Avg principal per settlement: <span className="font-medium">${safeToLocaleString(roiData.average_principal_payment)}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Clean Cash Return - Only show when loan is fully paid off */}
          {vehicle.vehicle_type === 'truck' && roiData.clean_cash_return !== null && roiData.clean_cash_return !== undefined && (
            <div className="mt-4 p-6 rounded-lg bg-gradient-to-br from-green-50 to-emerald-50 border-2 border-green-300 shadow-lg">
              <div className="flex justify-between items-center mb-3">
                <div className="flex items-center gap-2">
                  <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-base font-bold text-gray-800">Clean Cash Return</span>
                </div>
                <span className="text-3xl font-bold text-green-700">
                  ${safeToLocaleString(roiData.clean_cash_return)}
                </span>
              </div>
              <div className="flex items-start gap-2 text-xs text-green-700 bg-white bg-opacity-60 rounded p-3">
                <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span className="font-medium">
                  🎉 All investments recovered! This is pure profit after paying back your ${safeToLocaleString(roiData.cash_investment)} cash investment and ${safeToLocaleString(roiData.loan_amount)} loan.
                </span>
              </div>
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
                {(() => {
                  const expenseTotals = calculateExpenseTotals(vehicle.additional_expenses)
                  const section179 = vehicle.section_179_deduction ? parseFloat(vehicle.section_179_deduction.toString()) : 0
                  const bonusDepreciation = vehicle.bonus_depreciation && vehicle.cost_basis 
                    ? (parseFloat(vehicle.bonus_depreciation.toString()) / 100) * parseFloat(vehicle.cost_basis.toString())
                    : 0
                  const repairsCost = repairs.reduce((sum, r) => sum + (r.cost || 0), 0)
                  const registrationFee = vehicle.registration_fee ? parseFloat(vehicle.registration_fee.toString()) : 0
                  // Capitalized costs are included in cost basis, so they're deducted via Section 179/depreciation, not separately
                  const totalDeduction = section179 + bonusDepreciation + expenseTotals.deductible + repairsCost + registrationFee
                  
                  return (
                    <div className="bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-lg p-4">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-medium text-gray-700">Total Tax Deduction (First Year)</span>
                        <span className="text-xl font-bold text-green-700">
                          ${safeToLocaleString(totalDeduction)}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 space-y-1">
                        {section179 > 0 && <div className="flex justify-between"><span>Section 179:</span><span>${safeToLocaleString(section179)}</span></div>}
                        {bonusDepreciation > 0 && <div className="flex justify-between"><span>Bonus Depreciation:</span><span>${safeToLocaleString(bonusDepreciation)}</span></div>}
                        {expenseTotals.capitalized > 0 && <div className="flex justify-between text-blue-600"><span>Acquisition Costs (in cost basis):</span><span>${safeToLocaleString(expenseTotals.capitalized)}</span></div>}
                        {expenseTotals.deductible > 0 && <div className="flex justify-between"><span>Deductible Expenses:</span><span>${safeToLocaleString(expenseTotals.deductible)}</span></div>}
                        {repairsCost > 0 && <div className="flex justify-between"><span>Repairs:</span><span>${safeToLocaleString(repairsCost)}</span></div>}
                        {registrationFee > 0 && <div className="flex justify-between"><span>Registration:</span><span>${safeToLocaleString(registrationFee)}</span></div>}
                      </div>
                    </div>
                  )
                })()}
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
                {(() => {
                  const expenseTotals = calculateExpenseTotals(vehicle.additional_expenses)
                  return (
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <span className="text-xs font-medium text-red-700">Total Repair Costs</span>
                        <p className="text-xl font-bold text-red-700 mt-1">
                          ${safeToLocaleString(repairs.reduce((sum, r) => sum + (r.cost || 0), 0))}
                        </p>
                        <p className="text-xs text-red-600 mt-1">Deductible</p>
                      </div>
                      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                        <span className="text-xs font-medium text-orange-700">Registration Fee</span>
                        <p className="text-xl font-bold text-orange-700 mt-1">
                          ${safeToLocaleString(vehicle.registration_fee)}
                        </p>
                        <p className="text-xs text-orange-600 mt-1">Deductible</p>
                      </div>
                      {expenseTotals.capitalized > 0 && (
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                          <span className="text-xs font-medium text-blue-700">Acquisition Costs</span>
                          <p className="text-xl font-bold text-blue-700 mt-1">
                            ${safeToLocaleString(expenseTotals.capitalized)}
                          </p>
                          <p className="text-xs text-blue-600 mt-1">Added to cost basis</p>
                        </div>
                      )}
                      {expenseTotals.deductible > 0 && (
                        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                          <span className="text-xs font-medium text-green-700">Deductible Expenses</span>
                          <p className="text-xl font-bold text-green-700 mt-1">
                            ${safeToLocaleString(expenseTotals.deductible)}
                          </p>
                          <p className="text-xs text-green-600 mt-1">Direct write-off</p>
                        </div>
                      )}
                      {expenseTotals.nonDeductible > 0 && (
                        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                          <span className="text-xs font-medium text-gray-700">Non-Deductible</span>
                          <p className="text-xl font-bold text-gray-700 mt-1">
                            ${safeToLocaleString(expenseTotals.nonDeductible)}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">Not tax deductible</p>
                        </div>
                      )}
                    </div>
                  )
                })()}

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
                            </p>
                          </div>
                          <span className="text-sm font-semibold text-red-600">
                            ${safeToLocaleString(repair.cost || 0)}
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

                {/* Additional Expenses List */}
                {vehicle.additional_expenses && vehicle.additional_expenses.length > 0 && (
                  <div className="border-t pt-4">
                    <h3 className="text-sm font-medium text-gray-700 mb-3">Additional Expenses</h3>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {vehicle.additional_expenses.map((expense, index) => {
                        const category = expense.category || 'other_deductible'
                        const isCapitalized = CAPITALIZE_CATEGORIES.includes(category)
                        const isDeductible = DEDUCTIBLE_CATEGORIES.includes(category)
                        
                        let bgColor = 'bg-gray-50'
                        let textColor = 'text-gray-600'
                        let label = '✗ Non-Deductible'
                        
                        if (isCapitalized) {
                          bgColor = 'bg-blue-50'
                          textColor = 'text-blue-700'
                          label = '📦 Capitalized (in cost basis)'
                        } else if (isDeductible) {
                          bgColor = 'bg-green-50'
                          textColor = 'text-green-700'
                          label = '✓ Tax Deductible'
                        }
                        
                        return (
                          <div key={index} className={`flex justify-between items-center rounded-lg p-3 ${bgColor}`}>
                            <div>
                              <p className="text-sm font-medium text-gray-900">
                                {expense.description || expense.category?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || 'Expense'}
                              </p>
                              <p className={`text-xs ${isCapitalized ? 'text-blue-600' : isDeductible ? 'text-green-600' : 'text-gray-500'}`}>
                                {label}
                              </p>
                            </div>
                            <span className={`text-sm font-semibold ${textColor}`}>
                              ${safeToLocaleString(expense.amount)}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* Investment Information */}
      {(vehicle.cash_investment || vehicle.total_cost || vehicle.registration_fee || roiData.current_loan_balance !== null) && (
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
                  ${safeToLocaleString(vehicle.cash_investment ?? roiData.cash_investment)}
                </p>
              </div>
              
              {/* Loan Information - Only for trucks */}
              {vehicle.vehicle_type === 'truck' && displayLoanAmount > 0 && (
                <>
                  <div className={`flex flex-col ${isMobile ? 'bg-gray-50 rounded-lg p-3' : ''}`}>
                    <span className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Original Loan</span>
                    <p className={`${isMobile ? 'text-base' : 'text-xl'} font-semibold text-gray-900`}>
                      ${safeToLocaleString(displayLoanAmount)}
                    </p>
                  </div>
                  
                  {roiData.current_loan_balance !== null && roiData.current_loan_balance !== undefined && (
                    <div className={`flex flex-col ${isMobile ? 'bg-gray-50 rounded-lg p-3' : ''}`}>
                      <span className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Remaining Balance</span>
                      <p className={`${isMobile ? 'text-base' : 'text-xl'} font-semibold ${
                        roiData.current_loan_balance === 0 ? 'text-green-600' : 
                        roiData.current_loan_balance < displayLoanAmount ? 'text-orange-600' : 
                        'text-gray-900'
                      }`}>
                        ${safeToLocaleString(roiData.current_loan_balance)}
                      </p>
                      {roiData.current_loan_balance < displayLoanAmount && roiData.current_loan_balance > 0 && (
                        <p className="text-xs text-gray-500 mt-1">
                          ${safeToLocaleString(displayLoanAmount - (roiData.current_loan_balance || 0))} principal paid
                        </p>
                      )}
                      {roiData.current_loan_balance === 0 && (
                        <p className="text-xs text-green-600 font-medium mt-1">✓ Loan fully paid off!</p>
                      )}
                      {roiData.loan_payoff_date && (
                        <p className="text-xs text-gray-500 mt-1">
                          Paid off on {new Date(roiData.loan_payoff_date).toLocaleDateString()}
                        </p>
                      )}
                      {roiData.current_loan_balance > 0 && roiData.projected_payoff_date && (
                        <p className="text-xs text-gray-500 mt-1">
                          Forecast payoff: {new Date(roiData.projected_payoff_date).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  )}
                  
                  <div className={`flex flex-col ${isMobile ? 'bg-gray-50 rounded-lg p-3' : ''}`}>
                    <span className="text-xs sm:text-sm font-medium text-gray-600 mb-1">Interest Rate</span>
                    <p className={`${isMobile ? 'text-base' : 'text-xl'} font-semibold text-gray-900`}>
                      {(displayInterestRate * 100).toFixed(2)}%
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
                  ${safeToLocaleString(vehicle.total_cost ?? roiData.total_cost)}
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
