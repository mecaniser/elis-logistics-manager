import { useEffect, useState, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { trucksApi, analyticsApi, Truck, PMStatus } from '../services/api'
import Toast from '../components/Toast'
import ConfirmModal from '../components/ConfirmModal'
import { useMobile } from '../utils/useMobile'
import { useTenant } from '../contexts/TenantContext'

// Label with tooltip icon next to it
function LabelWithTooltip({ 
  label, 
  tooltip,
  containerRef
}: { 
  label: string
  tooltip: string
  containerRef?: (el: HTMLDivElement | null) => void
}) {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div ref={containerRef} className="flex items-center">
      <label className="text-xs font-medium text-gray-500">{label}</label>
      <div className="relative ml-1.5 flex-shrink-0">
        <button
          type="button"
          className="text-gray-400 hover:text-gray-600 focus:outline-none"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          onClick={() => setShowTooltip(!showTooltip)}
          aria-label="Show help"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </button>
        {showTooltip && (
          <div className="absolute z-50 w-64 p-3 text-xs text-gray-700 bg-gray-900 text-white rounded-lg shadow-xl left-1/2 -translate-x-1/2 bottom-full mb-2">
            <div>{tooltip}</div>
            {/* Arrow */}
            <div className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Trucks() {
  const isMobile = useMobile()
  const { currentTenant } = useTenant()
  const navigate = useNavigate()

  // Helper to format currency value for display (always 2 decimal places with comma separators when not focused)
  const formatCurrencyDisplay = (value: string | undefined | null): string => {
    if (!value || value === '') return ''
    const num = parseFloat(value)
    if (isNaN(num)) return value
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  // Helper to parse currency input (remove $, commas, etc.)
  const parseCurrency = (value: string): string => {
    return value.replace(/[$,]/g, '').trim()
  }

  // Helper to validate numeric input (allows numbers, decimal point, empty string)
  const isValidNumericInput = (value: string): boolean => {
    return value === '' || /^\d*\.?\d*$/.test(value)
  }

  // Helper to measure text width for auto-resizing inputs
  const measureTextWidth = (text: string, isAmount: boolean = false): number => {
    // Create a temporary span element to measure actual rendered width
    const span = document.createElement('span')
    span.style.visibility = 'hidden'
    span.style.position = 'absolute'
    span.style.whiteSpace = 'pre'
    span.style.fontSize = '14px'
    span.style.fontFamily = window.getComputedStyle(document.body).fontFamily
    span.style.padding = '0 12px' // Match input padding (px-3 = 12px)
    span.textContent = text || (isAmount ? '0.00' : '')
    document.body.appendChild(span)
    const width = Math.ceil(span.offsetWidth)
    document.body.removeChild(span)
    return Math.max(isAmount ? 80 : 150, width + 10) // Add small buffer, min widths
  }
  
  // Track which fields are focused to avoid formatting while typing
  const [focusedFields, setFocusedFields] = useState<Set<string>>(new Set())
  // Track input widths for auto-resizing
  const [inputWidths, setInputWidths] = useState<Record<string, number>>({})
  // Track label container widths (label + tooltip) to match input widths
  const labelContainerRefs = useRef<Record<string, HTMLDivElement | null>>({})
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
    bonus_depreciation: '',
    additional_expenses: [] as Array<{description: string, amount: string}>
  })
  const [truckToDelete, setTruckToDelete] = useState<number | null>(null)
  const [truckToDeleteName, setTruckToDeleteName] = useState<string>('')
  const [expandedPMStatus, setExpandedPMStatus] = useState<Set<number>>(new Set())
  const [expandedFormSections, setExpandedFormSections] = useState<Set<string>>(new Set(['vehicle_info', 'investment']))
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean }>({
    message: '',
    type: 'info',
    isVisible: false
  })

  // Toggle accordion section
  const toggleSection = (section: string) => {
    setExpandedFormSections(prev => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  useEffect(() => {
    // Reset state when tenant changes
    setTrucks([])
    setPmStatus([])
    loadTrucks()
    loadPMStatus()
  }, [vehicleTypeFilter, currentTenant?.id])

  // Helper to measure a single label container width (placeholder for future use)
  const measureLabelContainerWidth = (_key: string) => {
    // Width measurement available via labelContainerRefs if needed
  }

  // Calculate total_cost including additional expenses - use useMemo for reactive calculation
  const calculatedTotalCost = useMemo(() => {
    if (!showForm) return ''
    
    // Helper to safely parse numeric values
    const parseNumeric = (value: string | undefined | null): number => {
      if (value === undefined || value === null || value === '') return 0
      const trimmed = String(value).trim()
      if (trimmed === '') return 0
      const parsed = parseFloat(trimmed)
      return isNaN(parsed) ? 0 : parsed
    }
    
    const cash = parseNumeric(formData.cash_investment)
    const loan = (formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') ? parseNumeric(formData.loan_amount) : 0
    const registration = parseNumeric(formData.registration_fee)
    const additionalTotal = (formData.additional_expenses || []).reduce((sum, exp) => {
      if (!exp || !exp.amount) return sum
      return sum + parseNumeric(exp.amount)
    }, 0)
    
    const total = cash + loan + registration + additionalTotal
    return total > 0 ? total.toFixed(2) : ''
  }, [showForm, formData.cash_investment, formData.loan_amount, formData.registration_fee, JSON.stringify(formData.additional_expenses), formData.vehicle_type])

  // Sync calculatedTotalCost to formData.total_cost
  useEffect(() => {
    if (!showForm) return
    if (calculatedTotalCost !== formData.total_cost) {
      setFormData(prev => ({ ...prev, total_cost: calculatedTotalCost }))
    }
  }, [calculatedTotalCost, showForm])

  // Initialize input widths when additional expenses are added/removed
  useEffect(() => {
    if (!showForm) return
    const widths: Record<string, number> = {}
    formData.additional_expenses.forEach((expense, index) => {
      widths[`desc_${index}`] = measureTextWidth(expense.description || 'e.g., Documentation fee', false)
      widths[`amt_${index}`] = measureTextWidth(formatCurrencyDisplay(expense.amount) || '0.00', true)
    })
    setInputWidths(prev => {
      const updated = { ...prev }
      formData.additional_expenses.forEach((_, index) => {
        updated[`desc_${index}`] = widths[`desc_${index}`]
        updated[`amt_${index}`] = widths[`amt_${index}`]
      })
      // Clean up widths for removed expenses
      Object.keys(updated).forEach(key => {
        const match = key.match(/^(desc|amt)_(\d+)$/)
        if (match) {
          const idx = parseInt(match[2])
          if (idx >= formData.additional_expenses.length) {
            delete updated[key]
          }
        }
      })
      return updated
    })
  }, [formData.additional_expenses.length, showForm])

  // Initialize input widths for depreciation fields
  useEffect(() => {
    if (!showForm) return
    setInputWidths(prev => ({
      ...prev,
      cost_basis: measureTextWidth(formatCurrencyDisplay(formData.cost_basis) || 'Auto-calculated from total cost', true),
      section_179_deduction: measureTextWidth(formatCurrencyDisplay(formData.section_179_deduction) || '0.00', true),
      bonus_depreciation: measureTextWidth(formatCurrencyDisplay(formData.bonus_depreciation) || '0.00', true)
    }))
  }, [showForm, formData.cost_basis, formData.section_179_deduction, formData.bonus_depreciation])

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
    setIsSubmitting(true)
    setFormErrors({})
    
    // Validate required fields
    const errors: Record<string, string> = {}
    if (!formData.name.trim()) {
      errors.name = 'Vehicle name is required'
      setExpandedFormSections(prev => new Set(prev).add('vehicle_info'))
    }
    if (!formData.cash_investment || parseFloat(formData.cash_investment) <= 0) {
      errors.cash_investment = 'Cash investment must be greater than 0'
      setExpandedFormSections(prev => new Set(prev).add('investment'))
    }
    
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      setIsSubmitting(false)
      showToast('Please fix the errors in the form', 'error')
      return
    }
    
    try {
      const vehicleLabel = formData.vehicle_type === 'truck' ? 'Truck' : formData.vehicle_type === 'suv' ? 'SUV' : 'Trailer'
      
      // Helper to safely parse numeric values
      const parseNumeric = (value: string | undefined | null): number => {
        if (value === undefined || value === null || value === '') return 0
        const trimmed = String(value).trim()
        if (trimmed === '') return 0
        const parsed = parseFloat(trimmed)
        return isNaN(parsed) ? 0 : parsed
      }
      
      const investmentData: any = {}
      const cash = parseNumeric(formData.cash_investment)
      const loan = (formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') ? parseNumeric(formData.loan_amount) : 0
      const registration = parseNumeric(formData.registration_fee)
      
      // Calculate additional expenses total
      const additionalTotal = (formData.additional_expenses || []).reduce((sum, exp) => {
        if (!exp || !exp.amount) return sum
        return sum + parseNumeric(exp.amount)
      }, 0)
      
      // Calculate total_cost on the fly to ensure it's always correct
      const calculatedTotal = cash + loan + registration + additionalTotal
      
      if (cash > 0) {
        investmentData.cash_investment = cash
      }
      if (formData.vehicle_type === 'trailer') {
        investmentData.loan_amount = null
        investmentData.interest_rate = undefined
      } else if (formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') {
        if (loan > 0) {
          investmentData.loan_amount = loan
        } else {
          investmentData.loan_amount = null
          investmentData.interest_rate = undefined
        }
      }
      if (calculatedTotal > 0) {
        investmentData.total_cost = calculatedTotal
      }
      // Always send registration_fee explicitly (even if 0) so backend doesn't use stale value
      investmentData.registration_fee = registration > 0 ? registration : null
      // Additional expenses
      if (formData.additional_expenses.length > 0) {
        const validExpenses = formData.additional_expenses
          .filter(exp => exp.description.trim() && exp.amount)
          .map(exp => ({
            description: exp.description.trim(),
            amount: parseNumeric(exp.amount)
          }))
        if (validExpenses.length > 0) {
          investmentData.additional_expenses = validExpenses
        } else {
          investmentData.additional_expenses = undefined
        }
      } else {
        investmentData.additional_expenses = undefined
      }
      
      // Interest rate is handled above with loan_amount logic
      
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
      setExpandedFormSections(new Set(['vehicle_info', 'investment']))
      loadTrucks()
    } catch (err: any) {
      const vehicleLabel = formData.vehicle_type === 'truck' ? 'truck' : formData.vehicle_type === 'suv' ? 'SUV' : 'trailer'
      const errorMessage = err.response?.data?.detail || err.message || `Failed to save ${vehicleLabel}`
      showToast(errorMessage, 'error')
      
      // Expand relevant sections if there are field-specific errors
      if (err.response?.data?.detail) {
        if (err.response.data.detail.includes('name')) {
          setExpandedFormSections(prev => new Set(prev).add('vehicle_info'))
        }
        if (err.response.data.detail.includes('investment') || err.response.data.detail.includes('cost')) {
          setExpandedFormSections(prev => new Set(prev).add('investment'))
        }
      }
    } finally {
      setIsSubmitting(false)
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
      bonus_depreciation: '',
      additional_expenses: []
    })
    setFormErrors({})
    setExpandedFormSections(new Set(['vehicle_info', 'investment']))
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
            {/* Vehicle Information Accordion */}
            <div className="mb-4 bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              <button
                type="button"
                onClick={() => toggleSection('vehicle_info')}
                className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <h3 className="text-sm font-semibold text-gray-700">Vehicle Information</h3>
                <svg
                  className={`w-5 h-5 text-gray-500 transition-transform ${expandedFormSections.has('vehicle_info') ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {expandedFormSections.has('vehicle_info') && (
                <div className="p-4">
              <div className="space-y-3">
                {/* Vehicle Type, Name, VIN, and License Plate/Tag Number - 2 columns on medium, inline on large */}
                <div className="flex items-start gap-4 flex-wrap">
                  <div className="flex items-center min-w-0">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-3 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <label className="text-xs font-medium text-gray-500">Vehicle Type *</label>
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
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
                      className="px-3 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm border-l-0"
                      style={{ minWidth: '120px' }}
              >
                <option value="truck">Truck</option>
                      <option value="suv">SUV</option>
                <option value="trailer">Trailer</option>
              </select>
            </div>
                  <div className="flex items-center min-w-0 relative">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-3 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <label className="text-xs font-medium text-gray-500">Name *</label>
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
              <input
                type="text"
                value={formData.name}
                      onChange={(e) => {
                        setFormData({ ...formData, name: e.target.value })
                        if (formErrors.name) {
                          setFormErrors(prev => {
                            const next = { ...prev }
                            delete next.name
                            return next
                          })
                        }
                      }}
                required
                      className={`px-3 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 text-sm text-right border-l-0 ${
                        formErrors.name 
                          ? 'border-red-500 focus:ring-red-500' 
                          : 'focus:ring-blue-500'
                      }`}
                      style={{ minWidth: '150px' }}
                    />
                    {formErrors.name && (
                      <p className="absolute top-full mt-1 text-xs text-red-600 whitespace-nowrap">{formErrors.name}</p>
                    )}
            </div>
                  <div className="flex items-center min-w-0">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-3 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <label className="text-xs font-medium text-gray-500">VIN</label>
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                    <input
                      type="text"
                      value={formData.vin}
                      onChange={(e) => setFormData({ ...formData, vin: e.target.value })}
                      placeholder="Enter 17-character VIN"
                      maxLength={17}
                      className="px-3 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm text-right border-l-0"
                      style={{ minWidth: '180px' }}
                    />
                  </div>
                  {(formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') && (
                    <div className="flex items-center min-w-0">
                      <div className="flex-shrink-0 flex items-center h-[38px] px-3 py-2 border border-gray-300 rounded-l-md border-r-0">
                        <label className="text-xs font-medium text-gray-500">License Plate</label>
                      </div>
                      <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                <input
                  type="text"
                  value={formData.license_plate}
                  onChange={(e) => setFormData({ ...formData, license_plate: e.target.value })}
                        className="px-3 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm text-right border-l-0"
                        style={{ minWidth: '120px' }}
                />
              </div>
            )}
            {formData.vehicle_type === 'trailer' && (
                    <div className="flex items-center min-w-0">
                      <div className="flex-shrink-0 flex items-center h-[38px] px-3 py-2 border border-gray-300 rounded-l-md border-r-0">
                        <label className="text-xs font-medium text-gray-500">Tag Number</label>
                      </div>
                      <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                <input
                  type="text"
                  value={formData.tag_number}
                  onChange={(e) => setFormData({ ...formData, tag_number: e.target.value })}
                        className="px-3 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm text-right border-l-0"
                        style={{ minWidth: '120px' }}
                />
              </div>
            )}
                </div>
              </div>
                </div>
              )}
            </div>
            
            {/* Investment Information Accordion */}
            <div className="mb-4 bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              <button
                type="button"
                onClick={() => toggleSection('investment')}
                className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <h3 className="text-sm font-semibold text-gray-700">Investment Information</h3>
                <svg
                  className={`w-5 h-5 text-gray-500 transition-transform ${expandedFormSections.has('investment') ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {expandedFormSections.has('investment') && (
                <div className="p-4">
              <div className="space-y-3">
                {/* All investment fields in one flexible row */}
                <div className="flex flex-wrap items-start gap-2">
                  <div className="flex items-center relative">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <label className="text-xs font-medium text-gray-500 whitespace-nowrap">Cash ($) *</label>
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                  <input
                      type="text"
                    inputMode="decimal"
                    value={focusedFields.has('cash_investment') ? formData.cash_investment : formatCurrencyDisplay(formData.cash_investment)}
                    onChange={(e) => {
                      const inputValue = e.target.value
                      // Allow only numbers, decimal point, and empty string
                      if (inputValue === '' || /^\d*\.?\d*$/.test(inputValue)) {
                        const value = parseCurrency(inputValue)
                        // Prevent negative values
                        if (value === '' || parseFloat(value) >= 0 || isNaN(parseFloat(value))) {
                          setFormData({ ...formData, cash_investment: value })
                          if (formErrors.cash_investment) {
                            setFormErrors(prev => {
                              const next = { ...prev }
                              delete next.cash_investment
                              return next
                            })
                          }
                        }
                      }
                    }}
                    onFocus={() => setFocusedFields(prev => new Set(prev).add('cash_investment'))}
                    onBlur={(e) => {
                      // Format to 2 decimal places on blur
                      const value = parseCurrency(e.target.value)
                      if (value && !isNaN(parseFloat(value))) {
                        const formatted = parseFloat(value).toFixed(2)
                        setFormData({ ...formData, cash_investment: formatted })
                      }
                      setFocusedFields(prev => {
                        const next = new Set(prev)
                        next.delete('cash_investment')
                        return next
                      })
                    }}
                    placeholder="0.00"
                    className={`px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 text-sm text-right border-l-0 w-[100px] ${
                      formErrors.cash_investment 
                        ? 'border-red-500 focus:ring-red-500' 
                        : 'focus:ring-blue-500'
                    }`}
                  />
                  {formErrors.cash_investment && (
                    <p className="absolute top-full mt-1 text-xs text-red-600 whitespace-nowrap">{formErrors.cash_investment}</p>
                  )}
                </div>
                  {(formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv') && (
                  <>
                      <div className="flex items-center">
                        <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0">
                          <label className="text-xs font-medium text-gray-500 whitespace-nowrap">Loan ($)</label>
                        </div>
                        <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                      <input
                          type="text"
                        inputMode="decimal"
                        value={focusedFields.has('loan_amount') ? formData.loan_amount : formatCurrencyDisplay(formData.loan_amount)}
                        onChange={(e) => {
                          const inputValue = e.target.value
                          if (isValidNumericInput(inputValue)) {
                            const loanValue = parseCurrency(inputValue)
                            // Prevent negative values
                            if (loanValue === '' || parseFloat(loanValue) >= 0 || isNaN(parseFloat(loanValue))) {
                              // If loan amount is cleared/zero, clear interest rate as well
                              if (!loanValue || parseFloat(loanValue) === 0) {
                                setFormData({ ...formData, loan_amount: loanValue, interest_rate: '' })
                              } else {
                                setFormData({ ...formData, loan_amount: loanValue })
                              }
                            }
                          }
                        }}
                        onFocus={() => setFocusedFields(prev => new Set(prev).add('loan_amount'))}
                        onBlur={(e) => {
                          // Format to 2 decimal places on blur
                          const value = parseCurrency(e.target.value)
                          if (value && !isNaN(parseFloat(value))) {
                            const formatted = parseFloat(value).toFixed(2)
                            setFormData({ ...formData, loan_amount: formatted })
                          }
                          setFocusedFields(prev => {
                            const next = new Set(prev)
                            next.delete('loan_amount')
                            return next
                          })
                        }}
                        placeholder="0.00"
                        className="px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm text-right border-l-0 w-[100px]"
                      />
                    </div>
                      {formData.loan_amount && parseFloat(formData.loan_amount) > 0 && (
                        <div className="flex items-center">
                          <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0">
                            <label className="text-xs font-medium text-gray-500 whitespace-nowrap">Rate (%)</label>
                          </div>
                          <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                          <input
                          type="text"
                          inputMode="decimal"
                          value={(() => {
                            if (!formData.interest_rate || formData.interest_rate === '') {
                              return ''
                            }
                            const decimalValue = parseFloat(formData.interest_rate)
                            if (isNaN(decimalValue)) {
                              return ''
                            }
                            const percentValue = decimalValue * 100
                            // Round to avoid floating point precision issues (e.g., 0.07 * 100 = 7.000000000000001)
                            const roundedPercent = Math.round(percentValue * 100) / 100
                            return focusedFields.has('interest_rate') 
                              ? roundedPercent.toString() 
                              : roundedPercent.toFixed(2)
                          })()}
                        onChange={(e) => {
                            const inputValue = e.target.value
                            // Allow empty string or valid numeric input
                            if (inputValue === '' || isValidNumericInput(inputValue)) {
                              if (inputValue === '') {
                                setFormData({ ...formData, interest_rate: '' })
                              } else {
                                const value = parseCurrency(inputValue)
                                if (value !== '') {
                                  const percentValue = parseFloat(value)
                                  if (!isNaN(percentValue) && percentValue >= 0 && percentValue <= 100) {
                                    const decimalValue = (percentValue / 100).toFixed(4)
                                    setFormData({ ...formData, interest_rate: decimalValue })
                                  }
                                }
                              }
                            }
                        }}
                        onFocus={() => setFocusedFields(prev => new Set(prev).add('interest_rate'))}
                        onBlur={(e) => {
                          const inputValue = e.target.value
                          if (inputValue === '') {
                            setFormData({ ...formData, interest_rate: '' })
                          } else {
                            const value = parseCurrency(inputValue)
                            if (value !== '') {
                              const percentValue = parseFloat(value)
                              if (!isNaN(percentValue) && percentValue >= 0 && percentValue <= 100) {
                                const decimalValue = (percentValue / 100).toFixed(4)
                                setFormData({ ...formData, interest_rate: decimalValue })
                              }
                            }
                          }
                          setFocusedFields(prev => {
                            const next = new Set(prev)
                            next.delete('interest_rate')
                            return next
                          })
                        }}
                        placeholder="7.00"
                          className="px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm text-right border-l-0 w-[70px]"
                      />
                    </div>
                      )}
                  </>
                )}
                  <div className="flex items-center">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <label className="text-xs font-medium text-gray-500 whitespace-nowrap">Reg. Fee ($)</label>
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                    <input
                      type="text"
                    inputMode="decimal"
                    value={focusedFields.has('registration_fee') ? formData.registration_fee : formatCurrencyDisplay(formData.registration_fee)}
                    onChange={(e) => {
                      const inputValue = e.target.value
                      if (isValidNumericInput(inputValue)) {
                        const newValue = parseCurrency(inputValue)
                        // Prevent negative values
                        if (newValue === '' || parseFloat(newValue) >= 0 || isNaN(parseFloat(newValue))) {
                          setFormData(prev => ({ ...prev, registration_fee: newValue }))
                        }
                      }
                    }}
                    onFocus={() => setFocusedFields(prev => new Set(prev).add('registration_fee'))}
                    onBlur={(e) => {
                      // Format to 2 decimal places on blur
                      const value = parseCurrency(e.target.value)
                      if (value && !isNaN(parseFloat(value))) {
                        const formatted = parseFloat(value).toFixed(2)
                        setFormData(prev => ({ ...prev, registration_fee: formatted }))
                      }
                      setFocusedFields(prev => {
                        const next = new Set(prev)
                        next.delete('registration_fee')
                        return next
                      })
                    }}
                    placeholder="0.00"
                    className="px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm text-right border-l-0 w-[100px]"
                  />
                  </div>
                  <div className="flex items-center">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0 bg-gray-50">
                      <label className="text-xs font-medium text-gray-500 whitespace-nowrap">Total ($)</label>
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                  <input
                    type="text"
                    value={calculatedTotalCost ? parseFloat(calculatedTotalCost).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : ''}
                    readOnly
                    placeholder="Auto"
                    className="px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none bg-gray-50 text-gray-700 cursor-not-allowed text-sm text-right border-l-0 w-[100px]"
                  />
                  </div>
                </div>
                <p className="text-xs text-gray-500">
                  {formData.vehicle_type === 'truck' || formData.vehicle_type === 'suv'
                    ? 'Total Cost = Cash + Loan + Registration + Additional Expenses'
                    : 'Total Cost = Cash + Registration + Additional Expenses'}
                  </p>
                </div>
                </div>
              )}
            </div>
            
            {/* Additional Expenses Accordion */}
            <div className="mb-4 bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              <button
                type="button"
                onClick={() => toggleSection('additional_expenses')}
                className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <h3 className="text-sm font-semibold text-gray-700">Additional Investment Expenses</h3>
                <svg
                  className={`w-5 h-5 text-gray-500 transition-transform ${expandedFormSections.has('additional_expenses') ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {expandedFormSections.has('additional_expenses') && (
                <div className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <label className="block text-sm font-medium text-gray-700">Additional Investment Expenses</label>
                    <button
                      type="button"
                      onClick={() => {
                        setFormData(prev => ({
                          ...prev,
                          additional_expenses: [...prev.additional_expenses, { description: '', amount: '' }]
                        }))
                      }}
                      className="text-sm text-blue-600 hover:text-blue-800"
                    >
                      + Add Expense
                    </button>
                  </div>
                  {formData.additional_expenses.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {formData.additional_expenses.map((expense, index) => (
                        <div key={index} className="relative bg-white border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
                          {/* X button in top-right corner */}
                          <button
                            type="button"
                            onClick={() => {
                              setFormData(prev => {
                                const updated = prev.additional_expenses.filter((_, i) => i !== index)
                                return { ...prev, additional_expenses: updated }
                              })
                            }}
                            className="absolute top-2 right-2 text-gray-400 hover:text-red-600 transition-colors p-1 rounded-full hover:bg-red-50"
                            title="Remove expense"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                          
                          {/* Description and Amount inline */}
                          <div className="pr-6 min-w-0">
                            <div className="flex items-start min-w-0">
                              {/* Description input */}
                              <div className="flex-1 min-w-0">
                                <label className="block text-xs font-medium text-gray-500 mb-1">Description</label>
                                <input
                                  type="text"
                                  value={expense.description}
                                  onChange={(e) => {
                                    const value = e.target.value
                                    setFormData(prev => {
                                      const updated = [...prev.additional_expenses]
                                      updated[index] = { ...updated[index], description: value }
                                      return { ...prev, additional_expenses: updated }
                                    })
                                  }}
                                  placeholder="e.g., Documentation fee"
                                  className="w-full px-3 py-2 border border-gray-300 rounded-l-md rounded-r-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm border-r-0"
                                />
                              </div>
                              
                              {/* Red divider - aligned with inputs */}
                              <div className="flex-shrink-0 flex flex-col" style={{ width: '6px', marginLeft: '-3px', marginRight: '-3px' }}>
                                <div className="text-xs font-medium mb-1" style={{ height: '16px' }}></div>
                                <div className="w-0.5 h-[38px] bg-red-600"></div>
                              </div>
                              
                              {/* Amount input */}
                              <div className="flex-shrink-0">
                                <label className="block text-xs font-medium text-gray-500 mb-1">Amount</label>
                                <input
                                  type="text"
                                  inputMode="decimal"
                                  value={focusedFields.has(`additional_expense_${index}`) ? expense.amount : formatCurrencyDisplay(expense.amount)}
                                  onChange={(e) => {
                                    const inputValue = e.target.value
                                    if (isValidNumericInput(inputValue)) {
                                      const newAmount = parseCurrency(inputValue)
                                      // Prevent negative values
                                      if (newAmount === '' || parseFloat(newAmount) >= 0 || isNaN(parseFloat(newAmount))) {
                                        const displayValue = focusedFields.has(`additional_expense_${index}`) ? newAmount : formatCurrencyDisplay(newAmount)
                                        const width = measureTextWidth(displayValue || '0.00', true)
                                        setInputWidths(prev => ({ ...prev, [`amt_${index}`]: width }))
                                        setFormData(prev => {
                                          const updated = [...prev.additional_expenses]
                                          updated[index] = { ...updated[index], amount: newAmount }
                                          return { ...prev, additional_expenses: updated }
                                        })
                                      }
                                    }
                                  }}
                                  onFocus={(e) => {
                                    setFocusedFields(prev => new Set(prev).add(`additional_expense_${index}`))
                                    const width = measureTextWidth(e.target.value || '0.00', true)
                                    setInputWidths(prev => ({ ...prev, [`amt_${index}`]: width }))
                                  }}
                                  onBlur={(e) => {
                                    // Format to 2 decimal places on blur
                                    const value = parseCurrency(e.target.value)
                                    if (value && !isNaN(parseFloat(value))) {
                                      const formatted = parseFloat(value).toFixed(2)
                                      const displayValue = formatCurrencyDisplay(formatted)
                                      const width = measureTextWidth(displayValue, true)
                                      setInputWidths(prev => ({ ...prev, [`amt_${index}`]: width }))
                                      setFormData(prev => {
                                        const updated = [...prev.additional_expenses]
                                        updated[index] = { ...updated[index], amount: formatted }
                                        return { ...prev, additional_expenses: updated }
                                      })
                                    }
                                    setFocusedFields(prev => {
                                      const next = new Set(prev)
                                      next.delete(`additional_expense_${index}`)
                                      return next
                                    })
                                  }}
                                  placeholder="0.00"
                                  style={{ 
                                    width: `${inputWidths[`amt_${index}`] || measureTextWidth(formatCurrencyDisplay(expense.amount) || '0.00', true)}px`,
                                    minWidth: '80px',
                                    maxWidth: '110px'
                                  }}
                                  className="px-3 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm border-l-0 text-right"
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="text-xs text-gray-500 mt-2">Add any additional fees or expenses paid when purchasing the vehicle (e.g., documentation fees, inspection fees, etc.)</p>
                </div>
              )}
            </div>
            
            {/* Depreciation Settings Accordion */}
            <div className="mb-4 bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              <button
                type="button"
                onClick={() => toggleSection('depreciation')}
                className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <h3 className="text-sm font-semibold text-gray-700">Depreciation Settings</h3>
                <svg
                  className={`w-5 h-5 text-gray-500 transition-transform ${expandedFormSections.has('depreciation') ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {expandedFormSections.has('depreciation') && (
                <div className="p-4">
              <div className="space-y-4">
                {/* All depreciation fields in one flexible row */}
                <div className="flex flex-wrap items-start gap-2">
                  <div className="flex items-center">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <LabelWithTooltip 
                        label="Purchase Date" 
                        tooltip="Date vehicle was purchased/placed in service"
                        containerRef={(el) => { 
                          labelContainerRefs.current['purchase_date'] = el
                          if (el) setTimeout(() => measureLabelContainerWidth('purchase_date'), 0)
                        }}
                      />
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                    <input
                      type="date"
                      value={formData.purchase_date}
                      onChange={(e) => setFormData({ ...formData, purchase_date: e.target.value })}
                      className="px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm border-l-0 w-[130px]"
                    />
                  </div>
                  <div className="flex items-center">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <LabelWithTooltip 
                        label="Method" 
                        tooltip="Method for calculating depreciation"
                        containerRef={(el) => { 
                          labelContainerRefs.current['depreciation_method'] = el
                          if (el) setTimeout(() => measureLabelContainerWidth('depreciation_method'), 0)
                        }}
                      />
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                    <select
                      value={formData.depreciation_method}
                      onChange={(e) => setFormData({ ...formData, depreciation_method: e.target.value as 'MACRS_5' | 'straight_line' | 'none' })}
                      className="px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm border-l-0"
                    >
                      <option value="MACRS_5">MACRS 5-Year</option>
                      <option value="straight_line">Straight-Line</option>
                      <option value="none">None</option>
                    </select>
                  </div>
                  <div className="flex items-center">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <LabelWithTooltip 
                        label="Cost Basis ($)" 
                        tooltip="Depreciable amount (total cost - Section 179 - bonus depreciation)"
                        containerRef={(el) => { 
                          labelContainerRefs.current['cost_basis'] = el
                          if (el) setTimeout(() => measureLabelContainerWidth('cost_basis'), 0)
                        }}
                      />
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={focusedFields.has('cost_basis') ? formData.cost_basis : formatCurrencyDisplay(formData.cost_basis)}
                    onChange={(e) => {
                      const inputValue = e.target.value
                      if (isValidNumericInput(inputValue)) {
                        const value = parseCurrency(inputValue)
                        // Prevent negative values
                        if (value === '' || parseFloat(value) >= 0 || isNaN(parseFloat(value))) {
                          const displayValue = focusedFields.has('cost_basis') ? value : formatCurrencyDisplay(value)
                          const width = measureTextWidth(displayValue || e.target.placeholder || '0.00', true)
                          setInputWidths(prev => ({ ...prev, cost_basis: width }))
                          setFormData({ ...formData, cost_basis: value })
                        }
                      }
                    }}
                    onFocus={(e) => {
                      setFocusedFields(prev => new Set(prev).add('cost_basis'))
                      const width = measureTextWidth(e.target.value || e.target.placeholder || '0.00', true)
                      setInputWidths(prev => ({ ...prev, cost_basis: width }))
                    }}
                    onBlur={(e) => {
                      // Format to 2 decimal places on blur
                      const value = parseCurrency(e.target.value)
                      if (value && !isNaN(parseFloat(value))) {
                        const formatted = parseFloat(value).toFixed(2)
                        const displayValue = formatCurrencyDisplay(formatted)
                        const width = measureTextWidth(displayValue, true)
                        setInputWidths(prev => ({ ...prev, cost_basis: width }))
                        setFormData({ ...formData, cost_basis: formatted })
                      }
                      setFocusedFields(prev => {
                        const next = new Set(prev)
                        next.delete('cost_basis')
                        return next
                      })
                    }}
                    placeholder="0.00"
                    className="px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm text-right border-l-0 w-[100px]"
                  />
                  </div>
                  <div className="flex items-center">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <LabelWithTooltip 
                        label="Sec. 179 ($)" 
                        tooltip="First-year Section 179 deduction (if applicable)"
                        containerRef={(el) => { 
                          labelContainerRefs.current['section_179_deduction'] = el
                          if (el) setTimeout(() => measureLabelContainerWidth('section_179_deduction'), 0)
                        }}
                      />
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={focusedFields.has('section_179_deduction') ? formData.section_179_deduction : formatCurrencyDisplay(formData.section_179_deduction)}
                    onChange={(e) => {
                      const inputValue = e.target.value
                      if (isValidNumericInput(inputValue)) {
                        const value = parseCurrency(inputValue)
                        // Prevent negative values
                        if (value === '' || parseFloat(value) >= 0 || isNaN(parseFloat(value))) {
                          const displayValue = focusedFields.has('section_179_deduction') ? value : formatCurrencyDisplay(value)
                          const width = measureTextWidth(displayValue || '0.00', true)
                          setInputWidths(prev => ({ ...prev, section_179_deduction: width }))
                          setFormData({ ...formData, section_179_deduction: value })
                        }
                      }
                    }}
                    onFocus={(e) => {
                      setFocusedFields(prev => new Set(prev).add('section_179_deduction'))
                      const width = measureTextWidth(e.target.value || '0.00', true)
                      setInputWidths(prev => ({ ...prev, section_179_deduction: width }))
                    }}
                    onBlur={(e) => {
                      // Format to 2 decimal places on blur
                      const value = parseCurrency(e.target.value)
                      if (value && !isNaN(parseFloat(value))) {
                        const formatted = parseFloat(value).toFixed(2)
                        const displayValue = formatCurrencyDisplay(formatted)
                        const width = measureTextWidth(displayValue, true)
                        setInputWidths(prev => ({ ...prev, section_179_deduction: width }))
                        setFormData({ ...formData, section_179_deduction: formatted })
                      }
                      setFocusedFields(prev => {
                        const next = new Set(prev)
                        next.delete('section_179_deduction')
                        return next
                      })
                    }}
                    placeholder="0.00"
                    className="px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm text-right border-l-0 w-[100px]"
                  />
                </div>
                  <div className="flex items-center">
                    <div className="flex-shrink-0 flex items-center h-[38px] px-2 py-2 border border-gray-300 rounded-l-md border-r-0">
                      <LabelWithTooltip 
                        label="Bonus (%)" 
                        tooltip="Bonus depreciation percentage (e.g., 100 for 100%)"
                        containerRef={(el) => { 
                          labelContainerRefs.current['bonus_depreciation'] = el
                          if (el) setTimeout(() => measureLabelContainerWidth('bonus_depreciation'), 0)
                        }}
                      />
                    </div>
                    <div className="flex-shrink-0 w-0.5 h-[38px] bg-red-600"></div>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={focusedFields.has('bonus_depreciation') ? formData.bonus_depreciation : formatCurrencyDisplay(formData.bonus_depreciation)}
                    onChange={(e) => {
                      const inputValue = e.target.value
                      if (isValidNumericInput(inputValue)) {
                        const value = parseCurrency(inputValue)
                        // Prevent negative values
                        if (value === '' || parseFloat(value) >= 0 || isNaN(parseFloat(value))) {
                          const displayValue = focusedFields.has('bonus_depreciation') ? value : formatCurrencyDisplay(value)
                          const width = measureTextWidth(displayValue || '0.00', true)
                          setInputWidths(prev => ({ ...prev, bonus_depreciation: width }))
                          setFormData({ ...formData, bonus_depreciation: value })
                        }
                      }
                    }}
                    onFocus={(e) => {
                      setFocusedFields(prev => new Set(prev).add('bonus_depreciation'))
                      const width = measureTextWidth(e.target.value || '0.00', true)
                      setInputWidths(prev => ({ ...prev, bonus_depreciation: width }))
                    }}
                    onBlur={(e) => {
                      // Format to 2 decimal places on blur
                      const value = parseCurrency(e.target.value)
                      if (value && !isNaN(parseFloat(value))) {
                        const formatted = parseFloat(value).toFixed(2)
                        const displayValue = formatCurrencyDisplay(formatted)
                        const width = measureTextWidth(displayValue, true)
                        setInputWidths(prev => ({ ...prev, bonus_depreciation: width }))
                        setFormData({ ...formData, bonus_depreciation: formatted })
                      }
                      setFocusedFields(prev => {
                        const next = new Set(prev)
                        next.delete('bonus_depreciation')
                        return next
                      })
                    }}
                    placeholder="0.00"
                    className="px-2 py-2 border border-gray-300 rounded-r-md rounded-l-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm text-right border-l-0 w-[80px]"
                  />
                  </div>
                </div>
              </div>
                </div>
              )}
            </div>
            
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSubmitting && (
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                )}
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
                    <div className={`flex ${isMobile ? 'flex-col' : ''} gap-2 ml-4`}>
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
                            bonus_depreciation: truck.bonus_depreciation?.toString() || '',
                            additional_expenses: truck.additional_expenses?.map(exp => ({
                              description: exp.description || '',
                              amount: exp.amount?.toString() || ''
                            })) || []
                          })
                          setShowForm(true)
                          setExpandedFormSections(new Set(['vehicle_info', 'investment']))
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
      {(vehicleTypeFilter === 'all' || vehicleTypeFilter === 'suv') && suvsList.length > 0 && (
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
                            additional_expenses: suv.additional_expenses?.map(exp => ({
                              description: exp.description || '',
                              amount: exp.amount?.toString() || ''
                            })) || []
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
                            bonus_depreciation: trailer.bonus_depreciation?.toString() || '',
                            additional_expenses: trailer.additional_expenses?.map(exp => ({
                              description: exp.description || '',
                              amount: exp.amount?.toString() || ''
                            })) || []
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
