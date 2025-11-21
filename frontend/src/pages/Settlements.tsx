import { useEffect, useState } from 'react'
import { settlementsApi, trucksApi, Settlement, Truck } from '../services/api'
import Modal from '../components/Modal'
import ConfirmModal from '../components/ConfirmModal'
import Toast from '../components/Toast'

export default function Settlements() {
  const [settlements, setSettlements] = useState<Settlement[]>([])
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTruck] = useState<number | null>(null)
  const [showUploadForm, setShowUploadForm] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalMessage, setModalMessage] = useState<string | React.ReactNode>('')
  const [modalType, setModalType] = useState<'success' | 'error' | 'warning' | 'info'>('info')
  const [settlementToDelete, setSettlementToDelete] = useState<number | null>(null)
  const [selectedSettlements, setSelectedSettlements] = useState<Set<number>>(new Set())
  const [deleteMode, setDeleteMode] = useState(false)
  const [selectedTruckForUpload, setSelectedTruckForUpload] = useState<number | null>(null)
  const [showManualForm, setShowManualForm] = useState(false)
  const [manualFormData, setManualFormData] = useState<Partial<Settlement>>({
    truck_id: undefined,
    settlement_date: new Date().toISOString().split('T')[0],
    gross_revenue: undefined,
    expenses: undefined,
    net_profit: undefined,
  })
  const [expensesDescription, setExpensesDescription] = useState<string>('')
  const [vinLookup, setVinLookup] = useState<string>('')
  const [creatingManual, setCreatingManual] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [editingSettlement, setEditingSettlement] = useState<Settlement | null>(null)
  const [editFormData, setEditFormData] = useState<Partial<Settlement>>({})
  const [originalFormData, setOriginalFormData] = useState<Partial<Settlement>>({})
  const [expenseCategoryInputs, setExpenseCategoryInputs] = useState<{ [key: string]: string }>({})
  const [categoryNameInputs, setCategoryNameInputs] = useState<{ [key: string]: string }>({})
  const [dispatchFeePercent, setDispatchFeePercent] = useState<6 | 8 | 10>(6)
  const [grossRevenueInput, setGrossRevenueInput] = useState<string>('')
  const [totalExpensesInput, setTotalExpensesInput] = useState<string>('')
  const [netProfitInput, setNetProfitInput] = useState<string>('')
  const [isNavigating, setIsNavigating] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean }>({
    message: '',
    type: 'info',
    isVisible: false
  })
  

  // Standard expense categories that should always be displayed
  const STANDARD_EXPENSE_CATEGORIES = [
    'fuel',
    'dispatch_fee',
    'insurance',
    'safety',
    'prepass',
    'ifta',
    'driver_pay',
    'payroll_fee',
    'truck_parking',
    'service_on_truck'
  ]

  // Color codes for expense categories
  const getCategoryColor = (category: string) => {
    const colorMap: { [key: string]: { bg: string; border: string; text: string } } = {
      fuel: { bg: 'bg-red-50', border: 'border-red-300', text: 'text-red-700' },
      dispatch_fee: { bg: 'bg-blue-50', border: 'border-blue-300', text: 'text-blue-700' },
      insurance: { bg: 'bg-green-50', border: 'border-green-300', text: 'text-green-700' },
      safety: { bg: 'bg-yellow-50', border: 'border-yellow-300', text: 'text-yellow-700' },
      prepass: { bg: 'bg-purple-50', border: 'border-purple-300', text: 'text-purple-700' },
      ifta: { bg: 'bg-indigo-50', border: 'border-indigo-300', text: 'text-indigo-700' },
      driver_pay: { bg: 'bg-pink-50', border: 'border-pink-300', text: 'text-pink-700' },
      payroll_fee: { bg: 'bg-orange-50', border: 'border-orange-300', text: 'text-orange-700' },
      truck_parking: { bg: 'bg-teal-50', border: 'border-teal-300', text: 'text-teal-700' },
      service_on_truck: { bg: 'bg-cyan-50', border: 'border-cyan-300', text: 'text-cyan-700' },
    }
    return colorMap[category] || { bg: 'bg-gray-50', border: 'border-gray-300', text: 'text-gray-700' }
  }

  useEffect(() => {
    loadTrucks()
    loadSettlements()
  }, [])

  useEffect(() => {
    loadSettlements()
  }, [selectedTruck])

  const loadTrucks = async () => {
    try {
      const response = await trucksApi.getAll()
      setTrucks(Array.isArray(response.data) ? response.data : [])
    } catch (err) {
      console.error(err)
      setTrucks([])
    }
  }

  const loadSettlements = async () => {
    try {
      setLoading(true)
      const response = await settlementsApi.getAll(selectedTruck || undefined)
      const newSettlements = Array.isArray(response.data) ? response.data : []
      setSettlements(newSettlements)
      
      // Clear selections if any selected IDs don't exist in the new settlements
      const newSettlementIds = new Set(newSettlements.map(s => s.id))
      const validSelections = Array.from(selectedSettlements).filter(id => newSettlementIds.has(id))
      if (validSelections.length !== selectedSettlements.size) {
        setSelectedSettlements(new Set(validSelections))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load settlements')
      setSettlements([])
    } finally {
      setLoading(false)
    }
  }

  const showModal = (title: string, message: string | React.ReactNode, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
    setModalTitle(title)
    setModalMessage(message)
    setModalType(type)
    setModalOpen(true)
  }

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadFile) {
      showToast('Please select a file to upload', 'error')
      return
    }

    try {
      setUploading(true)
      // Settlement type is optional - backend will use default parser
      await settlementsApi.upload(uploadFile, selectedTruckForUpload || undefined, undefined)
      showToast('Settlement uploaded successfully! PDF stored in Cloud and data imported.', 'success')
      
      setUploadFile(null)
      setSelectedTruckForUpload(null)
      setShowUploadForm(false)
      setSelectedSettlements(new Set()) // Clear any selected settlements
      loadSettlements()
    } catch (err: any) {
      console.error('Upload error:', err)
      const errorMessage = err.response?.data?.detail || err.response?.data?.message || err.message || 'Failed to upload settlement'
      showToast(errorMessage, 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async () => {
    if (!settlementToDelete) return
    try {
      await settlementsApi.delete(settlementToDelete)
      showToast('Settlement deleted successfully!', 'success')
      setSettlementToDelete(null)
      loadSettlements()
    } catch (err: any) {
      showToast(err.response?.data?.detail || err.message || 'Failed to delete settlement', 'error')
      setSettlementToDelete(null)
    }
  }

  const handleBulkDelete = async () => {
    if (selectedSettlements.size === 0) return
    
    try {
      const deletePromises = Array.from(selectedSettlements).map(async (id) => {
        try {
          await settlementsApi.delete(id)
          return { id, success: true }
        } catch (err: any) {
          return { 
            id, 
            success: false, 
            error: err.response?.data?.detail || err.message || 'Unknown error' 
          }
        }
      })
      
      const results = await Promise.all(deletePromises)
      const successful = results.filter(r => r.success).length
      const failed = results.filter(r => !r.success)
      
      if (failed.length > 0) {
        const errorMessages = failed.map(f => `Settlement ${f.id}: ${f.error}`).join(', ')
        showToast(`Deleted ${successful} of ${selectedSettlements.size} settlement(s). Errors: ${errorMessages}`, 'warning')
      } else {
        showToast(`Successfully deleted ${successful} settlement(s)!`, 'success')
      }
      
      setSelectedSettlements(new Set())
      setSettlementToDelete(null)
      setDeleteMode(false)
      loadSettlements()
    } catch (err: any) {
      showModal('Error', err.response?.data?.detail || err.message || 'Failed to delete settlements', 'error')
      setSettlementToDelete(null)
    }
  }

  const handleSelectSettlement = (id: number) => {
    const newSelected = new Set(selectedSettlements)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedSettlements(newSelected)
  }

  const handleSelectAll = () => {
    if (!Array.isArray(settlements)) return
    if (selectedSettlements.size === settlements.length) {
      // Deselect all - this will hide the delete button
      setSelectedSettlements(new Set())
    } else {
      // Select all - this will show the delete button
      setSelectedSettlements(new Set(settlements.map(s => s.id)))
    }
  }

  const getTruckName = (truckId: number) => {
    const truck = trucks.find((t) => t.id === truckId)
    return truck?.name || `Truck ${truckId}`
  }

  const getPdfUrl = (pdfPath: string) => {
    if (!pdfPath) return ''
    if (pdfPath.startsWith('http')) return pdfPath
    
    // Handle different path formats:
    // - Full path: "uploads/1234567890_filename.pdf"
    // - Relative path: "1234567890_filename.pdf"
    // - Just filename: "filename.pdf"
    let filename = pdfPath
    
    // Remove "uploads/" prefix if present
    if (pdfPath.startsWith('uploads/')) {
      filename = pdfPath.replace('uploads/', '')
    } else if (pdfPath.includes('/')) {
      // Extract filename from path
      filename = pdfPath.split('/').pop() || pdfPath
    }
    
    // Validate filename has proper extension
    if (!filename.includes('.') || filename.length < 5) {
      console.warn('Invalid PDF path:', pdfPath)
      return ''
    }
    
    return `/uploads/${encodeURIComponent(filename)}`
  }

  // Helper function to get description from custom_expense_descriptions
  const getCustomDescription = (key: string): string => {
    if (key === 'custom') return ''
    if (editFormData.custom_expense_descriptions && editFormData.custom_expense_descriptions[key]) {
      return editFormData.custom_expense_descriptions[key]
    }
    // Fallback: try to extract from key for backward compatibility
    if (key.startsWith('custom_')) {
      return key.replace('custom_', '').split('_').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1)
      ).join(' ')
    }
    return ''
  }
  
  // Helper function to generate unique custom key
  const generateCustomKey = (): string => {
    const currentCategories = editFormData.expense_categories || {}
    let counter = 1
    let key = `custom_${counter}`
    while (currentCategories[key] !== undefined) {
      counter++
      key = `custom_${counter}`
    }
    return key
  }

  const handleEditSettlement = (settlement: Settlement) => {
    setEditingSettlement(settlement)
    // Ensure expense_categories is always an object with all standard categories
    const existingCategories = settlement.expense_categories && typeof settlement.expense_categories === 'object' 
      ? settlement.expense_categories 
      : {}
    
    // Initialize all standard categories, using existing values from PDF parsing or 0
    const categories: { [key: string]: number } = {}
    
    // Map old category names to new ones (for backward compatibility)
    const categoryMapping: { [key: string]: string[] } = {
      'fees': ['dispatch_fee', 'safety', 'prepass', 'insurance'], // Old "fees" category might contain multiple
      'other': ['service_on_truck', 'truck_parking'] // Old "other" category
      // Note: 'custom' is no longer ignored - it will be preserved and can be renamed
    }
    
    STANDARD_EXPENSE_CATEGORIES.forEach(category => {
      // First, check if the category exists directly
      if (existingCategories[category] !== undefined && existingCategories[category] !== null) {
        categories[category] = Number(existingCategories[category]) || 0
      } else {
        // Check if it's in an old grouped category
        let found = false
        for (const [oldCategory, newCategories] of Object.entries(categoryMapping)) {
          if (newCategories.includes(category) && existingCategories[oldCategory]) {
            // If the old category exists, we can't split it automatically
            // So we'll leave it as 0, but the user can manually fill it
            categories[category] = 0
            found = true
            break
          }
        }
        if (!found) {
          categories[category] = 0
        }
      }
    })
    
    // Also include any non-standard categories that might exist (preserve them)
    // This includes "custom" and any other custom category names
    Object.keys(existingCategories).forEach(key => {
      if (!STANDARD_EXPENSE_CATEGORIES.includes(key) && !categoryMapping[key]) {
        const value = existingCategories[key]
        categories[key] = value !== undefined && value !== null ? Number(value) || 0 : 0
      }
    })
    
    const formData = {
      truck_id: settlement.truck_id,
      driver_id: settlement.driver_id || undefined,
      settlement_date: settlement.settlement_date,
      week_start: settlement.week_start || undefined,
      week_end: settlement.week_end || undefined,
      miles_driven: settlement.miles_driven || undefined,
      blocks_delivered: settlement.blocks_delivered || undefined,
      gross_revenue: settlement.gross_revenue || undefined,
      expenses: settlement.expenses || undefined,
      expense_categories: categories,
      custom_expense_descriptions: settlement.custom_expense_descriptions || {},
      net_profit: settlement.net_profit || undefined,
      license_plate: settlement.license_plate || undefined,
      settlement_type: settlement.settlement_type || undefined,
    }
    
    setEditFormData(formData)
    // Store original data for comparison
    setOriginalFormData({ ...formData })
    
    // Initialize input values - auto-fill with parsed values from PDF
    const inputValues: { [key: string]: string } = {}
    const categoryNameValues: { [key: string]: string } = {}
    Object.entries(categories).forEach(([key, value]) => {
      // Check if this category was parsed from the PDF (exists in original data)
      const wasParsed = existingCategories[key] !== undefined && existingCategories[key] !== null
      
      if (wasParsed) {
        // Show the parsed value formatted with 2 decimals (even if 0, because it was explicitly parsed)
        inputValues[key] = formatCurrency(existingCategories[key])
      } else if (value > 0) {
        // Show non-zero values that were calculated/derived, formatted with 2 decimals
        inputValues[key] = formatCurrency(value)
      } else {
        // Leave empty for unparsed zero values
        inputValues[key] = ''
      }
      
      // Initialize category name inputs for non-standard categories
      if (!STANDARD_EXPENSE_CATEGORIES.includes(key)) {
        // For custom categories, get description from settlement's custom_expense_descriptions
        if (key === 'custom' || key.startsWith('custom_')) {
          // Read directly from settlement's custom_expense_descriptions
          if (settlement.custom_expense_descriptions && settlement.custom_expense_descriptions[key]) {
            categoryNameValues[key] = settlement.custom_expense_descriptions[key]
          } else {
            // Fallback: try to extract from key for backward compatibility
            if (key.startsWith('custom_')) {
              categoryNameValues[key] = key.replace('custom_', '').split('_').map(word => 
                word.charAt(0).toUpperCase() + word.slice(1)
              ).join(' ')
            } else {
              categoryNameValues[key] = ''
            }
          }
        } else {
          categoryNameValues[key] = key
        }
      }
    })
    setExpenseCategoryInputs(inputValues)
    setCategoryNameInputs(categoryNameValues)
    
      // Initialize dispatch fee percentage based on existing dispatch fee
      // If dispatch fee exists, try to determine percentage from gross revenue
      if (categories.dispatch_fee && settlement.gross_revenue) {
        const calculatedPercent = (categories.dispatch_fee / settlement.gross_revenue) * 100
        // Round to nearest 6%, 8%, or 10%
        const diff6 = Math.abs(calculatedPercent - 6)
        const diff8 = Math.abs(calculatedPercent - 8)
        const diff10 = Math.abs(calculatedPercent - 10)
        if (diff6 <= diff8 && diff6 <= diff10) {
          setDispatchFeePercent(6)
        } else if (diff8 <= diff10) {
          setDispatchFeePercent(8)
        } else {
          setDispatchFeePercent(10)
        }
      } else {
        setDispatchFeePercent(6) // Default to 6%
      }
      
      // Initialize input values for gross revenue, expenses, and net profit
      setGrossRevenueInput(settlement.gross_revenue !== undefined && settlement.gross_revenue !== null ? formatCurrency(settlement.gross_revenue) : '')
      setTotalExpensesInput(settlement.expenses !== undefined && settlement.expenses !== null ? formatCurrency(settlement.expenses) : '')
      setNetProfitInput(settlement.net_profit !== undefined && settlement.net_profit !== null ? formatCurrency(settlement.net_profit) : '')
  }
  
  // Format currency to 2 decimals with dollar sign (handles negative values)
  const formatCurrency = (value: number | string | undefined | null): string => {
    if (value === undefined || value === null || value === '') return ''
    const numValue = typeof value === 'string' ? parseFloat(value) : value
    if (isNaN(numValue)) return ''
    if (numValue < 0) {
      return `-$${Math.abs(numValue).toFixed(2)}`
    }
    return `$${numValue.toFixed(2)}`
  }

  // Parse currency input (remove dollar sign and commas, preserve minus sign)
  const parseCurrencyInput = (value: string): string => {
    // Remove dollar sign and commas, keep numbers, decimal point, and minus sign
    // Allow minus sign only at the beginning
    const cleaned = value.replace(/[$,]/g, '')
    // Ensure minus sign is only at the start if present
    if (cleaned.includes('-') && !cleaned.startsWith('-')) {
      return cleaned.replace(/-/g, '')
    }
    return cleaned
  }

  // Calculate dispatch fee when percentage or gross revenue changes
  const calculateDispatchFee = (grossRevenue: number | undefined, percent: 6 | 8 | 10) => {
    if (!grossRevenue) return 0
    return grossRevenue * (percent / 100)
  }
  
  const handleDispatchFeePercentChange = (percent: 6 | 8 | 10) => {
    setDispatchFeePercent(percent)
    setEditFormData(prev => {
      const grossRevenue = prev.gross_revenue
      if (!grossRevenue) return prev
      
      const dispatchFee = calculateDispatchFee(grossRevenue, percent)
      const updatedCategories = { ...(prev.expense_categories || {}) }
      updatedCategories.dispatch_fee = dispatchFee
      
      // Recalculate total expenses
      const totalExpenses = Object.values(updatedCategories).reduce((sum, val) => sum + (val || 0), 0)
      const netProfit = grossRevenue && totalExpenses ? grossRevenue - totalExpenses : (grossRevenue ? grossRevenue : undefined)
      
      const updatedFormData = {
        ...prev,
        expense_categories: { ...updatedCategories },
        expenses: totalExpenses,
        net_profit: netProfit
      }
      
      // Update input values
      setExpenseCategoryInputs(prevInputs => ({ ...prevInputs, dispatch_fee: formatCurrency(dispatchFee) }))
      setTotalExpensesInput(formatCurrency(totalExpenses))
      if (netProfit !== undefined) {
        setNetProfitInput(formatCurrency(netProfit))
      }
      
      return updatedFormData
    })
  }

  const handleCancelEdit = () => {
    setEditingSettlement(null)
    setEditFormData({})
    setOriginalFormData({})
    setExpenseCategoryInputs({})
    setCategoryNameInputs({})
    setDispatchFeePercent(6)
    setGrossRevenueInput('')
    setTotalExpensesInput('')
    setNetProfitInput('')
    setIsNavigating(false)
  }

  // Helper function to get sorted settlements (newest first)
  const getSortedSettlements = () => {
    return [...settlements].sort((a, b) => {
      const dateA = new Date(a.settlement_date).getTime()
      const dateB = new Date(b.settlement_date).getTime()
      if (dateB !== dateA) return dateB - dateA
      return b.id - a.id
    })
  }

  const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info') => {
    setToast({ message, type, isVisible: true })
  }

  const handleVinLookup = () => {
    if (!vinLookup.trim()) return
    
    const foundTruck = trucks.find(t => 
      t.vin && t.vin.toLowerCase() === vinLookup.trim().toLowerCase()
    )
    
    if (foundTruck) {
      setManualFormData({ ...manualFormData, truck_id: foundTruck.id })
      showToast(`Found ${foundTruck.vehicle_type === 'truck' ? 'truck' : 'trailer'}: ${foundTruck.name}`, 'success')
    } else {
      showToast('No vehicle found with that VIN', 'error')
    }
  }

  const handleCreateManual = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!manualFormData.truck_id) {
      showToast('Please select a truck or trailer', 'error')
      return
    }
    
    if (!manualFormData.settlement_date) {
      showToast('Settlement date is required', 'error')
      return
    }

    // Calculate net profit if not provided
    const grossRevenue = manualFormData.gross_revenue || 0
    const expenses = manualFormData.expenses || 0
    const netProfit = manualFormData.net_profit !== undefined 
      ? manualFormData.net_profit 
      : grossRevenue - expenses

    setCreatingManual(true)
    try {
      // Build custom_expense_descriptions if description is provided
      const customExpenseDescriptions = expensesDescription.trim() 
        ? { total_expenses: expensesDescription.trim() }
        : undefined

      const settlementData: Partial<Settlement> = {
        truck_id: manualFormData.truck_id,
        settlement_date: manualFormData.settlement_date,
        gross_revenue: grossRevenue,
        expenses: expenses,
        net_profit: netProfit,
        week_start: manualFormData.week_start,
        week_end: manualFormData.week_end,
        miles_driven: manualFormData.miles_driven,
        blocks_delivered: manualFormData.blocks_delivered,
        expense_categories: manualFormData.expense_categories,
        custom_expense_descriptions: customExpenseDescriptions,
        settlement_type: manualFormData.settlement_type || 'Manual Entry',
      }

      const response = await settlementsApi.create(settlementData)
      console.log('Settlement created:', response.data)
      showToast('Settlement created successfully!', 'success')
      setShowManualForm(false)
      setManualFormData({
        truck_id: undefined,
        settlement_date: new Date().toISOString().split('T')[0],
        gross_revenue: undefined,
        expenses: undefined,
        net_profit: undefined,
      })
      setExpensesDescription('')
      setVinLookup('')
      loadSettlements()
    } catch (err: any) {
      console.error('Error creating settlement:', err)
      console.error('Error response:', err.response?.data)
      console.error('Settlement data sent:', settlementData)
      showToast(err.response?.data?.detail || err.message || 'Failed to create settlement', 'error')
    } finally {
      setCreatingManual(false)
    }
  }

  // Check if there are any changes compared to original data
  const hasChanges = (): boolean => {
    if (!originalFormData || Object.keys(originalFormData).length === 0) return false
    
    // Compare all fields
    const fieldsToCompare: string[] = [
      'truck_id', 'settlement_date', 'week_start', 'week_end',
      'miles_driven', 'blocks_delivered', 'gross_revenue', 'expenses',
      'net_profit', 'settlement_type'
    ]
    
    for (const field of fieldsToCompare) {
      const original = (originalFormData as any)[field]
      const current = (editFormData as any)[field]
      
      if (original !== current) {
        // Handle null/undefined comparison
        if ((original == null && current != null) || (original != null && current == null)) {
          return true
        }
        if (original !== current) {
          return true
        }
      }
    }
    
    // Compare expense_categories
    const originalCategories = originalFormData.expense_categories || {}
    const currentCategories = editFormData.expense_categories || {}
    
    const allCategoryKeys = new Set([
      ...Object.keys(originalCategories),
      ...Object.keys(currentCategories)
    ])
    
    for (const key of allCategoryKeys) {
      const originalValue = originalCategories[key] || 0
      const currentValue = currentCategories[key] || 0
      if (Math.abs(originalValue - currentValue) > 0.01) { // Account for floating point precision
        return true
      }
    }
    
    return false
  }

  const navigateToSettlement = async (direction: 'prev' | 'next') => {
    if (!editingSettlement || isNavigating) return
    
    setIsNavigating(true)
    
    // Only save if there are changes
    const hasUnsavedChanges = hasChanges()
    
    if (hasUnsavedChanges) {
      // Save current settlement before navigating
      try {
        await settlementsApi.update(editingSettlement.id, editFormData)
        await loadSettlements()
        showToast('Settlement saved successfully', 'success')
      } catch (err: any) {
        const errorMessage = err.response?.data?.detail || err.message || 'Failed to update settlement'
        showToast(errorMessage, 'error')
        setIsNavigating(false)
        return // Don't navigate if save failed
      }
    }
    
    const sortedSettlements = getSortedSettlements()
    const currentIndex = sortedSettlements.findIndex(s => s.id === editingSettlement.id)
    
    if (currentIndex === -1) {
      setIsNavigating(false)
      return
    }
    
    let targetIndex: number
    if (direction === 'prev') {
      targetIndex = currentIndex + 1
      if (targetIndex >= sortedSettlements.length) {
        setIsNavigating(false)
        return // Already at first
      }
    } else {
      targetIndex = currentIndex - 1
      if (targetIndex < 0) {
        setIsNavigating(false)
        return // Already at last
      }
    }
    
    const targetSettlement = sortedSettlements[targetIndex]
    if (targetSettlement) {
      handleEditSettlement(targetSettlement)
    }
    
    setIsNavigating(false)
  }
  
  // Check if navigation buttons should be disabled
  const getNavigationState = () => {
    if (!editingSettlement) return { canGoPrev: false, canGoNext: false }
    
    const sortedSettlements = getSortedSettlements()
    const currentIndex = sortedSettlements.findIndex(s => s.id === editingSettlement.id)
    
    if (currentIndex === -1) return { canGoPrev: false, canGoNext: false }
    
    return {
      canGoPrev: currentIndex + 1 < sortedSettlements.length,
      canGoNext: currentIndex - 1 >= 0
    }
  }
  

  const handleSaveEdit = async () => {
    if (!editingSettlement) return
    try {
      await settlementsApi.update(editingSettlement.id, editFormData)
      await loadSettlements()
      // Update original data to reflect saved state
      setOriginalFormData({ ...editFormData })
      showToast('Settlement updated successfully!', 'success')
      handleCancelEdit()
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to update settlement'
      showToast(errorMessage, 'error')
    }
  }

  const handleExpenseCategoryChange = (oldKey: string, newKey: string, value: string | number) => {
    if (!editFormData.expense_categories) {
      setEditFormData({ ...editFormData, expense_categories: {} })
      return
    }
    const updated = { ...editFormData.expense_categories }
    if (oldKey !== newKey) {
      delete updated[oldKey]
    }
    const numValue = value === '' || value === null || value === undefined 
      ? 0 
      : typeof value === 'string' 
        ? parseFloat(value) || 0 
        : value
    updated[newKey] = numValue
    
    // Calculate total expenses:
    // - Standard categories: positive values add to expenses, negative values reduce expenses
    // - Custom categories: positive values are credits (reduce expenses), negative values are charges (add to expenses)
    // So we flip the sign for custom categories
    const totalExpenses = Object.entries(updated).reduce((sum, [key, val]) => {
      const numVal = typeof val === 'number' ? val : (parseFloat(String(val)) || 0)
      // Flip sign for custom categories (non-standard)
      if (!STANDARD_EXPENSE_CATEGORIES.includes(key)) {
        return sum - numVal  // Flip: positive becomes negative (reduces expenses), negative becomes positive (adds to expenses)
      }
      return sum + numVal  // Standard categories: positive adds, negative subtracts
    }, 0)
    const grossRevenue = editFormData.gross_revenue || 0
    const netProfit = grossRevenue ? grossRevenue - totalExpenses : undefined
    
    setEditFormData({
      ...editFormData,
      expense_categories: updated,
      expenses: totalExpenses,
      net_profit: netProfit
    })
    
    // Update total expenses input and net profit input to reflect the changes
    setTotalExpensesInput(formatCurrency(totalExpenses))
    if (netProfit !== undefined) {
      setNetProfitInput(formatCurrency(netProfit))
    }
  }

  const handleExpenseCategoryAmountChange = (key: string, value: string) => {
    // Store the raw input value (without formatting) while typing
    setExpenseCategoryInputs(prev => ({ ...prev, [key]: value }))
    if (!editFormData.expense_categories) {
      setEditFormData({ ...editFormData, expense_categories: {} })
      return
    }
    
    // Allow empty values during typing - don't update the category value yet
    // Only update on blur
    if (value === '' || value === '.' || value === '-') {
      // Keep the input empty, but don't update the category value yet
      // The category value will be updated on blur
      return
    }
    
    // Parse the value, preserving negative sign
    // parseCurrencyInput already cleaned it, so we can parse directly
    const numValue = parseFloat(value)
    const updated = { ...editFormData.expense_categories }
    updated[key] = isNaN(numValue) ? 0 : numValue
    
    // Calculate total expenses:
    // - Standard categories: positive values add to expenses, negative values reduce expenses
    // - Custom categories: positive values are credits (reduce expenses), negative values are charges (add to expenses)
    const totalExpenses = Object.entries(updated).reduce((sum, [catKey, val]) => {
      const numVal = typeof val === 'number' ? val : (parseFloat(String(val)) || 0)
      // Flip sign for custom categories (non-standard)
      if (!STANDARD_EXPENSE_CATEGORIES.includes(catKey)) {
        return sum - numVal  // Flip: positive becomes negative (reduces expenses), negative becomes positive (adds to expenses)
      }
      return sum + numVal  // Standard categories: positive adds, negative subtracts
    }, 0)
    const grossRevenue = editFormData.gross_revenue || 0
    const netProfit = grossRevenue ? grossRevenue - totalExpenses : undefined
    
    setEditFormData({
      ...editFormData,
      expense_categories: updated,
      expenses: totalExpenses,
      net_profit: netProfit
    })
    
    // Update total expenses input and net profit input to reflect the changes
    setTotalExpensesInput(formatCurrency(totalExpenses))
    if (netProfit !== undefined) {
      setNetProfitInput(formatCurrency(netProfit))
    }
  }

  const handleAddExpenseCategory = () => {
    const currentCategories = editFormData.expense_categories || {}
    const customKey = generateCustomKey()
    
    const updated = {
      ...currentCategories,
      [customKey]: 0
    }
    
    // Initialize custom_expense_descriptions if it doesn't exist
    const updatedDescriptions = editFormData.custom_expense_descriptions || {}
    
    setEditFormData({
      ...editFormData,
      expense_categories: updated,
      custom_expense_descriptions: updatedDescriptions
    })
    setExpenseCategoryInputs(prev => ({ ...prev, [customKey]: '' }))
    // Initialize with empty description - user will fill it in
    setCategoryNameInputs(prev => ({ ...prev, [customKey]: '' }))
  }

  const handleRemoveExpenseCategory = (key: string) => {
    if (!editFormData.expense_categories) return
    const updated = { ...editFormData.expense_categories }
    delete updated[key]
    // Calculate total expenses:
    // - Standard categories: positive values add to expenses, negative values reduce expenses
    // - Custom categories: positive values are credits (reduce expenses), negative values are charges (add to expenses)
    const totalExpenses = Object.entries(updated).reduce((sum, [catKey, val]) => {
      const numVal = typeof val === 'number' ? val : (parseFloat(String(val)) || 0)
      // Flip sign for custom categories (non-standard)
      if (!STANDARD_EXPENSE_CATEGORIES.includes(catKey)) {
        return sum - numVal  // Flip: positive becomes negative (reduces expenses), negative becomes positive (adds to expenses)
      }
      return sum + numVal  // Standard categories: positive adds, negative subtracts
    }, 0)
    const grossRevenue = editFormData.gross_revenue || 0
    const netProfit = grossRevenue ? grossRevenue - totalExpenses : undefined
    
    // Also remove description if it exists
    const updatedDescriptions = { ...(editFormData.custom_expense_descriptions || {}) }
    delete updatedDescriptions[key]
    
    setEditFormData({
      ...editFormData,
      expense_categories: updated,
      custom_expense_descriptions: updatedDescriptions,
      expenses: totalExpenses,
      net_profit: netProfit
    })
    
    setExpenseCategoryInputs(prev => {
      const newInputs = { ...prev }
      delete newInputs[key]
      return newInputs
    })
    
    setCategoryNameInputs(prev => {
      const newInputs = { ...prev }
      delete newInputs[key]
      return newInputs
    })
    
    // Update total expenses input and net profit input to reflect the changes
    setTotalExpensesInput(formatCurrency(totalExpenses))
    if (netProfit !== undefined) {
      setNetProfitInput(formatCurrency(netProfit))
    }
  }

  if (loading) return <div className="text-center py-8">Loading settlements...</div>
  if (error) return <div className="text-center py-8 text-red-600">{error}</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Settlements</h1>
        <div className="flex gap-2 items-center">
          {deleteMode ? (
            <>
              {selectedSettlements.size > 0 && (
                <button
                  onClick={() => setSettlementToDelete(0)}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium"
                >
                  Delete Selected ({selectedSettlements.size})
                </button>
              )}
              <button
                onClick={() => {
                  setDeleteMode(false)
                  setSelectedSettlements(new Set())
                }}
                className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setDeleteMode(true)}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium"
              >
                Delete
              </button>
              <button
                onClick={() => {
                  setShowManualForm(!showManualForm)
                  if (showManualForm) {
                    // Reset form when closing
                    setManualFormData({
                      truck_id: undefined,
                      settlement_date: new Date().toISOString().split('T')[0],
                      gross_revenue: undefined,
                      expenses: undefined,
                      net_profit: undefined,
                    })
                    setExpensesDescription('')
                    setVinLookup('')
                  }
                }}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
              >
                {showManualForm ? 'Cancel' : 'Add Manual Settlement'}
              </button>
              <button
                onClick={() => {
                  setShowUploadForm(!showUploadForm)
                  if (showUploadForm) {
                    // Reset form when closing
                    setUploadFile(null)
                    setSelectedTruckForUpload(null)
                  }
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                {showUploadForm ? 'Cancel' : 'Upload Settlement'}
              </button>
            </>
          )}
        </div>
      </div>

      {showUploadForm && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Upload Settlement</h2>
          <p className="text-sm text-gray-600 mb-4">
            Upload a settlement PDF. The system will automatically extract data, upload the PDF to Cloud storage, and import the settlement to the database.
          </p>
          <form onSubmit={handleUpload}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Truck/Trailer (Optional - will auto-detect from license plate if not selected)
              </label>
              <select
                value={selectedTruckForUpload || ''}
                onChange={(e) => setSelectedTruckForUpload(e.target.value ? Number(e.target.value) : null)}
                disabled={uploading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Auto-detect from PDF license plate</option>
                {trucks.map((truck) => (
                  <option key={truck.id} value={truck.id}>
                    {truck.vehicle_type === 'trailer' ? '🚛 ' : '🚚 '}
                    {truck.name} 
                    {truck.license_plate ? ` (${truck.license_plate})` : ''}
                    {truck.tag_number ? ` [Tag: ${truck.tag_number}]` : ''}
                    {truck.vin ? ` - VIN: ${truck.vin}` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">PDF File *</label>
              <label 
                className={`flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
                  isDragging 
                    ? 'border-blue-500 bg-blue-50' 
                    : 'border-gray-300 bg-gray-50 hover:bg-gray-100 hover:border-blue-400'
                }`}
                onDragEnter={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setIsDragging(true)
                }}
                onDragLeave={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setIsDragging(false)
                }}
                onDragOver={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                }}
                onDrop={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setIsDragging(false)
                  const files = Array.from(e.dataTransfer.files).filter(file => file.type === 'application/pdf')
                  if (files.length > 0) {
                    setUploadFile(files[0])
                  }
                }}
              >
                <div className="flex flex-col items-center justify-center pt-5 pb-6">
                  <svg className="w-10 h-10 mb-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  <p className="mb-2 text-sm text-gray-500">
                    <span className="font-semibold">Click to upload</span> or drag and drop
                  </p>
                  <p className="text-xs text-gray-500">PDF file only</p>
                  {uploadFile && (
                    <p className="mt-2 text-xs font-medium text-blue-600 truncate max-w-[200px]">{uploadFile.name}</p>
                  )}
                </div>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  required
                  disabled={uploading}
                  className="hidden"
                />
              </label>
              <p className="text-xs text-gray-500 mt-1">
                PDFs are automatically uploaded to Cloud storage and settlement data is extracted and imported to the database.
              </p>
            </div>
            <button
              type="submit"
              disabled={uploading || !uploadFile}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </form>
        </div>
      )}

      {showManualForm && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Add Manual Settlement</h2>
          <p className="text-sm text-gray-600 mb-4">
            Manually create a settlement for trucks or trailers. Useful for tracking revenue from trailers or when PDF parsing fails.
          </p>
          <form onSubmit={handleCreateManual} autoComplete="off">
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Vehicle *</label>
              <div className="mb-2">
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={vinLookup}
                    onChange={(e) => setVinLookup(e.target.value)}
                    placeholder="Enter VIN to lookup vehicle"
                    maxLength={17}
                    autoComplete="off"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={handleVinLookup}
                    className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                  >
                    Lookup VIN
                  </button>
                </div>
              </div>
              <select
                value={manualFormData.truck_id || ''}
                onChange={(e) => setManualFormData({ ...manualFormData, truck_id: e.target.value ? Number(e.target.value) : undefined })}
                required
                disabled={creatingManual}
                autoComplete="off"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select a truck or trailer...</option>
                {trucks.map((truck) => (
                  <option key={truck.id} value={truck.id}>
                    {truck.vehicle_type === 'trailer' ? '🚛 Trailer' : '🚚 Truck'}: {truck.name}
                    {truck.license_plate ? ` (${truck.license_plate})` : ''}
                    {truck.tag_number ? ` [Tag: ${truck.tag_number}]` : ''}
                    {truck.vin ? ` - VIN: ${truck.vin}` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Settlement Date *</label>
                <input
                  type="date"
                  value={manualFormData.settlement_date || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, settlement_date: e.target.value })}
                  required
                  autoComplete="off"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Week Start</label>
                <input
                  type="date"
                  value={manualFormData.week_start || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, week_start: e.target.value || undefined })}
                  autoComplete="off"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Week End</label>
                <input
                  type="date"
                  value={manualFormData.week_end || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, week_end: e.target.value || undefined })}
                  autoComplete="off"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Gross Revenue ($)</label>
                <input
                  type="number"
                  step="0.01"
                  value={manualFormData.gross_revenue || ''}
                  onChange={(e) => {
                    const value = e.target.value ? parseFloat(e.target.value) : undefined
                    const expenses = manualFormData.expenses || 0
                    const netProfit = value !== undefined ? (value - expenses) : undefined
                    setManualFormData({ 
                      ...manualFormData, 
                      gross_revenue: value,
                      net_profit: netProfit
                    })
                  }}
                  placeholder="0.00"
                  autoComplete="off"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Total Expenses ($)</label>
                <input
                  type="number"
                  step="0.01"
                  value={manualFormData.expenses || ''}
                  onChange={(e) => {
                    const value = e.target.value ? parseFloat(e.target.value) : undefined
                    const revenue = manualFormData.gross_revenue || 0
                    const netProfit = revenue > 0 ? (revenue - (value || 0)) : undefined
                    setManualFormData({ 
                      ...manualFormData, 
                      expenses: value,
                      net_profit: netProfit
                    })
                  }}
                  placeholder="0.00"
                  autoComplete="off"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Net Profit ($)</label>
                <input
                  type="number"
                  step="0.01"
                  value={manualFormData.net_profit || ''}
                  onChange={(e) => setManualFormData({ 
                    ...manualFormData, 
                    net_profit: e.target.value ? parseFloat(e.target.value) : undefined 
                  })}
                  placeholder="Auto-calculated"
                  autoComplete="off"
                  readOnly
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Expenses Description</label>
              <textarea
                value={expensesDescription}
                onChange={(e) => setExpensesDescription(e.target.value)}
                placeholder="Describe what these expenses are for (e.g., fuel, repairs, maintenance, etc.)"
                rows={3}
                autoComplete="off"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Miles Driven</label>
                <input
                  type="number"
                  step="0.01"
                  value={manualFormData.miles_driven || ''}
                  onChange={(e) => setManualFormData({ 
                    ...manualFormData, 
                    miles_driven: e.target.value ? parseFloat(e.target.value) : undefined 
                  })}
                  autoComplete="off"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Blocks Delivered</label>
                <input
                  type="number"
                  value={manualFormData.blocks_delivered || ''}
                  onChange={(e) => setManualFormData({ 
                    ...manualFormData, 
                    blocks_delivered: e.target.value ? parseInt(e.target.value) : undefined 
                  })}
                  autoComplete="off"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Settlement Type</label>
              <input
                type="text"
                value={manualFormData.settlement_type || 'Manual Entry'}
                onChange={(e) => setManualFormData({ ...manualFormData, settlement_type: e.target.value || 'Manual Entry' })}
                autoComplete="off"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={creatingManual}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {creatingManual ? 'Creating...' : 'Create Settlement'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowManualForm(false)
                  setManualFormData({
                    truck_id: undefined,
                    settlement_date: new Date().toISOString().split('T')[0],
                    gross_revenue: undefined,
                    expenses: undefined,
                    net_profit: undefined,
                  })
                  setExpensesDescription('')
                  setVinLookup('')
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {!Array.isArray(settlements) || settlements.length === 0 ? (
            <li className="px-6 py-4 text-gray-500 text-center">No settlements found.</li>
          ) : (
            <>
              {deleteMode && (
                <li className="px-6 py-3 bg-gray-50 border-b border-gray-200">
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={settlements.length > 0 && selectedSettlements.size === settlements.length}
                      onChange={handleSelectAll}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label className="ml-3 text-sm font-medium text-gray-700">Select All</label>
                  </div>
                </li>
              )}
              {settlements.map((settlement) => (
                <li 
                  key={settlement.id} 
                  className={`px-6 py-4 hover:bg-gray-50 transition-colors ${
                    deleteMode ? '' : 'cursor-pointer'
                  }`}
                  onClick={() => !deleteMode && handleEditSettlement(settlement)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-start flex-1">
                      {deleteMode && (
                        <input
                          type="checkbox"
                          checked={selectedSettlements.has(settlement.id)}
                          onChange={(e) => {
                            e.stopPropagation()
                            handleSelectSettlement(settlement.id)
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                      )}
                      <div className={deleteMode ? "ml-4 flex-1" : "flex-1"}>
                        <div className="flex items-center gap-2">
                          <h3 className="text-lg font-medium text-gray-900">
                            {getTruckName(settlement.truck_id)} - {new Date(settlement.settlement_date).toLocaleDateString()}
                          </h3>
                          {!deleteMode && (
                            <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                              Click to edit
                            </span>
                          )}
                        </div>
                        <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          {settlement.miles_driven && (
                            <div>
                              <span className="text-gray-500">Miles: </span>
                              <span className="font-medium">{settlement.miles_driven.toLocaleString()}</span>
                            </div>
                          )}
                          {settlement.blocks_delivered && (
                            <div>
                              <span className="text-gray-500">Blocks: </span>
                              <span className="font-medium">{settlement.blocks_delivered}</span>
                            </div>
                          )}
                          {settlement.gross_revenue && (
                            <div>
                              <span className="text-gray-500">Revenue: </span>
                              <span className="font-medium text-green-600">
                                ${settlement.gross_revenue.toLocaleString()}
                              </span>
                            </div>
                          )}
                          {settlement.net_profit !== undefined && (
                            <div>
                              <span className="text-gray-500">Profit: </span>
                              <span className={`font-medium ${
                                settlement.net_profit < 0 ? 'text-red-600' : 'text-blue-600'
                              }`}>
                                ${settlement.net_profit.toLocaleString()}
                              </span>
                            </div>
                          )}
                        </div>
                        {settlement.pdf_file_path && (
                          <div className="mt-3">
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                window.open(getPdfUrl(settlement.pdf_file_path!), '_blank')
                              }}
                              className="text-xs text-blue-600 hover:text-blue-800 flex items-center space-x-1"
                            >
                              <span>📄</span>
                              <span>View PDF</span>
                            </button>
                          </div>
                        )}
                        {settlement.settlement_type && (
                          <div className="mt-2">
                            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                              Type: {settlement.settlement_type}
                            </span>
                          </div>
                        )}
                        {settlement.custom_expense_descriptions?.total_expenses && (
                          <div className="mt-2">
                            <span className="text-xs text-gray-600 italic">
                              Expenses: {settlement.custom_expense_descriptions.total_expenses}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                    {!deleteMode && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setSettlementToDelete(settlement.id)
                        }}
                        className="text-red-600 hover:text-red-800 ml-4"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </>
          )}
        </ul>
      </div>

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={modalTitle} type={modalType}>
        {modalMessage}
      </Modal>

      <ConfirmModal
        isOpen={settlementToDelete !== null && settlementToDelete !== 0}
        onClose={() => setSettlementToDelete(null)}
        onConfirm={handleDelete}
        title="Delete Settlement"
        message="Are you sure you want to delete this settlement? This action cannot be undone."
        confirmText="Delete"
        type="danger"
      />

      <ConfirmModal
        isOpen={settlementToDelete === 0 && selectedSettlements.size > 0}
        onClose={() => setSettlementToDelete(null)}
        onConfirm={handleBulkDelete}
        title="Delete Multiple Settlements"
        message={`Are you sure you want to delete ${selectedSettlements.size} settlement(s)? This action cannot be undone.`}
        confirmText={`Delete ${selectedSettlements.size} Settlement${selectedSettlements.size !== 1 ? 's' : ''}`}
        type="danger"
      />

      {editingSettlement && (
            <div className="fixed inset-0 z-50 overflow-y-auto">
              <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={handleCancelEdit} />
              <div className="flex min-h-full items-center justify-center p-4">
                <div
                  className="relative transform overflow-hidden rounded-lg bg-white shadow-xl transition-all w-[66vw] max-h-[95vh] lg:max-h-[98vh] flex flex-col"
                  onClick={(e) => e.stopPropagation()}
                >
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
                <div className="flex items-center gap-4">
                  {/* Previous/Next Navigation */}
                  <div className="flex items-center gap-2">
                    {(() => {
                      const navState = getNavigationState()
                      return (
                        <>
                          <button
                            onClick={() => navigateToSettlement('prev')}
                            disabled={!navState.canGoPrev || isNavigating}
                            className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            title="Previous settlement (newer)"
                          >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                            </svg>
                          </button>
                          <button
                            onClick={() => navigateToSettlement('next')}
                            disabled={!navState.canGoNext || isNavigating}
                            className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            title="Next settlement (older)"
                          >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </button>
                        </>
                      )
                    })()}
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900">
                    Edit Settlement - {getTruckName(editingSettlement.truck_id)} - {new Date(editingSettlement.settlement_date).toLocaleDateString()}
                  </h3>
                </div>
                <button onClick={handleCancelEdit} className="text-gray-400 hover:text-gray-500">
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-6">
                  {/* Settlement Data Section */}
                  <div className="space-y-4">
                    <h4 className="text-lg font-medium text-gray-900 mb-3">Settlement Data</h4>
                    <div className="grid grid-cols-7 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Truck</label>
                        <select
                          value={editFormData.truck_id || ''}
                          onChange={(e) => setEditFormData({ ...editFormData, truck_id: Number(e.target.value) })}
                          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          {trucks.map((truck) => (
                            <option key={truck.id} value={truck.id}>{truck.name}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Settlement Date</label>
                        <input
                          type="date"
                          value={editFormData.settlement_date || ''}
                          onChange={(e) => setEditFormData({ ...editFormData, settlement_date: e.target.value })}
                          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Miles Driven</label>
                        <input
                          type="number"
                          value={editFormData.miles_driven || ''}
                          onChange={(e) => setEditFormData({ ...editFormData, miles_driven: e.target.value ? Number(e.target.value) : undefined })}
                          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="0"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Blocks Delivered</label>
                        <input
                          type="number"
                          value={editFormData.blocks_delivered || ''}
                          onChange={(e) => setEditFormData({ ...editFormData, blocks_delivered: e.target.value ? Number(e.target.value) : undefined })}
                          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="0"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-blue-600 mb-1">Gross Revenue</label>
                        <input
                          type="text"
                          inputMode="decimal"
                          value={grossRevenueInput}
                          onChange={(e) => {
                            const inputValue = parseCurrencyInput(e.target.value)
                            if (inputValue === '' || /^-?\d*\.?\d*$/.test(inputValue)) {
                              setGrossRevenueInput(e.target.value)
                              const revenue = inputValue && inputValue !== '.' ? Number(inputValue) : undefined
                              
                              // Recalculate dispatch fee when gross revenue changes
                              let updatedCategories = { ...editFormData.expense_categories }
                              if (revenue) {
                                const dispatchFee = calculateDispatchFee(revenue, dispatchFeePercent)
                                updatedCategories.dispatch_fee = dispatchFee
                                setExpenseCategoryInputs(prev => ({ ...prev, dispatch_fee: formatCurrency(dispatchFee) }))
                              }
                              
                              // Recalculate total expenses
                              const totalExpenses = Object.values(updatedCategories).reduce((sum, val) => sum + (val || 0), 0)
                              const netProfit = revenue && totalExpenses ? revenue - totalExpenses : (revenue ? revenue : undefined)
                              
                              setEditFormData({
                                ...editFormData,
                                gross_revenue: revenue,
                                expense_categories: updatedCategories,
                                expenses: totalExpenses,
                                net_profit: netProfit
                              })
                              
                              // Update total expenses and net profit input fields
                              setTotalExpensesInput(formatCurrency(totalExpenses))
                              if (netProfit !== undefined) {
                                setNetProfitInput(formatCurrency(netProfit))
                              }
                            }
                          }}
                          onBlur={(e) => {
                            const inputValue = parseCurrencyInput(e.target.value.trim())
                            if (inputValue === '' || inputValue === '.') {
                              setGrossRevenueInput('')
                              setEditFormData({ ...editFormData, gross_revenue: undefined })
                            } else {
                              const revenue = parseFloat(inputValue)
                              if (!isNaN(revenue)) {
                                setGrossRevenueInput(formatCurrency(revenue))
                                setEditFormData({ ...editFormData, gross_revenue: revenue })
                              } else {
                                setGrossRevenueInput('')
                                setEditFormData({ ...editFormData, gross_revenue: undefined })
                              }
                            }
                          }}
                          className="w-full px-2 py-1.5 text-sm border border-blue-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-blue-700 font-medium"
                          placeholder="$0.00"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-red-600 mb-1">Total Expenses</label>
                        <input
                          type="text"
                          inputMode="decimal"
                          value={totalExpensesInput}
                          onChange={(e) => {
                            const inputValue = parseCurrencyInput(e.target.value)
                            if (inputValue === '' || /^-?\d*\.?\d*$/.test(inputValue)) {
                              setTotalExpensesInput(e.target.value)
                              const expenses = inputValue && inputValue !== '.' ? Number(inputValue) : undefined
                              const revenue = editFormData.gross_revenue || 0
                              setEditFormData({
                                ...editFormData,
                                expenses: expenses,
                                net_profit: revenue && expenses ? revenue - expenses : editFormData.net_profit
                              })
                            }
                          }}
                          onBlur={(e) => {
                            const inputValue = parseCurrencyInput(e.target.value.trim())
                            if (inputValue === '' || inputValue === '.') {
                              setTotalExpensesInput('')
                              setEditFormData({ ...editFormData, expenses: undefined })
                            } else {
                              const expenses = parseFloat(inputValue)
                              if (!isNaN(expenses)) {
                                setTotalExpensesInput(formatCurrency(expenses))
                                setEditFormData({ ...editFormData, expenses: expenses })
                              } else {
                                setTotalExpensesInput('')
                                setEditFormData({ ...editFormData, expenses: undefined })
                              }
                            }
                          }}
                          className="w-full px-2 py-1.5 text-sm border border-red-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 text-red-700 font-medium"
                          placeholder="$0.00"
                        />
                        <textarea
                          value={editFormData.custom_expense_descriptions?.total_expenses || ''}
                          onChange={(e) => {
                            const description = e.target.value.trim()
                            const updatedDescriptions = {
                              ...(editFormData.custom_expense_descriptions || {}),
                              total_expenses: description || undefined
                            }
                            if (!description) {
                              delete updatedDescriptions.total_expenses
                            }
                            setEditFormData({
                              ...editFormData,
                              custom_expense_descriptions: Object.keys(updatedDescriptions).length > 0 ? updatedDescriptions : undefined
                            })
                          }}
                          placeholder="Describe expenses (e.g., fuel, repairs, maintenance)"
                          rows={2}
                          className="w-full mt-1 px-2 py-1 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className={`block text-xs font-medium mb-1 ${
                          editFormData.net_profit !== undefined && editFormData.net_profit < 0 
                            ? 'text-red-600' 
                            : 'text-green-600'
                        }`}>Net Profit</label>
                        <input
                          type="text"
                          inputMode="decimal"
                          value={netProfitInput}
                          onChange={(e) => {
                            const inputValue = parseCurrencyInput(e.target.value)
                            if (inputValue === '' || /^-?\d*\.?\d*$/.test(inputValue)) {
                              setNetProfitInput(e.target.value)
                              const profit = inputValue && inputValue !== '.' ? Number(inputValue) : undefined
                              const revenue = editFormData.gross_revenue || 0
                              setEditFormData({
                                ...editFormData,
                                net_profit: profit,
                                expenses: revenue && profit ? revenue - profit : editFormData.expenses
                              })
                            }
                          }}
                          onBlur={(e) => {
                            const inputValue = parseCurrencyInput(e.target.value.trim())
                            if (inputValue === '' || inputValue === '.') {
                              setNetProfitInput('')
                              setEditFormData({ ...editFormData, net_profit: undefined })
                            } else {
                              const profit = parseFloat(inputValue)
                              if (!isNaN(profit)) {
                                setNetProfitInput(formatCurrency(profit))
                                setEditFormData({ ...editFormData, net_profit: profit })
                              } else {
                                setNetProfitInput('')
                                setEditFormData({ ...editFormData, net_profit: undefined })
                              }
                            }
                          }}
                          className={`w-full px-2 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 font-medium ${
                            editFormData.net_profit !== undefined && editFormData.net_profit < 0
                              ? 'border-red-300 text-red-700 focus:ring-red-500'
                              : 'border-green-300 text-green-700 focus:ring-green-500'
                          }`}
                          placeholder="$0.00"
                        />
                      </div>
                    </div>
                    
                    {/* Dispatch Fee Percentage Toggle */}
                    {editFormData.gross_revenue && (
                      <div className="border-t pt-2 mt-2">
                        <div className="flex items-center gap-3 text-sm">
                          <span className="text-gray-600 font-medium">Dispatch Fee:</span>
                          <label className="flex items-center cursor-pointer">
                            <input
                              type="radio"
                              name="dispatchFeePercent"
                              checked={dispatchFeePercent === 6}
                              onChange={() => handleDispatchFeePercentChange(6)}
                              className="h-3.5 w-3.5 text-blue-600 focus:ring-blue-500 border-gray-300"
                            />
                            <span className="ml-1.5 text-gray-700">6%</span>
                          </label>
                          <label className="flex items-center cursor-pointer">
                            <input
                              type="radio"
                              name="dispatchFeePercent"
                              checked={dispatchFeePercent === 8}
                              onChange={() => handleDispatchFeePercentChange(8)}
                              className="h-3.5 w-3.5 text-blue-600 focus:ring-blue-500 border-gray-300"
                            />
                            <span className="ml-1.5 text-gray-700">8%</span>
                          </label>
                          <label className="flex items-center cursor-pointer">
                            <input
                              type="radio"
                              name="dispatchFeePercent"
                              checked={dispatchFeePercent === 10}
                              onChange={() => handleDispatchFeePercentChange(10)}
                              className="h-3.5 w-3.5 text-blue-600 focus:ring-blue-500 border-gray-300"
                            />
                            <span className="ml-1.5 text-gray-700">10%</span>
                          </label>
                        </div>
                      </div>
                    )}
                    
                    <div className="border-t pt-4">
                      <div className="flex items-center justify-between mb-3">
                        <h5 className="text-md font-medium text-gray-900">Expense Categories</h5>
                        <button
                          type="button"
                          onClick={handleAddExpenseCategory}
                          className="text-sm text-blue-600 hover:text-blue-800"
                        >
                          + Add Category
                        </button>
                      </div>
                      <div className="grid grid-cols-6 gap-2 max-h-96 lg:max-h-[70vh] overflow-y-auto w-full">
                        {editFormData.expense_categories ? (
                          <>
                            {/* Display standard categories */}
                            {STANDARD_EXPENSE_CATEGORIES.map((category) => {
                              const value = editFormData.expense_categories![category] || 0
                              const displayName = category.split('_').map(word => 
                                word.charAt(0).toUpperCase() + word.slice(1)
                              ).join(' ')
                              
                              // Calculate payroll fee percentage if this is payroll_fee and driver_pay exists
                              let percentageDisplay = null
                              if (category === 'payroll_fee' && editFormData.expense_categories?.driver_pay && editFormData.expense_categories.driver_pay > 0 && value > 0) {
                                const percent = (value / editFormData.expense_categories.driver_pay) * 100
                                percentageDisplay = (
                                  <span className="text-xs text-gray-500 ml-2">
                                    ({percent.toFixed(2)}%)
                                  </span>
                                )
                              }
                              
                              const categoryColor = getCategoryColor(category)
                              return (
                                <div key={category} className="flex flex-col gap-1.5">
                                  <label className={`px-2 py-1.5 border rounded-md ${categoryColor.bg} ${categoryColor.border} text-sm font-medium ${categoryColor.text} flex items-center justify-between`}>
                                    <span className="truncate">{displayName}</span>
                                    {percentageDisplay}
                                  </label>
                                  <input
                                    type="text"
                                    inputMode="decimal"
                                    value={expenseCategoryInputs[category] !== undefined ? expenseCategoryInputs[category] : (value === 0 || value === null || value === undefined ? '' : formatCurrency(value))}
                                    onChange={(e) => {
                                      const rawValue = e.target.value
                                      const inputValue = parseCurrencyInput(rawValue)
                                      if (inputValue === '' || /^-?\d*\.?\d*$/.test(inputValue)) {
                                        // Store raw input value
                                        setExpenseCategoryInputs(prev => ({ ...prev, [category]: rawValue }))
                                        
                                        // Update category value during typing to recalculate net profit
                                        if (inputValue === '' || inputValue === '.') {
                                          handleExpenseCategoryChange(category, category, 0)
                                        } else {
                                          handleExpenseCategoryAmountChange(category, inputValue)
                                        }
                                      }
                                    }}
                                    onBlur={(e) => {
                                      const inputValue = parseCurrencyInput(e.target.value.trim())
                                      if (inputValue === '' || inputValue === '.' || inputValue === null) {
                                        handleExpenseCategoryChange(category, category, 0)
                                        setExpenseCategoryInputs(prev => ({ ...prev, [category]: '' }))
                                      } else {
                                        const numValue = parseFloat(inputValue)
                                        if (!isNaN(numValue)) {
                                          handleExpenseCategoryChange(category, category, numValue)
                                          setExpenseCategoryInputs(prev => ({ ...prev, [category]: formatCurrency(numValue) }))
                                        } else {
                                          handleExpenseCategoryChange(category, category, 0)
                                          setExpenseCategoryInputs(prev => ({ ...prev, [category]: '' }))
                                        }
                                      }
                                    }}
                                    className="w-full px-2 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                    placeholder="0.00"
                                  />
                                </div>
                              )
                            })}
                            {/* Display any additional non-standard categories as editable */}
                            {Object.entries(editFormData.expense_categories)
                              .filter(([key]) => !STANDARD_EXPENSE_CATEGORIES.includes(key))
                              .map(([key, value]) => {
                                // For custom categories, show description input instead of renaming
                                const isCustomCategory = key === 'custom' || key.startsWith('custom_')
                                // Get description from categoryNameInputs (initialized from settlement), or from editFormData, or fallback
                                const currentDescription = categoryNameInputs[key] !== undefined && categoryNameInputs[key] !== ''
                                  ? categoryNameInputs[key] 
                                  : isCustomCategory 
                                    ? (editFormData.custom_expense_descriptions?.[key] || getCustomDescription(key))
                                    : key
                                
                                return (
                                  <div key={key} className="flex flex-col gap-1.5">
                                    <div className="flex items-center gap-1">
                                      {isCustomCategory ? (
                                        <>
                                          <span className="px-2 py-1.5 text-sm text-gray-700 bg-gray-100 border border-gray-300 rounded-md whitespace-nowrap">
                                            Custom
                                          </span>
                                          <input
                                            type="text"
                                            value={currentDescription}
                                            onChange={(e) => {
                                              setCategoryNameInputs(prev => ({ ...prev, [key]: e.target.value }))
                                            }}
                                            onBlur={(e) => {
                                              const description = e.target.value.trim()
                                              
                                              // Update custom_expense_descriptions
                                              const updatedDescriptions = {
                                                ...(editFormData.custom_expense_descriptions || {}),
                                                [key]: description
                                              }
                                              
                                              // If description is empty, remove it from descriptions
                                              if (!description) {
                                                delete updatedDescriptions[key]
                                              }
                                              
                                              setEditFormData({
                                                ...editFormData,
                                                custom_expense_descriptions: updatedDescriptions
                                              })
                                              
                                              // Update the category name input state
                                              setCategoryNameInputs(prev => ({ ...prev, [key]: description }))
                                            }}
                                            className="flex-1 px-2 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                            placeholder="Description (e.g., Truck Parking, Repair)"
                                          />
                                        </>
                                      ) : (
                                        <input
                                          type="text"
                                          value={currentDescription}
                                          onChange={(e) => {
                                            setCategoryNameInputs(prev => ({ ...prev, [key]: e.target.value }))
                                          }}
                                          onBlur={(e) => {
                                            const newKey = e.target.value.trim()
                                            if (newKey && newKey !== key) {
                                              const currentCategories = editFormData.expense_categories || {}
                                              if (currentCategories[newKey] !== undefined && newKey !== key) {
                                                showModal('Error', `Category "${newKey}" already exists.`, 'error')
                                                setCategoryNameInputs(prev => ({ ...prev, [key]: key }))
                                                return
                                              }
                                              handleExpenseCategoryChange(key, newKey, value || 0)
                                              setCategoryNameInputs(prev => {
                                                const updated = { ...prev }
                                                delete updated[key]
                                                updated[newKey] = newKey
                                                return updated
                                              })
                                            } else if (!newKey) {
                                              setCategoryNameInputs(prev => ({ ...prev, [key]: key }))
                                            } else {
                                              setCategoryNameInputs(prev => ({ ...prev, [key]: newKey }))
                                            }
                                          }}
                                          className="flex-1 px-2 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                          placeholder="Category name"
                                        />
                                      )}
                                      <button
                                        type="button"
                                        onClick={() => handleRemoveExpenseCategory(key)}
                                        className="text-red-600 hover:text-red-800 px-1.5 py-1.5 text-sm"
                                        title="Remove category"
                                      >
                                        ✕
                                      </button>
                                    </div>
                                    <input
                                      type="text"
                                      inputMode="decimal"
                                      value={expenseCategoryInputs[key] !== undefined ? expenseCategoryInputs[key] : (value === 0 || value === null || value === undefined ? '' : formatCurrency(value))}
                                      onChange={(e) => {
                                        const rawValue = e.target.value
                                        const inputValue = parseCurrencyInput(rawValue)
                                        
                                        // Only allow valid decimal input (including negative)
                                        if (inputValue === '' || /^-?\d*\.?\d*$/.test(inputValue)) {
                                          // Store raw input value
                                          setExpenseCategoryInputs(prev => ({ ...prev, [key]: rawValue }))
                                          
                                          // Update category value during typing to recalculate net profit
                                          // But don't format the input until blur
                                          if (inputValue === '' || inputValue === '.' || inputValue === '-') {
                                            handleExpenseCategoryChange(key, key, 0)
                                          } else {
                                            // Parse the value, preserving negative sign
                                            handleExpenseCategoryAmountChange(key, inputValue)
                                          }
                                        }
                                      }}
                                      onBlur={(e) => {
                                        const inputValue = parseCurrencyInput(e.target.value.trim())
                                        if (inputValue === '' || inputValue === '.' || inputValue === null) {
                                          // Empty value - set to 0
                                          handleExpenseCategoryChange(key, key, 0)
                                          setExpenseCategoryInputs(prev => ({ ...prev, [key]: '' }))
                                        } else {
                                          const numValue = parseFloat(inputValue)
                                          if (!isNaN(numValue)) {
                                            // Valid number - update category and format the input
                                            handleExpenseCategoryChange(key, key, numValue)
                                            setExpenseCategoryInputs(prev => ({ ...prev, [key]: formatCurrency(numValue) }))
                                          } else {
                                            // Invalid - set to 0
                                            handleExpenseCategoryChange(key, key, 0)
                                            setExpenseCategoryInputs(prev => ({ ...prev, [key]: '' }))
                                          }
                                        }
                                      }}
                                      className={`w-full px-2 py-1.5 border rounded-md focus:outline-none focus:ring-2 text-sm ${
                                        (value || 0) < 0
                                          ? 'border-red-300 text-red-700 focus:ring-red-500'
                                          : 'border-green-300 text-green-700 focus:ring-green-500'
                                      }`}
                                      placeholder="0.00"
                                    />
                                  </div>
                                )
                              })}
                          </>
                        ) : (
                          <p className="col-span-6 text-sm text-gray-500 italic py-2">No expense categories. Click "+ Add Category" to add one.</p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                <button
                  onClick={handleCancelEdit}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                >
                  Save Changes
                </button>
              </div>
            </div>
          </div>
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
