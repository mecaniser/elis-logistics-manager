import axios from 'axios'

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
  if (config.url?.includes('/tenants') && config.method === 'get' && !config.url.match(/\/tenants\/\d+/)) {
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
api.interceptors.response.use((response) => response, (error) => {
  if (error.response?.status === 401) {
    window.location.href = '/login'
  }
  return Promise.reject(error)
})

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

formDataApi.interceptors.response.use((response) => response, (error) => {
  if (error.response?.status === 401) {
    window.location.href = '/login'
  }
  return Promise.reject(error)
})

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
  estimated_mpg?: number | null
  fuel_card_discount_per_gallon?: number | null
  license_plate_history?: string[]
  cash_investment?: number  // Cash invested in vehicle
  loan_amount?: number  // Loan amount for financed vehicles
  current_loan_balance?: number  // Current loan balance (reduces as principal is paid)
  loan_term_months?: number | null  // Original loan duration in months
  interest_rate?: number  // Annual interest rate (default 0.07 = 7%)
  total_cost?: number  // Total purchase cost (cash + loan + fees)
  registration_fee?: number  // Registration fee for vehicle
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

export interface DashboardData {
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
  login: (username: string, password: string) =>
    axios.post('/api/auth/login', { username, password }, { withCredentials: true }),
  logout: () => axios.post('/api/auth/logout', {}, { withCredentials: true }),
  me: () => axios.get<{ username: string }>('/api/auth/me', { withCredentials: true }),
}

// Truck API (also handles trailers and SUVs)
export const trucksApi = {
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
    const params: any = {}
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
    const cleanedData: any = {}
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
    const params: Record<string, any> = {}
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
    const params: any = {}
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
  account_type?: string  // 'checking', 'savings', etc.
}

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
  bank_accounts?: BankAccount[]
  notes?: string
  created_at: string
  updated_at?: string
}

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
  createTenant: (tenant: Partial<Tenant>) =>
    api.post<Tenant>('/tenants', tenant),
  updateTenant: (tenantId: number, tenant: Partial<Tenant>) =>
    api.put<Tenant>(`/tenants/${tenantId}`, tenant),
  deleteTenant: (tenantId: number) => api.delete(`/tenants/${tenantId}`),
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
    const params: Record<string, any> = {}
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
    const params: Record<string, any> = {}
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
    const params: Record<string, any> = { account_id: accountId }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    return api.get<GeneralLedger>('/accounting/general-ledger', { params })
  },
  getBalanceSheet: (asOfDate?: string, truckId?: number) => {
    const params: Record<string, any> = {}
    if (asOfDate) params.as_of_date = asOfDate
    if (truckId) params.truck_id = truckId
    return api.get<BalanceSheet>('/accounting/balance-sheet', { params })
  },
  getIncomeStatement: (startDate: string, endDate: string, truckId?: number, source?: 'all' | 'csv_only' | 'app_only') => {
    const params: Record<string, any> = { start_date: startDate, end_date: endDate }
    if (truckId) params.truck_id = truckId
    if (source) params.source = source
    return api.get<IncomeStatement>('/accounting/income-statement', { params })
  },
  calculateDepreciation: (truckId: number, asOfDate?: string) => {
    const params: Record<string, any> = {}
    if (asOfDate) params.as_of_date = asOfDate
    return api.post(`/accounting/depreciation/calculate/${truckId}`, null, { params })
  },
  recordDepreciation: (truckId: number, entryDate?: string, description?: string) => {
    const params: Record<string, any> = {}
    if (entryDate) params.entry_date = entryDate
    if (description) params.description = description
    return api.post(`/accounting/depreciation/record/${truckId}`, null, { params })
  },
  recordDepreciationAll: (entryDate?: string) => {
    const params: Record<string, any> = {}
    if (entryDate) params.entry_date = entryDate
    return api.post('/accounting/depreciation/record-all', null, { params })
  },
  // Export methods
  exportJournalEntries: (format: 'csv' | 'excel', startDate?: string, endDate?: string, referenceType?: string, truckId?: number) => {
    const params: Record<string, any> = { format }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    if (referenceType) params.reference_type = referenceType
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/export/journal-entries', { params, responseType: 'blob' })
  },
  exportGeneralLedger: (accountId: number, format: 'csv' | 'excel', startDate?: string, endDate?: string) => {
    const params: Record<string, any> = { account_id: accountId, format }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    return api.get('/accounting/export/general-ledger', { params, responseType: 'blob' })
  },
  exportBalanceSheet: (format: 'pdf' | 'excel', asOfDate?: string) => {
    const params: Record<string, any> = { format }
    if (asOfDate) params.as_of_date = asOfDate
    return api.get('/accounting/export/balance-sheet', { params, responseType: 'blob' })
  },
  exportIncomeStatement: (format: 'pdf' | 'excel', startDate: string, endDate: string, truckId?: number) => {
    const params: Record<string, any> = { format, start_date: startDate, end_date: endDate }
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/export/income-statement', { params, responseType: 'blob' })
  },
  exportTrialBalance: (format: 'csv' | 'excel' | 'pdf', asOfDate?: string, truckId?: number) => {
    const params: Record<string, any> = { format }
    if (asOfDate) params.as_of_date = asOfDate
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/export/trial-balance', { params, responseType: 'blob' })
  },
  // Tax report methods
  getTaxYearSummary: (year: number, truckId?: number) => {
    const params: Record<string, any> = { year }
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/tax-year-summary', { params })
  },
  getScheduleC: (year: number, truckId?: number) => {
    const params: Record<string, any> = { year }
    if (truckId) params.truck_id = truckId
    return api.get('/accounting/schedule-c', { params })
  },
  // Tax package export (ZIP with all reports)
  exportTaxPackage: (year: number) => {
    return api.get('/accounting/export/tax-package', { params: { year }, responseType: 'blob' })
  },
}
