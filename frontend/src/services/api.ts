import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface Truck {
  id: number
  name: string
  license_plate?: string
  vin?: string
  license_plate_history?: string[]
}

export interface Settlement {
  id: number
  truck_id: number
  driver_id?: number
  settlement_date: string
  week_start?: string
  week_end?: string
  miles_driven?: number
  blocks_delivered?: number
  gross_revenue?: number
  expenses?: number
  expense_categories?: { [key: string]: number }
  net_profit?: number
  pdf_file_path?: string
  settlement_type?: string
  license_plate?: string
}

export interface Repair {
  id: number
  truck_id: number
  repair_date: string
  description: string
  cost: number
  category?: string
  invoice_number?: string
  receipt_path?: string
  image_paths?: string[]
}

export interface DashboardData {
  total_trucks: number
  total_settlements: number
  total_revenue: number
  total_expenses: number
  net_profit: number
  expense_categories?: {
    fuel: number
    dispatch_fee: number
    insurance: number
    safety: number
    prepass: number
    ifta: number
    driver_pay: number
    payroll_fee: number
    truck_parking: number
    repairs: number
    custom: number
  }
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
}

// Truck API
export const trucksApi = {
  getAll: () => api.get<Truck[]>('/trucks'),
  getById: (id: number) => api.get<Truck>(`/trucks/${id}`),
  create: (data: { name: string; license_plate?: string; vin?: string }) =>
    api.post<Truck>('/trucks', data),
  update: (id: number, data: { name?: string; license_plate?: string; vin?: string }) =>
    api.put<Truck>(`/trucks/${id}`, data),
  delete: (id: number) => api.delete(`/trucks/${id}`),
}

// Settlement API
export const settlementsApi = {
  getAll: (truckId?: number) => {
    const params = truckId ? { truck_id: truckId } : {}
    return api.get<Settlement[]>('/settlements', { params })
  },
  getById: (id: number) => api.get<Settlement>(`/settlements/${id}`),
  create: (data: Partial<Settlement>) =>
    api.post<Settlement>('/settlements', data),
  update: (id: number, data: Partial<Settlement>) =>
    api.put<Settlement>(`/settlements/${id}`, data),
  upload: (file: File, truckId?: number, settlementType?: string, extractOnly?: boolean, storePdfOnly?: boolean) => {
    const formData = new FormData()
    formData.append('file', file)
    if (truckId !== undefined) {
      formData.append('truck_id', truckId.toString())
    }
    if (settlementType) {
      formData.append('settlement_type', settlementType)
    }
    if (extractOnly !== undefined) {
      formData.append('extract_only', extractOnly.toString())
    }
    if (storePdfOnly !== undefined) {
      formData.append('store_pdf_only', storePdfOnly.toString())
    }
    return api.post<Settlement>(
      `/settlements/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )
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
    return api.post<{
      total: number
      successful: number
      failed: number
      results: Array<{
        filename: string
        success: boolean
        settlement?: Settlement
        error?: string
      }>
    }>(
      `/settlements/upload-bulk`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )
  },
  delete: (id: number) => api.delete(`/settlements/${id}`),
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
    return api.post<Repair>('/repairs', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
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
    return api.post<{
      repair: Repair | null
      warning?: string
      vin_found?: boolean
      vin?: string
      requires_truck_selection?: boolean
    }>(
      `/repairs/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )
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
    
    return api.put<Repair>(`/repairs/${id}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
  delete: (id: number) => api.delete(`/repairs/${id}`),
}

export interface TimeSeriesData {
  by_week: Array<{
    week_key: string
    week_label: string
    gross_revenue: number
    net_profit: number
    driver_pay: number
    payroll_fee: number
    fuel: number
    dispatch_fee: number
    insurance: number
    safety: number
    prepass: number
    ifta: number
    truck_parking: number
    custom: number
    trucks: Array<{ truck_id: number; truck_name: string }>
  }>
  by_month: Array<{
    month_key: string
    month_label: string
    gross_revenue: number
    net_profit: number
    driver_pay: number
    payroll_fee: number
    fuel: number
    dispatch_fee: number
    insurance: number
    safety: number
    prepass: number
    ifta: number
    truck_parking: number
    custom: number
    trucks: Array<{ truck_id: number; truck_name: string }>
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
    net_profit: number
    driver_pay: number
    payroll_fee: number
    fuel: number
    dispatch_fee: number
    insurance: number
    safety: number
    prepass: number
    ifta: number
    truck_parking: number
    custom: number
    repairs?: number
    trucks: Array<{ truck_id: number; truck_name: string }>
  }>
}

// Analytics API
export const analyticsApi = {
  getDashboard: (truckId?: number) => {
    const params = truckId ? { truck_id: truckId } : {}
    return api.get<DashboardData>('/analytics/dashboard', { params })
  },
  getTruckProfit: (truckId: number) =>
    api.get<{
      truck_id: number
      settlements_total: number
      repairs_total: number
      net_profit: number
    }>(`/analytics/truck-profit/${truckId}`),
  getTimeSeries: (groupBy?: 'week_start' | 'settlement_date', truckId?: number) => {
    const params: any = {}
    if (groupBy) params.group_by = groupBy
    if (truckId) params.truck_id = truckId
    return api.get<TimeSeriesData>('/analytics/time-series', { params })
  },
}
