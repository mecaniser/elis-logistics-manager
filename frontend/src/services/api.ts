import axios from 'axios'

const handleAuthFailure = async (error: unknown) => {
  const status = (error as { response?: { status?: number } })?.response?.status
  if (status === 401 && window.location.pathname !== '/login') {
    // An endpoint can require stronger authorization than the app shell.
    // A valid shell session (including local-dev mode) must not loop through Login.
    try {
      await axios.get('/api/auth/me', { withCredentials: true })
      return Promise.reject(error)
    } catch {
      // Only recover through Login when the shell session check also fails.
    }
    const from = `${window.location.pathname}${window.location.search}${window.location.hash}`
    const query = new URLSearchParams({ from, reason: 'session-expired' })
    window.location.replace(`/login?${query.toString()}`)
  }
  return Promise.reject(error)
}

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // include auth cookies
})

// Add tenant ID interceptor to include X-Tenant-ID header in all requests
api.interceptors.request.use((config) => {
  // Skip adding tenant_id header for tenants endpoints (they don't need it)
  if (config.url && /^\/tenants(?:\/|$)/.test(config.url)) {
    return config
  }
  
  const tenantId = localStorage.getItem('currentTenantId')
  if (!tenantId) {
    // If no tenant ID, this will cause an error - which is correct behavior
    // The user must select a tenant before making API calls
    console.error('No tenant ID found in localStorage. Please select a business first.')
    throw new Error('No tenant ID available. Please select a business.')
  } else {
    config.headers['X-Tenant-ID'] = parseInt(tenantId, 10)
  }
  return config
}, (error) => {
  return Promise.reject(error)
})

// Redirect to login on auth failures
api.interceptors.response.use((response) => response, handleAuthFailure)

// Separate axios instance for FormData requests (no default Content-Type header)
// This allows the browser to automatically set multipart/form-data with boundary
const formDataApi = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

// Add tenant ID interceptor for FormData requests
formDataApi.interceptors.request.use((config) => {
  const tenantId = localStorage.getItem('currentTenantId')
  if (tenantId) {
    config.headers['X-Tenant-ID'] = parseInt(tenantId, 10)
  }
  // Don't set Content-Type - let browser set it automatically with boundary for FormData
  return config
}, (error) => {
  return Promise.reject(error)
})

formDataApi.interceptors.response.use((response) => response, handleAuthFailure)

// Types
export interface Truck {
  id: number
  name: string
  vehicle_type: 'truck' | 'trailer' | 'suv'
  license_plate?: string  // For trucks and SUVs
  tag_number?: string  // For trailers
  vin?: string
  default_trailer_id?: number | null
  default_trailer_income_split_amount?: number | null
  default_repair_reserve_amount?: number | null
  trailer_depreciation_reserve_amount?: number | null
  expected_resale_value?: number | null
  investment_plans?: Record<string, string | number | null>[] | null
  planned_service_weeks?: number | null
  estimated_mpg?: number | null
  fuel_card_discount_per_gallon?: number | null
  license_plate_history?: string[]
  cash_investment?: number | null  // Cash invested in vehicle
  loan_amount?: number | null  // Loan amount for financed vehicles
  current_loan_balance?: number  // Current loan balance (reduces as principal is paid)
  loan_term_months?: number | null  // Original loan duration in months
  interest_rate?: number  // Annual interest rate (default 0.07 = 7%)
  total_cost?: number  // Total purchase cost (cash + loan + fees)
  registration_fee?: number | null  // Registration fee for vehicle
  // Depreciation fields
  purchase_date?: string  // Date vehicle was purchased/placed in service (ISO date string)
  depreciation_method?: 'MACRS_5' | 'straight_line' | 'none'  // Depreciation method
  cost_basis?: number  // Depreciable cost basis
  section_179_deduction?: number  // Section 179 deduction taken in first year
  bonus_depreciation?: number  // Bonus depreciation percentage (e.g., 100 for 100%)
  additional_expenses?: Array<{category?: string, description: string, amount: number}>  // Additional expenses/fees with category
  // PM (Preventive Maintenance) Schedule fields (trucks only)
  last_pm_date?: string  // Date of last D13 full PM (ISO date string)
  last_pm_repair_id?: number  // Reference to the repair record
  pm_threshold_months?: number  // PM due every N months (default 3)
  vehicle_documents?: VehicleDocument[]
}

export interface VehicleDocument {
  id: number
  truck_id: number
  document_type: 'title' | 'inspection' | 'registration' | 'insurance' | 'permit' | 'other'
  title?: string | null
  notes?: string | null
  original_filename: string
  file_path: string
  mime_type?: string | null
  file_size?: number | null
  uploaded_at: string
}

export interface VehicleROI {
  vehicle_id: number
  vehicle_name: string
  vehicle_type: 'truck' | 'trailer'
  cash_investment: number | null
  loan_amount: number | null
  loan_term_months: number | null
  trailer_depreciation_reserve_amount: number | null
  current_loan_balance: number | null
  loan_payoff_date: string | null
  projected_payoff_date: string | null
  estimated_settlements_to_payoff: number | null
  average_principal_payment: number | null
  latest_settlement_date: string | null
  principal_paid_from_excess: number
  interest_rate: number
  total_cost: number | null
  registration_fee: number | null
  cumulative_revenue: number
  cumulative_settlement_expenses: number
  cumulative_repair_costs: number
  cumulative_loan_interest: number
  cumulative_net_profit: number
  trailer_settlement_count: number
  trailer_depreciation_reserve_total: number | null
  trailer_replacement_reserve_target: number | null
  trailer_reserve_remaining: number | null
  trailer_expected_resale_value: number | null
  trailer_planned_service_weeks: number | null
  trailer_net_sale_proceeds_today: number | null
  trailer_cash_after_principal_and_reserve: number | null
  trailer_free_profit: number | null
  trailer_cash_position_total: number | null
  trailer_break_even_sale_price: number | null
  trailer_projected_three_year_reserve: number | null
  cash_recovery_percentage: number | null
  cash_recovery_amount: number | null
  cash_recovery_achieved: boolean
  remaining_to_cash_recovery: number | null
  investment_recovery_percentage: number | null
  remaining_to_break_even: number | null
  break_even_achieved: boolean
  clean_cash_return: number | null
}

export interface Settlement {
  id: number
  truck_id: number
  driver_id?: number | null
  driver_name?: string | null
  trailer_income_split_trailer_id?: number | null
  trailer_income_split_amount?: number | null
  repair_reserve_amount?: number | null
  source_settlement_id?: number | null
  settlement_date: string | null
  week_start?: string | null
  week_end?: string | null
  miles_driven?: number | null
  blocks_delivered?: number | null
  block_ids?: (string | { block_id: string; delivery_date?: string })[] | null  // Array of block IDs (strings) or objects with block_id and delivery_date
  gross_revenue?: number | null
  expenses?: number | null
  expense_categories?: { [key: string]: number } | null
  overview_amounts?: { [key: string]: number } | null
  custom_expense_descriptions?: { [key: string]: string } | null  // Descriptions for custom expenses: {custom_1: "handles replaced", custom_2: "truck parking"}
  custom_expense_validation?: { [key: string]: boolean } | null  // Validation status for custom expenses: {deduct: true, decals: false}
  reimbursement_details?: Array<{ description: string; amount: number | null }> | null  // Reimbursement details from PDF
  deduction_details?: Array<{ description: string; amount: number | null }> | null  // Deduction details from PDF
  net_profit?: number | null
  cash_settlement_amount?: number | null
  cash_adjustments?: Array<{ type: string; description: string; amount: number | null }> | null
  pdf_file_path?: string | null
  settlement_type?: string | null
  license_plate?: string | null
  duplicate_block_ids_warning?: {
    has_duplicates: boolean
    duplicate_block_ids: string[]
    conflicting_settlements: Array<{
      block_id: string
      settlement_id: number
      truck_id: number
      settlement_date: string | null
    }>
    warning_message: string
  } | null
}

export interface Repair {
  id: number
  truck_id: number
  repair_date: string
  title?: string
  details?: string
  description: string
  cost: number
  miles?: number  // Miles/odometer reading at time of repair (for PM tracking)
  category?: string
  invoice_number?: string
  receipt_path?: string
  image_paths?: string[]
  paid_from_reserve?: boolean
}

export interface ReserveBalance {
  truck_id: number
  balance: number
  deposits_total: number
  withdrawals_total: number
  adjustments_total: number
  as_of: string
}

export interface ReserveLedgerEntry {
  id: number
  tenant_id: number
  truck_id: number
  entry_date: string
  entry_type: 'deposit' | 'withdrawal' | 'adjustment'
  amount: number
  description?: string | null
  source_type?: string | null
  source_id?: number | null
  created_at?: string
}

export interface RepairReserveWithdrawal {
  entry_id: number
  truck_id: number
  payment_date: string
  amount: number
  basis: 'verified_payment' | 'legacy_recorded_withdrawal'
}

export interface DashboardData {
  repair_reserve_withdrawals?: RepairReserveWithdrawal[]
  repairs_by_month?: Array<{ repair_id?: number; truck_id: number; month_key: string; month: string; category?: string; cost: number; truck_name?: string; description?: string; repair_date?: string }>
  blocks_by_truck_month?: Array<{ truck_id: number; month_key: string; month: string; blocks: number; block_ids?: (string | {block_id:string; delivery_date?:string})[]; truck_name?:string }>

  total_trucks: number
  total_settlements: number
  total_revenue: number
  total_expenses: number
  net_profit: number
  operational_metrics?: OperationalMetrics
  expense_categories?: {
    fuel: number
    tolls: number
    dispatch_fee: number
    insurance: number
    safety: number
    prepass: number
    ifta: number
    deduct: number
    fleet_manager_support: number
    driver_pay: number
    payroll_fee: number
    truck_parking: number
    repairs: number
    custom: number
  }
  custom_descriptions?: { [key: string]: string }  // Descriptions for custom expense categories (e.g., {"custom_truck_parking": "Truck Parking"})
  truck_profits: Array<{
    truck_id: number
    truck_name: string
    total_revenue: number
    total_expenses: number
    settlement_expenses: number
    repair_costs: number
    profit_before_repairs: number
    net_profit: number
  }>
  pm_status?: Array<{
    truck_id: number
    truck_name: string
    last_pm_date: string | null
    last_pm_repair_id: number | null
    is_due: boolean
    days_since_pm: number | null
    days_overdue: number | null
    pm_threshold_months: number
  }>
  trucks?: DashboardVehicleAggregate
  trailers?: DashboardVehicleAggregate
}

export interface OperationalMetrics {
  miles_driven: number
  post_dispatch_revenue: number
  settlement_expenses: number
  repair_costs: number
  raw_gross_revenue: number
  raw_gross_miles_driven: number
  post_dispatch_revenue_per_mile: number | null
  raw_gross_revenue_per_mile: number | null
  settlement_cost_per_mile: number | null
  all_in_cost_per_mile: number | null
}

export interface DashboardVehicleAggregate {
  total_revenue: number
  total_expenses: number
  net_profit: number
  expense_categories?: DashboardData['expense_categories']
  custom_descriptions?: { [key: string]: string }
  operational_metrics?: OperationalMetrics
  truck_profits?: DashboardData['truck_profits']
  trailer_profits?: DashboardData['truck_profits']
}

export interface PMStatus {
  truck_id: number
  truck_name: string
  vin?: string | null
  last_pm_date: string | null
  last_pm_miles: number | null
  current_miles: number | null
  last_pm_repair_id: number | null
  is_due: boolean
  pm_method?: 'mileage' | 'time' | null
  // Mileage-based fields
  miles_since_pm: number | null
  miles_overdue: number | null
  miles_until_due: number | null
  next_pm_miles: number | null
  pm_threshold_miles: number
  // Time-based fields (fallback)
  days_since_pm: number | null
  days_overdue: number | null
  days_until_due: number | null
  next_pm_date: string | null
  pm_threshold_days: number
  pm_threshold_months?: number  // Legacy field for backward compatibility
}

export interface PMStatusResponse {
  pm_status: PMStatus[]
}

// Auth API (no tenant header)
export const authApi = {
  login: (username: string, password: string, remember: boolean, mfaCode?: string) =>
    axios.post<{ mfa_required?: boolean }>('/api/auth/login', { username, password, remember, mfa_code: mfaCode }, { withCredentials: true }),
  logout: () => axios.post('/api/auth/logout', {}, { withCredentials: true }),
  me: () => axios.get<{ username: string }>('/api/auth/me', { withCredentials: true }),
  capabilities: () => axios.get<{ password_recovery: boolean; recovery_email_hint: string | null }>('/api/auth/capabilities'),
  requestReset: (email: string) => axios.post('/api/auth/password/reset-request', { email }),
  resetPassword: (token: string, password: string) => axios.post('/api/auth/password/reset', { token, password }),
  changePassword: (currentPassword: string, newPassword: string) => axios.post<{ message: string }>('/api/auth/password/change', { current_password: currentPassword, new_password: newPassword }, { withCredentials: true }),
  recoveryEmail: () => axios.get<{ email: string; pending_email_hint: string | null }>('/api/auth/recovery-email', { withCredentials: true }),
  requestRecoveryEmailChange: (currentPassword: string, newEmail: string) => axios.post<{ message: string }>('/api/auth/recovery-email/change-request', { current_password: currentPassword, new_email: newEmail }, { withCredentials: true }),
  confirmRecoveryEmail: (token: string) => axios.post<{ message: string }>('/api/auth/recovery-email/confirm', { token }),
  mfaStatus: () => axios.get<{ enabled: boolean }>('/api/auth/mfa', { withCredentials: true }),
  mfaSetup: (password: string) => axios.post<{ secret: string; uri: string }>('/api/auth/mfa/setup', { password }, { withCredentials: true }),
  mfaConfirm: (code: string) => axios.post<{ recovery_codes: string[] }>('/api/auth/mfa/confirm', { code }, { withCredentials: true }),
}

// Truck API (also handles trailers and SUVs)
export const trucksApi = {
  investmentProgress: (id:number, as_of:string) => api.get(`/trucks/${id}/investment-progress`,{params:{as_of}}),
  previewInvestment: (id: number, plan: Record<string, unknown>) => api.post<Record<string, string | number | null>>(id ? `/trucks/${id}/investment-plan/preview` : '/trucks/investment-preview', plan),
  saveInvestment: (id: number, plan: Record<string, unknown>) => api.post(`/trucks/${id}/investment-plan`, plan),
  getAll: (vehicleType?: 'truck' | 'trailer' | 'suv') => {
    const params = vehicleType ? { vehicle_type: vehicleType } : {}
    return api.get<Truck[]>('/trucks', { params })
  },
  getById: (id: number) => api.get<Truck>(`/trucks/${id}`),
  getDocuments: (id: number) => api.get<VehicleDocument[]>(`/trucks/${id}/documents`),
  uploadDocument: (id: number, payload: {
    file: File
    document_type: VehicleDocument['document_type']
    title?: string
    notes?: string
  }) => {
    const formData = new FormData()
    formData.append('file', payload.file)
    formData.append('document_type', payload.document_type)
    if (payload.title) {
      formData.append('title', payload.title)
    }
    if (payload.notes) {
      formData.append('notes', payload.notes)
    }
    return formDataApi.post<VehicleDocument>(`/trucks/${id}/documents`, formData)
  },
  deleteDocument: (truckId: number, documentId: number) =>
    api.delete(`/trucks/${truckId}/documents/${documentId}`),
  create: (data: Partial<Truck>) =>
    api.post<Truck>('/trucks', data),
  update: (id: number, data: Partial<Truck>) =>
    api.put<Truck>(`/trucks/${id}`, data),
  delete: (id: number) => api.delete(`/trucks/${id}`),
}

// Settlement API
export const settlementsApi = {
  getAll: (truckId?: number, skip?: number, limit?: number, search?: string) => {
    const params: Record<string, string | number | boolean> = {}
    if (truckId) params.truck_id = truckId
    if (skip !== undefined) params.skip = skip
    if (limit !== undefined) params.limit = limit
    if (search && search.trim()) params.search = search.trim()
    return api.get<Settlement[]>('/settlements', { params })
  },
  getById: (id: number) => api.get<Settlement>(`/settlements/${id}`),
  create: (data: Partial<Settlement>) =>
    api.post<Settlement>('/settlements', data),
  update: (id: number, data: Partial<Settlement>) => {
    // Always use form data because the backend endpoint expects it when File/Form params exist
    const formData = new FormData()
    formData.append('settlement_update_json', JSON.stringify(data))
    return formDataApi.put<Settlement>(`/settlements/${id}`, formData)
  },
  updateWithPdf: (id: number, data: Partial<Settlement>, pdfFile?: File) => {
    const formData = new FormData()
    formData.append('settlement_update_json', JSON.stringify(data))
    if (pdfFile) {
      formData.append('pdf_file', pdfFile)
    }
    return formDataApi.put<Settlement>(`/settlements/${id}`, formData)
  },
  preview: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return formDataApi.post<{
      parsed: Partial<Settlement>
      suggested_truck: { id: number; name: string } | null
      warnings: string[]
    }>('/settlements/preview', formData)
  },
  upload: (
    file: File,
    truckId?: number,
    settlementType?: string,
    trailerIncomeSplitTrailerId?: number,
    trailerIncomeSplitAmount?: number,
    repairReserveAmount?: number,
  ) => {
    const formData = new FormData()
    formData.append('file', file)
    if (truckId !== undefined) {
      formData.append('truck_id', truckId.toString())
    }
    if (settlementType) {
      formData.append('settlement_type', settlementType)
    }
    if (trailerIncomeSplitTrailerId !== undefined) {
      formData.append('trailer_income_split_trailer_id', trailerIncomeSplitTrailerId.toString())
    }
    if (trailerIncomeSplitAmount !== undefined) {
      formData.append('trailer_income_split_amount', trailerIncomeSplitAmount.toString())
    }
    if (repairReserveAmount !== undefined) {
      formData.append('repair_reserve_amount', repairReserveAmount.toString())
    }
    return formDataApi.post<Settlement>(`/settlements/upload`, formData)
  },
  uploadBulk: (files: File[], truckId?: number, settlementType?: string) => {
    const formData = new FormData()
    files.forEach((file) => {
      formData.append('files', file)
    })
    if (truckId !== undefined) {
      formData.append('truck_id', truckId.toString())
    }
    if (settlementType) {
      formData.append('settlement_type', settlementType)
    }
    return formDataApi.post<{
      total: number
      successful: number
      failed: number
      results: Array<{
        filename: string
        success: boolean
        settlement?: Settlement
        error?: string
      }>
    }>(`/settlements/upload-bulk`, formData)
  },
  delete: (id: number) => api.delete(`/settlements/${id}`),
  uploadConsolidated: (jsonData: string, dryRun: boolean = false) => {
    const formData = new FormData()
    formData.append('json_data', jsonData)
    formData.append('dry_run', dryRun.toString())
    return formDataApi.post<{
      settlements?: Settlement[]
      summary: {
        total_entries: number
        created?: number
        updated?: number
        would_create?: number
        would_update?: number
        skipped?: number
        would_skip?: number
        errors: number
        error_details?: string[]
        dry_run?: boolean
      }
    }>('/settlements/upload-consolidated', formData)
  },
}

// Repair API
export const repairsApi = {
  getAll: (truckId?: number) => {
    const params = truckId ? { truck_id: truckId } : {}
    return api.get<Repair[]>('/repairs', { params })
  },
  getById: (id: number) => api.get<Repair>(`/repairs/${id}`),
  create: (data: Partial<Repair>, images?: File[]) => {
    const formData = new FormData()
    
    // Clean data - remove undefined values before stringifying
    const cleanedData: Record<string, unknown> = {}
    Object.keys(data).forEach(key => {
      const value = data[key as keyof Repair]
      if (value !== undefined && value !== null && value !== '') {
        cleanedData[key] = value
      }
    })
    
    formData.append('repair_json', JSON.stringify(cleanedData))
    if (images && images.length > 0) {
      images.forEach((img) => {
        formData.append('images', img)
      })
    }
    
    // Use shared FormData axios instance (no default Content-Type header)
    return formDataApi.post<Repair>('/repairs/', formData)
  },
  upload: (file: File, images: File[], truckId?: number) => {
    const formData = new FormData()
    formData.append('file', file)
    images.forEach((img) => {
      formData.append('images', img)
    })
    if (truckId !== undefined) {
      formData.append('truck_id', truckId.toString())
    }
    return formDataApi.post<{
      repair: Repair | null
      warning?: string
      vin_found?: boolean
      vin?: string
      requires_truck_selection?: boolean
    }>(`/repairs/upload`, formData)
  },
  update: (id: number, data: Partial<Repair>, images?: File[]) => {
    const formData = new FormData()
    
    // Add repair data as JSON string (backend will parse it)
    formData.append('repair_update_json', JSON.stringify(data))
    
    // Add images if provided
    if (images && images.length > 0) {
      images.forEach((img) => {
        formData.append('images', img)
      })
    }
    
    return formDataApi.put<Repair>(`/repairs/${id}`, formData)
  },
  delete: (id: number) => api.delete(`/repairs/${id}`),
  deleteImage: (repairId: number, imageIndex: number) => 
    api.delete(`/repairs/${repairId}/images/${imageIndex}`),
}

export const reserveApi = {
  getBalance: (truckId: number) =>
    api.get<ReserveBalance>(`/trucks/${truckId}/reserve-balance`),
  getLedger: (truckId: number, params?: { from?: string; to?: string }) =>
    api.get<ReserveLedgerEntry[]>(`/trucks/${truckId}/reserve-ledger`, { params }),
  getAllBalances: () =>
    api.get<ReserveBalance[]>('/reserve-balances'),
}

export interface TimeSeriesPeriod {
  service_on_truck?: number
  total_expenses?: number
  settlement_count?: number
  settlements?: TimeSeriesData['by_month'][number]['settlements']

  week_key?: string
  week_label?: string
  week_start?: string | null
  week_end?: string | null
  month_key?: string
  month_label?: string
  year_key?: string
  year_label?: string
  gross_revenue: number
  raw_gross_revenue: number
  raw_gross_miles_driven: number
  miles_driven: number
  net_profit: number
  expenses?: number
  trailer_income_split_amount?: number
  repair_reserve_amount?: number
  driver_pay: number
  payroll_fee: number
  fuel: number
  tolls: number
  dispatch_fee: number
  deduct: number
  fleet_manager_support: number
  insurance: number
  safety: number
  prepass: number
  ifta: number
  loan_interest: number
  truck_parking: number
  custom: number
  diesel_price_per_gallon?: number | null
  repairs?: number
  custom_descriptions?: { [key: string]: string }  // Descriptions for custom expense categories
  trucks?: Array<{ truck_id: number; truck_name: string }>
  settlement_types?: string[]
}

export interface TimeSeriesData {
  by_week: Array<{
    week_key: string
    week_label: string
    week_start?: string | null
    week_end?: string | null
    gross_revenue: number
    raw_gross_revenue: number
    raw_gross_miles_driven: number
    miles_driven: number
    net_profit: number
    driver_pay: number
    expenses: number
    trailer_income_split_amount?: number
    repair_reserve_amount?: number
    payroll_fee: number
    fuel: number
    tolls: number
    dispatch_fee: number
    deduct: number
    fleet_manager_support: number
    insurance: number
    safety: number
    prepass: number
    ifta: number
    loan_interest: number
    truck_parking: number
    custom: number
    diesel_price_per_gallon?: number | null
    custom_descriptions?: { [key: string]: string }  // Descriptions for custom expense categories
    trucks: Array<{ truck_id: number; truck_name: string }>
    settlement_types?: string[]
  }>
  by_month: Array<{
    month_key: string
    month_label: string
    gross_revenue: number
    raw_gross_revenue: number
    raw_gross_miles_driven: number
    miles_driven: number
    net_profit: number
    expenses: number
    trailer_income_split_amount?: number
    repair_reserve_amount?: number
    driver_pay: number
    payroll_fee: number
    fuel: number
    tolls: number
    dispatch_fee: number
    deduct: number
    fleet_manager_support: number
    insurance: number
    safety: number
    prepass: number
    ifta: number
    loan_interest: number
    truck_parking: number
    custom: number
    diesel_price_per_gallon?: number | null
    custom_descriptions?: { [key: string]: string }  // Descriptions for custom expense categories
    trucks: Array<{ truck_id: number; truck_name: string }>
    settlement_types?: string[]
    settlement_count?: number
    settlements?: Array<{
      settlement_id: number
      settlement_date: string | null
      week_start: string | null
      truck_id: number
      truck_name: string
      insurance: number
      driver_pay: number
    }>
  }>
  by_year: Array<{
    year_key: string
    year_label: string
    gross_revenue: number
    raw_gross_revenue: number
    raw_gross_miles_driven: number
    miles_driven: number
    net_profit: number
    expenses: number
    trailer_income_split_amount?: number
    repair_reserve_amount?: number
    driver_pay: number
    payroll_fee: number
    fuel: number
    tolls: number
    dispatch_fee: number
    deduct: number
    fleet_manager_support: number
    insurance: number
    safety: number
    prepass: number
    ifta: number
    loan_interest: number
    truck_parking: number
    custom: number
    diesel_price_per_gallon?: number | null
    repairs?: number
    custom_descriptions?: { [key: string]: string }  // Descriptions for custom expense categories
    trucks: Array<{ truck_id: number; truck_name: string }>
    settlement_types?: string[]
  }>
}

// Analytics API
export const analyticsApi = {
  getDashboard: (truckId?: number, vehicleType?: 'truck' | 'trailer') => {
    const params: Record<string, string | number | boolean> = {}
    if (truckId) params.truck_id = truckId
    if (vehicleType) params.vehicle_type = vehicleType
    return api.get<DashboardData>('/analytics/dashboard', { params })
  },
  getTruckProfit: (truckId: number) =>
    api.get<{
      truck_id: number
      settlements_total: number
      repairs_total: number
      net_profit: number
    }>(`/analytics/truck-profit/${truckId}`),
  getVehicleROI: (vehicleId: number) =>
    api.get<VehicleROI>(`/analytics/vehicle/${vehicleId}/roi`),
  getTimeSeries: (
    groupBy?: 'week_start' | 'settlement_date',
    truckId?: number,
    vehicleType?: 'truck' | 'trailer',
    includeDiesel?: boolean,
  ) => {
    const params: Record<string, string | number | boolean> = {}
    if (groupBy) params.group_by = groupBy
    if (truckId) params.truck_id = truckId
    if (vehicleType) params.vehicle_type = vehicleType
    if (includeDiesel) params.include_diesel = true
    return api.get<TimeSeriesData>('/analytics/time-series', { params })
  },
  getPMStatus: () =>
    api.get<PMStatusResponse>('/analytics/pm-status'),
}

// Accounting types
export interface ChartOfAccount {
  id: number
  code: string
  name: string
  account_type: 'Asset' | 'Liability' | 'Equity' | 'Revenue' | 'Expense'
  parent_id?: number | null
  is_active: boolean
  created_at: string
}

export interface JournalEntryLine {
  id: number
  journal_entry_id: number
  account_id: number
  debit: number
  credit: number
  description?: string | null
  truck_id?: number | null
  created_at: string
}

export interface JournalEntry {
  id: number
  entry_date: string
  reference_type?: string | null
  reference_id?: number | null
  description?: string | null
  created_at: string
  lines: JournalEntryLine[]
}

export interface GeneralLedgerEntry {
  entry_date: string
  journal_entry_id: number
  account_code: string
  account_name: string
  description?: string | null
  debit: number
  credit: number
  running_balance: number
}

export interface GeneralLedger {
  account_id: number
  account_code: string
  account_name: string
  account_type: string
  start_balance: number
  end_balance: number
  entries: GeneralLedgerEntry[]
}

export interface BalanceSheet {
  as_of_date: string
  assets: {
    cash: number
    accounts_receivable: number
    vehicles: number
    accumulated_depreciation: number
    net_vehicles: number
    total: number
  }
  liabilities: {
    accounts_payable: number
    loans_payable: number
    total: number
  }
  equity: {
    owner_equity: number
    retained_earnings: number
    total: number
  }
  total_liabilities_and_equity: number
}

export interface IncomeStatement {
  start_date: string
  end_date: string
  truck_id?: number | null
  revenue: { [key: string]: number }
  total_revenue: number
  expenses: { [key: string]: number }
  total_expenses: number
  net_income: number
}

export interface BankAccount {
  bank_name: string
  account_number: string
  routing_number: string
  account_type?: string | null  // 'checking', 'savings', etc.
}

export interface BankAccountSummary {
  bank_name: string
  account_type?: string | null
  account_number_masked: string
  routing_number_masked: string
}

export type BankNumberField = 'account_number' | 'routing_number'

export interface Tenant {
  id: number
  name: string
  business_type: string  // 'logistics', 'tech', 'real_estate', etc.
  is_active: boolean
  ein?: string
  legal_name?: string
  address?: string
  city?: string
  state?: string
  zip_code?: string
  phone?: string
  email?: string
  bank_accounts?: BankAccountSummary[]
  notes?: string
  created_at: string
  updated_at?: string
}

export type TenantInput = Partial<Omit<Tenant, 'bank_accounts'>> & { bank_accounts?: BankAccount[] }

// Tenant API - these endpoints don't require tenant_id header
export const tenantsApi = {
  getTenants: () => {
    // Create a separate axios instance without the interceptor for tenant management
    const tempApi = axios.create({
      baseURL: '/api',
      headers: { 'Content-Type': 'application/json' }
    })
    return tempApi.get<Tenant[]>('/tenants')
  },
  getTenant: (tenantId: number) => api.get<Tenant>(`/tenants/${tenantId}`),
  createTenant: (tenant: TenantInput) =>
    api.post<Tenant>('/tenants', tenant),
  updateTenant: (tenantId: number, tenant: TenantInput) =>
    api.put<Tenant>(`/tenants/${tenantId}`, tenant),
  deleteTenant: (tenantId: number) => api.delete(`/tenants/${tenantId}`),
  getBankNumber: (tenantId: number, accountIndex: number, field: BankNumberField, action: 'show' | 'copy', signal: AbortSignal) =>
    api.post<{ value: string }>(`/tenants/${tenantId}/bank-details`, {
      action, account_index: accountIndex, field,
    }, { signal, headers: { 'X-Bank-Details-Action': action } }),
  getBankAccountsForEdit: (tenantId: number, signal: AbortSignal) =>
    api.post<{ bank_accounts: BankAccount[] }>(`/tenants/${tenantId}/bank-details`, { action: 'edit' }, {
      signal, headers: { 'X-Bank-Details-Action': 'edit' },
    }),
}

// Accounting API
export const accountingApi = {
  importIncomeCsv: (file: File, commit: boolean = false, incomeKeywords?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('commit', String(commit))
    if (incomeKeywords) {
      formData.append('income_keywords', incomeKeywords)
    }
    return formDataApi.post('/accounting/income/import-csv', formData)
  },
  importExpenseCsv: (file: File, commit: boolean = false) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('commit', String(commit))
    return formDataApi.post('/accounting/expenses/import-csv', formData)
  },
  initializeChartOfAccounts: () =>
    api.post<ChartOfAccount[]>('/accounting/chart-of-accounts/initialize'),
  resetChartOfAccounts: () =>
    api.delete<{ message: string }>('/accounting/chart-of-accounts/reset', { params: { confirm: 'CONFIRM_RESET' } }),
  getChartOfAccounts: (accountType?: string, isActive?: boolean, truckId?: number) => {
    const params: Record<string, string | number | boolean> = {}
    if (accountType) params.account_type = accountType
    if (isActive !== undefined) params.is_active = isActive
    if (truckId) params.truck_id = truckId
    return api.get<ChartOfAccount[]>('/accounting/chart-of-accounts', { params })
  },
  createChartOfAccount: (account: Omit<ChartOfAccount, 'id' | 'created_at'>) =>
    api.post<ChartOfAccount>('/accounting/chart-of-accounts', account),
  getChartOfAccount: (accountId: number) =>
    api.get<ChartOfAccount>(`/accounting/chart-of-accounts/${accountId}`),
  getJournalEntries: (startDate?: string, endDate?: string, referenceType?: string, referenceId?: number, truckId?: number) => {
    const params: Record<string, string | number | boolean> = {}
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    if (referenceType) params.reference_type = referenceType
    if (referenceId) params.reference_id = referenceId
    if (truckId) params.truck_id = truckId
    return api.get<JournalEntry[]>('/accounting/journal-entries', { params })
  },
  createJournalEntry: (entry: { entry_date: string; reference_type?: string; reference_id?: number; description?: string; lines: Array<{ account_id: number; debit: number; credit: number; description?: string; truck_id?: number }> }) =>
    api.post<JournalEntry>('/accounting/journal-entries', entry),
  getJournalEntry: (entryId: number) =>
    api.get<JournalEntry>(`/accounting/journal-entries/${entryId}`),
  getGeneralLedger: (accountId: number, startDate?: string, endDate?: string) => {
    const params: Record<string, string | number | boolean> = { account_id: accountId }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    return api.get<GeneralLedger>('/accounting/general-ledger', { params })
  },
  getBalanceSheet: (asOfDate?: string, truckId?: number) => {
    const params: Record<string, string | number | boolean> = {}
    if (asOfDate) params.as_of_date = asOfDate
    if (truckId) params.truck_id = truckId
    return api.get<BalanceSheet>('/accounting/balance-sheet', { params })
  },
  getIncomeStatement: (startDate: string, endDate: string, truckId?: number, source?: 'all' | 'csv_only' | 'app_only') => {
    const params: Record<string, string | number | boolean> = { start_date: startDate, end_date: endDate }
    if (truckId) params.truck_id = truckId
    if (source) params.source = source
    return api.get<IncomeStatement>('/accounting/income-statement', { params })
  },
  calculateDepreciation: (truckId: number, asOfDate?: string) => {
    const params: Record<string, string | number | boolean> = {}
    if (asOfDate) params.as_of_date = asOfDate
    return api.post(`/accounting/depreciation/calculate/${truckId}`, null, { params })
  },
  recordDepreciation: (truckId: number, entryDate?: string, description?: string) => {
    const params: Record<string, string | number | boolean> = {}
    if (entryDate) params.entry_date = entryDate
    if (description) params.description = description
    return api.post(`/accounting/depreciation/record/${truckId}`, null, { params })
  },
  recordDepreciationAll: (entryDate?: string) => {
    const params: Record<string, string | number | boolean> = {}
    if (entryDate) params.entry_date = entryDate
    return api.post('/accounting/depreciation/record-all', null, { params })
  },
  // Export methods
  exportJournalEntries: (format: 'csv' | 'excel', startDate?: string, endDate?: string, referenceType?: string, truckId?: number) => {
    const params: Record<string, string | number | boolean> = { format }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    if (referenceType) params.reference_type = referenceType
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/export/journal-entries', { params, responseType: 'blob' })
  },
  exportGeneralLedger: (accountId: number, format: 'csv' | 'excel', startDate?: string, endDate?: string) => {
    const params: Record<string, string | number | boolean> = { account_id: accountId, format }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    return api.get('/accounting/export/general-ledger', { params, responseType: 'blob' })
  },
  exportBalanceSheet: (format: 'pdf' | 'excel', asOfDate?: string) => {
    const params: Record<string, string | number | boolean> = { format }
    if (asOfDate) params.as_of_date = asOfDate
    return api.get('/accounting/export/balance-sheet', { params, responseType: 'blob' })
  },
  exportIncomeStatement: (format: 'pdf' | 'excel', startDate: string, endDate: string, truckId?: number) => {
    const params: Record<string, string | number | boolean> = { format, start_date: startDate, end_date: endDate }
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/export/income-statement', { params, responseType: 'blob' })
  },
  exportTrialBalance: (format: 'csv' | 'excel' | 'pdf', asOfDate?: string, truckId?: number) => {
    const params: Record<string, string | number | boolean> = { format }
    if (asOfDate) params.as_of_date = asOfDate
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/export/trial-balance', { params, responseType: 'blob' })
  },
  // Tax report methods
  getTaxYearSummary: (year: number, truckId?: number) => {
    const params: Record<string, string | number | boolean> = { year }
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/tax-year-summary', { params })
  },
  getScheduleC: (year: number, truckId?: number) => {
    const params: Record<string, string | number | boolean> = { year }
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/schedule-c', { params })
  },
  // Tax package export (ZIP with all reports)
  exportTaxPackage: (year: number) => {
    return api.get('/accounting/export/tax-package', { params: { year }, responseType: 'blob' })
  },
}

const draftHeaders = (tenantId: number) => ({ withCredentials: true, headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'reviewed-transfer' } })
const bankMonitorClient = axios.create({ baseURL: '/api', withCredentials: true })
bankMonitorClient.interceptors.response.use((response) => response, handleAuthFailure)
export const bankMonitorApi = {
  plaidDashboardUsage: (tenantId: number) => bankMonitorClient.get('/bank-monitor/plaid-dashboard-usage', { headers: { 'X-Tenant-ID': String(tenantId) } }),
  plaidUsage: (tenantId: number) => bankMonitorClient.get('/bank-monitor/plaid-usage', { headers: { 'X-Tenant-ID': String(tenantId) } }),
  transferReview: (tenantId: number) => bankMonitorClient.post('/bank-monitor/transfer-reviews', {}, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'review-bank-transfers' } }),
  createReviewedTransfers: (tenantId: number, id: number, routes: { from_last4: string; to_last4: string; amount_cents: number }[]) => bankMonitorClient.post(`/bank-monitor/transfer-reviews/${id}/drafts`, { routes }, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'create-reviewed-transfers' } }),
  draftHistoryMatch: (tenantId: number, id: string, evidence: unknown) => bankMonitorClient.post(`/bank-monitor/drafts/${id}/history-match`, evidence, draftHeaders(tenantId)),
  draftPlaidMatch: (tenantId: number, id: string, evidence: { confirm?: boolean; automatic?: boolean; source_evidence?: string; destination_evidence?: string }) => bankMonitorClient.post(`/bank-monitor/drafts/${id}/plaid-match`, evidence, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'verify-plaid-transfer' } }),
  cancelDraft: (tenantId: number, id: string) => bankMonitorClient.post(`/bank-monitor/drafts/${id}/cancel`, {}, draftHeaders(tenantId)),
  drafts: (tenantId: number) => bankMonitorClient.get('/bank-monitor/drafts', draftHeaders(tenantId)),
  createDraft: (tenantId: number, draft: unknown) => bankMonitorClient.post('/bank-monitor/drafts', draft, draftHeaders(tenantId)),
  prepareDraft: (tenantId: number, id: string) => bankMonitorClient.post(`/bank-monitor/drafts/${id}/prepare`, {}, draftHeaders(tenantId)),
  prepareChargeDraft: (tenantId: number, id: string) => bankMonitorClient.post(`/bank-monitor/drafts/${id}/prepare-charge`, {}, draftHeaders(tenantId)),
  draftOutcome: (tenantId: number, id: string, status: string) => bankMonitorClient.post(`/bank-monitor/drafts/${id}/outcome`, { status }, draftHeaders(tenantId)),
  retryDraft: (tenantId: number, id: string, confirmedNotSubmitted = false) => bankMonitorClient.post(`/bank-monitor/drafts/${id}/retry`, confirmedNotSubmitted ? { reason: 'confirmed_not_submitted', confirmed_not_submitted: true } : { reason: 'signed_out_before_form' }, draftHeaders(tenantId)),
  updateDraftBankDetails: (tenantId: number, id: string, details: { bank_state: 'posted' | 'pending'; bank_effective_date: string }) => bankMonitorClient.put(`/bank-monitor/drafts/${id}/bank-details`, details, draftHeaders(tenantId)),
  get: (tenantId: number) => bankMonitorClient.get('/bank-monitor', { headers: { 'X-Tenant-ID': String(tenantId) } }),
  verifyWorkerConnection: (tenantId: number) => bankMonitorClient.post('/bank-monitor/connection-checks', {}, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'verify-worker-bank-access' } }),
  providerLinkToken: (tenantId: number) => bankMonitorClient.post<{ link_token: string; attempt_id: string }>('/bank-monitor/provider/link-token', {}, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'start-provider-link' } }),
  providerUpdateToken: (tenantId: number) => bankMonitorClient.post<{ link_token: string }>('/bank-monitor/provider/update-link-token', {}, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'renew-provider-link' } }),
  providerRenewed: (tenantId: number) => bankMonitorClient.post('/bank-monitor/provider/renewed', {}, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'confirm-provider-renewal' } }),
  providerAccounts: (tenantId: number) => bankMonitorClient.get<{ accounts: { nickname: string; last4: string; kind: 'checking' | 'credit' }[] }>('/bank-monitor/provider/accounts', { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'discover-provider-accounts' } }),
  providerExchange: (tenantId: number, input: { link_token: string; attempt_id: string; public_token: string }) => bankMonitorClient.post('/bank-monitor/provider/exchange', input, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'finish-provider-link' } }),
  recordBrowserCheck: (tenantId: number, evidence: unknown) => bankMonitorClient.post('/bank-monitor/browser-checks', evidence, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'record-browser-check' } }),
  saveProfileSchedule: (tenantId: number, enabled: boolean) => bankMonitorClient.put('/bank-monitor/profile-schedule', { enabled }, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'save-settings' } }),
  save: (tenantId: number, rules: unknown) => bankMonitorClient.put('/bank-monitor', rules, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'save-settings' } }),
  runRepayment: (tenantId: number, evidence: unknown) => bankMonitorClient.post('/bank-monitor/repayment-runs', evidence, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'run-repayment-check' } }),
  createRepaymentDrafts: (tenantId: number, runId: number) => bankMonitorClient.post(`/bank-monitor/repayment-runs/${runId}/drafts`, {}, { headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'create-repayment-drafts' } }),
}

export const bankProfilesApi = {
  request: <T>(tenantId: number, path = '', method: 'get' | 'post' | 'put' = 'get', data?: unknown) => bankMonitorClient.request<T>({ url: `/bank-monitor/profiles${path}`, method, data, headers: { 'X-Tenant-ID': String(tenantId), 'X-Bank-Monitor-Action': 'manage-bank-profiles' } }),
}


export interface DieselBridgeInvoice {
  id: number
  invoice_id: string
  revision: string
  truck_id: number | null
  repair_id: number | null
  state: string
  review_reason: string
  invoice: { invoice_number?: string; vin?: string; total_amount?: string }
}
const dieselBridgeClient = axios.create({ baseURL: '/api/v1/accounting/dieselbridge', withCredentials: true })
dieselBridgeClient.interceptors.response.use(response => response, handleAuthFailure)
const dieselBridgeHeaders = (tenantId: number) => ({ headers: { 'X-Tenant-ID': String(tenantId) } })
export const dieselBridgeApi = {
  connections: (tenantId: number) => dieselBridgeClient.get('/connections', dieselBridgeHeaders(tenantId)),
  invoices: (tenantId: number, after = 0) => dieselBridgeClient.get<{ items: DieselBridgeInvoice[]; next_after: number | null }>('/invoices', { ...dieselBridgeHeaders(tenantId), params: { after } }),
  sync: (tenantId: number, slug: string, dryRun: boolean) => dieselBridgeClient.post(`/connections/${encodeURIComponent(slug)}/sync`, null, { ...dieselBridgeHeaders(tenantId), params: { dry_run: dryRun } }),
  accept: (tenantId: number, id: number, revision: string, note: string) => dieselBridgeClient.post(`/invoices/${id}/accept`, { revision, note, cost_treatment: 'repair_expense' }, dieselBridgeHeaders(tenantId)),
  pdf: (tenantId: number, id: number) => dieselBridgeClient.get<Blob>(`/invoices/${id}/pdf`, { ...dieselBridgeHeaders(tenantId), responseType: 'blob' }),
}

export interface DieselBridgeRepairHistoryService {
  repair_order_id: string
  order_number: string
  vehicle_id: string
  vin: string | null
  unit_number: string | null
  status: 'completed' | 'invoiced' | 'paid'
  description: string | null
  created_at: string
  work_completed_at: string | null
  service_date: string
  service_date_source: 'work_completed_at' | 'created_at_fallback'
  revision: string
}
export interface DieselBridgeRepairHistoryRow {
  id: number
  shop_id: string
  repair_order_id: string
  truck_id: number | null
  truck_name: string | null
  revision: string
  state: 'imported' | 'review_required' | 'source_unavailable'
  review_reason: string
  service: DieselBridgeRepairHistoryService | null
  legacy_repair_candidates: number[]
}
export interface DieselBridgeRepairHistoryPage {
  items: DieselBridgeRepairHistoryRow[]
  total: number
  next_after: number | null
}
export interface DieselBridgeRepairHistorySync {
  dry_run: boolean
  source_count: number
  matched: number
  review_required: number
  created: number
  updated: number
  unchanged: number
  source_unavailable: number
  legacy_candidate_count: number
  snapshot_id: string
}
export const dieselBridgeHistoryApi = {
  list: (tenantId: number, truckId?: number, after = 0) => dieselBridgeClient.get<DieselBridgeRepairHistoryPage>('/repair-history', {
    ...dieselBridgeHeaders(tenantId), params: { truck_id: truckId, after },
  }),
  sync: (tenantId: number, slug: string, dryRun: boolean) => dieselBridgeClient.post<DieselBridgeRepairHistorySync>(`/connections/${encodeURIComponent(slug)}/repair-history/sync`, null, {
    ...dieselBridgeHeaders(tenantId), params: { dry_run: dryRun },
  }),
}

export interface DieselBridgeFinancialPayment {
  id: number
  event_id: string
  amount: string
  paid_date: string
  payer: 'business' | 'owner' | 'card' | 'cash'
  reversed: boolean
  reserve_withdrawal_id: number | null
  source_attempt_id?: string | null
  source_attempt_revision?: string | null
}
export interface DieselBridgeReconciliationNote {
  date_treatment?: 'note_only' | 'confirmed_service_date' | 'source_default'
  source_revision?: string | null
  id: number
  note: string
  source_references: string[]
  confirmed_service_date: string | null
  original_invoice_date: string | null
  amount_discrepancy: string | null
  supersedes_note_id: number | null
  created_at: string
  author: string
  repair_order_id: string
}
export interface DieselBridgeReconciliationNoteInput {
  date_treatment?: 'note_only' | 'confirmed_service_date' | 'source_default'
  expected_source_revision?: string
  note: string
  source_references: string[]
  confirmed_service_date?: string
  original_invoice_date?: string
  amount_discrepancy?: string
  supersedes_note_id?: number
}
export interface DieselBridgeSourcePaymentAttempt {
  attempt_id: string
  revision: string
  rail: 'cash' | 'card' | 'zelle' | 'check' | 'ach' | 'fleet_payment'
  state: 'pending' | 'confirmed' | 'failed' | 'expired' | 'refunded' | 'reversed'
  principal_amount: string
  received_amount: string | null
  gross_received_amount: string | null
  applied_principal_amount: string
  applied_card_fee_amount: string
  applied_card_fee_tax_amount: string
  unapplied_amount: string
  confirmed_at: string | null
  actual_paid_date: string | null
  paid_date_basis: 'unknown' | 'explicit_verified_date'
}
export interface DieselBridgeSourceSettlement {
  settlement_id: string
  revision: string
  status: 'available' | 'review_required'
  review_reasons: string[]
  source_state: string
  principal_total: string
  max_card_fee: string
  max_card_fee_tax: string
  confirmed_principal: string
  pending_principal: string
  unapplied_credit: string
  refund_pending: string
  payments: DieselBridgeSourcePaymentAttempt[]
}
export interface DieselBridgeEquipmentAllocation {
  id: number
  asset_id: number
  work_equipment_type: 'truck' | 'trailer'
  interim_unit_allocation: number
  reason: string
  author: string
  created_at: string
  supersedes_id: number | null
}
export interface DieselBridgeFinancialState {
  temporary_replacements?: { id: number; reason: string; restored: boolean; repair_ids: number[] }[]
  equipment_allocation?: DieselBridgeEquipmentAllocation | null
  cost_asset_id?: number
  reconciliation_notes?: DieselBridgeReconciliationNote[]
  reconciliation_notes_has_older?: boolean
  link_id: number
  connection_slug: string
  repair_order_id: string
  order_number?: string
  invoice_id: string
  invoice_number: string
  revision: string
  state: 'active' | 'review_required' | 'access_removed'
  review_reason: string | null
  source_status: string
  invoice_total: string
  source_invoice_total?: string
  booked_cost?: string
  source_settlement?: DieselBridgeSourceSettlement | null
  source_payment_review_required?: boolean
  source_payment_review_reasons?: string[]
  source_obligation_amount?: string | null
  source_confirmed_amount?: string | null
  source_recorded_balance?: string | null
  source_claims?: { source_attempt_id: string; payment_id: number; reversed: boolean; source_attempt_revision: string }[]
  recorded_paid_amount: string
  recorded_balance_due: string
  payment_status: 'unconfirmed' | 'partial' | 'paid'
  payment_history_confirmed?: boolean
  bill_event_id: string | null
  payments: DieselBridgeFinancialPayment[]
  source_pdf_url: string | null
}
export interface DieselBridgeFinancialPreviewRow {
  date_decision?: DieselBridgeReconciliationNote | null
  equipment_allocation?: DieselBridgeEquipmentAllocation | null
  cost_asset_id?: number | null
  source_revision?: string | null
  repair_order_id: string
  order_number?: string
  truck_name?: string | null
  action: 'create' | 'unchanged' | 'review_required' | 'blocked'
  repair_id: number | null
  invoice_id: string | null
  invoice_total: string | null
  source_invoice_total?: string | null
  price_basis?: 'settlement_principal_plus_applied_card_fees' | 'fee_free_invoice' | 'unresolved'
  repair_date: string | null
  category: string | null
  blockers: string[]
}
export interface DieselBridgeFinancialPreview {
  version: string
  plan_digest: string
  source_manifest_digest: string
  local_state_digest: string
  source_count: number
  selected_count: number
  executable: boolean
  rows: DieselBridgeFinancialPreviewRow[]
  blockers: string[]
}
export interface DieselBridgeFinancialSync {
  created: number
  unchanged: number
  review_required: number
  blocked: number
  operation_id: number | string
  plan_digest: string
}
export interface DieselBridgeVerifiedPayment {
  source_attempt_id?: string
  source_attempt_revision?: string
  expected_revision: string
  amount: string
  paid_date: string
  payer: 'business' | 'owner' | 'card' | 'cash'
  transaction_id?: string
  evidence_id?: string
  owner_payment_confirmed?: boolean
  note?: string
}
export interface DieselBridgePaymentWorkspace {
  accounts: { id: string; name?: string; account_type: string }[]
  transactions: { id: string; account_id: string; date: string; amount: string; description?: string; matched: boolean }[]
}
export interface DieselBridgePaymentEvidence {
  id: string
  filename: string
  extraction_version?: string
  supersedes_id?: string | null
}
const dbnAccountingClient = axios.create({ baseURL: '/api/v1/accounting', withCredentials: true })
dbnAccountingClient.interceptors.response.use(response => response, handleAuthFailure)
export const dieselBridgeReconciliationApi = {
  appendSource: (tenantId: number, slug: string, repairOrderId: string, body: DieselBridgeReconciliationNoteInput, key: string) => dieselBridgeClient.post<DieselBridgeReconciliationNote>(`/connections/${encodeURIComponent(slug)}/repair-orders/${encodeURIComponent(repairOrderId)}/reconciliation-notes`, body, { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } }),
  list: (tenantId: number, repairId: number, after = 0) => dieselBridgeClient.get<{ items: DieselBridgeReconciliationNote[]; next_after: number | null }>(`/repairs/${repairId}/reconciliation-notes`, { ...dieselBridgeHeaders(tenantId), params: { limit: 100, after } }),
  append: (tenantId: number, repairId: number, body: DieselBridgeReconciliationNoteInput, key: string) => dieselBridgeClient.post<DieselBridgeReconciliationNote>(`/repairs/${repairId}/reconciliation-notes`, body, { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } }),
}
export interface DieselBridgeReplacementPlan {
  plan_digest: string
  correction_date: string
  expense_removed: string
  reserve_correction: string
  temporary_records: { repair: { id: string; title: string | null; description: string | null; repair_date: string | null; cost: string | null }; withdrawals: { id: string; amount: string; entry_date: string }[]; journals: { entry: { id: string; entry_date: string }; lines: { account_id: string; debit: string; credit: string }[] }[] }[]
}
export const dieselBridgeFinancialApi = {
  replacementCandidates: (tenantId: number, repairId: number) => dieselBridgeClient.get<{ items: { id: number; title: string; date: string | null; cost: string | null }[] }>(`/repairs/${repairId}/replacement-candidates`, dieselBridgeHeaders(tenantId)),
  replacementPreview: (tenantId: number, slug: string, body: { repair_order_id: string; legacy_repair_ids: number[]; correction_date: string }) => dieselBridgeClient.post<DieselBridgeReplacementPlan>(`/connections/${encodeURIComponent(slug)}/financial-import/archive-preview`, body, dieselBridgeHeaders(tenantId)),
  replacementApply: (tenantId: number, slug: string, body: Record<string, unknown>, key: string) => dieselBridgeClient.post(`/connections/${encodeURIComponent(slug)}/financial-import/archive-apply`, body, { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } }),
  replacementRestorePreview: (tenantId: number, slug: string, operationId: number, correctionDate: string) => dieselBridgeClient.post<{ plan_digest: string; original_operation: { plan: DieselBridgeReplacementPlan } }>(`/connections/${encodeURIComponent(slug)}/financial-import/replacements/${operationId}/restore-preview`, { correction_date: correctionDate }, dieselBridgeHeaders(tenantId)),
  replacementRestore: (tenantId: number, slug: string, operationId: number, body: Record<string, unknown>, key: string) => dieselBridgeClient.post(`/connections/${encodeURIComponent(slug)}/financial-import/replacements/${operationId}/restore`, body, { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } }),
  equipmentOptions: (tenantId: number) => dieselBridgeClient.get<{ items: { id: number; name: string; vehicle_type: 'truck' | 'trailer'; vin: string | null }[] }>('/equipment-options', dieselBridgeHeaders(tenantId)),
  allocateEquipment: (tenantId: number, slug: string, ro: string, body: { asset_id: number; expected_source_revision: string; work_equipment_type: 'truck' | 'trailer'; interim_unit_allocation: boolean; supersedes_id?: number; reason: string }, key: string) => dieselBridgeClient.post<DieselBridgeEquipmentAllocation>(`/connections/${encodeURIComponent(slug)}/repair-orders/${encodeURIComponent(ro)}/equipment-allocation`, body, { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } }),
  preview: (tenantId: number, slug: string) => dieselBridgeClient.post<DieselBridgeFinancialPreview>(`/connections/${encodeURIComponent(slug)}/financial-import/preview`, {}, dieselBridgeHeaders(tenantId)),
  sync: (tenantId: number, slug: string, expectedPlanDigest: string, key: string) => dieselBridgeClient.post<DieselBridgeFinancialSync>(`/connections/${encodeURIComponent(slug)}/financial-import/sync`, { expected_plan_digest: expectedPlanDigest }, { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } }),
  state: (tenantId: number, repairId: number) => dieselBridgeClient.get<DieselBridgeFinancialState>(`/repairs/${repairId}/financial-state`, dieselBridgeHeaders(tenantId)),
  payment: (tenantId: number, repairId: number, body: DieselBridgeVerifiedPayment, key: string) => dieselBridgeClient.post<DieselBridgeFinancialState>(`/repairs/${repairId}/verified-payments`, body, { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } }),
  reverse: (tenantId: number, repairId: number, paymentId: number, body: { reversal_date: string; reason: string; expected_revision: string }, key: string) => dieselBridgeClient.post<DieselBridgeFinancialState>(`/repairs/${repairId}/payments/${paymentId}/reverse`, body, { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } }),
  pdf: (tenantId: number, repairId: number) => dieselBridgeClient.get<Blob>(`/repairs/${repairId}/source-pdf`, { ...dieselBridgeHeaders(tenantId), responseType: 'blob' }),
  paymentOptions: (tenantId: number, asOf: string) => dbnAccountingClient.get<DieselBridgePaymentWorkspace>('/workspace', { ...dieselBridgeHeaders(tenantId), params: { as_of: asOf } }),
  paymentEvidence: async (tenantId: number) => {
    const items: DieselBridgePaymentEvidence[] = []
    const seen = new Set<string>()
    let cursor: string | null = null
    do {
      const response: { data: { items: DieselBridgePaymentEvidence[]; next_cursor: string | null } } = await dbnAccountingClient.get('/evidence', { ...dieselBridgeHeaders(tenantId), params: { limit: 500, cursor } })
      items.push(...response.data.items)
      cursor = response.data.next_cursor
      if (cursor && (seen.has(cursor) || seen.size >= 100)) throw new Error('Evidence list could not be completed.')
      if (cursor) seen.add(cursor)
    } while (cursor)
    return items
  },
}

export interface DieselBridgeSourceReview {
  review_digest: string
  action: 'replace_unpaid_invoice' | 'cancel_unpaid_invoice' | 'no_change' | 'blocked'
  can_apply: boolean
  before: { invoice_id: string; invoice_number: string; cost: string; repair_date: string | null; description?: string; category?: string }
  after: { invoice_id: string; invoice_number: string; cost: string; repair_date: string | null; description?: string; category?: string } | null
  recorded_paid_amount: string
  blockers: string[]
  candidate_pdf_url?: string | null
}
export const dieselBridgeSourceReviewApi = {
  pdf: (tenantId: number, repairId: number) => dieselBridgeClient.get<Blob>(`/repairs/${repairId}/source-review/pdf`, { ...dieselBridgeHeaders(tenantId), responseType: 'blob' }),
  preview: (tenantId: number, repairId: number, expectedRevision: string) => dieselBridgeClient.post<DieselBridgeSourceReview>(`/repairs/${repairId}/source-review/preview`, { expected_revision: expectedRevision }, dieselBridgeHeaders(tenantId)),
  apply: (tenantId: number, repairId: number, body: { expected_revision: string; expected_review_digest: string; note: string }, key: string) => dieselBridgeClient.post(`/repairs/${repairId}/source-review/apply`, body, { headers: { 'X-Tenant-ID': String(tenantId), 'Idempotency-Key': key } }),
}
