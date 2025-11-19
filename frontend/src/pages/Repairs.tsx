import { useEffect, useState } from 'react'
import { repairsApi, trucksApi, Repair, Truck } from '../services/api'
import Modal from '../components/Modal'
import ConfirmModal from '../components/ConfirmModal'
import Toast from '../components/Toast'

export default function Repairs() {
  const [repairs, setRepairs] = useState<Repair[]>([])
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showUploadForm, setShowUploadForm] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadImages, setUploadImages] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [repairToDelete, setRepairToDelete] = useState<number | null>(null)
  const [imageToDelete, setImageToDelete] = useState<{ repairId: number; imageIndex: number } | null>(null)
  const [repairToEdit, setRepairToEdit] = useState<Repair | null>(null)
  const [editFormData, setEditFormData] = useState<Partial<Repair>>({})
  const [editImages, setEditImages] = useState<File[]>([])
  const [saving, setSaving] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalMessage, setModalMessage] = useState('')
  const [modalType, setModalType] = useState<'success' | 'error' | 'warning' | 'info'>('info')
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean }>({
    message: '',
    type: 'info',
    isVisible: false
  })
  const [searchFilter, setSearchFilter] = useState<string>('')
  const [selectedTruckForUpload, setSelectedTruckForUpload] = useState<number | null>(null)
  const [extractedVin, setExtractedVin] = useState<string | null>(null)
  const [requiresTruckSelection, setRequiresTruckSelection] = useState(false)
  const [showManualForm, setShowManualForm] = useState(false)
  const [manualFormData, setManualFormData] = useState<Partial<Repair>>({
    truck_id: undefined,
    repair_date: undefined,
    title: '',
    details: '',
    description: '',
    category: '',
    cost: undefined,
    invoice_number: ''
  })
  const [manualFormImages, setManualFormImages] = useState<File[]>([])
  const [creating, setCreating] = useState(false)
  const [manualCustomCategory, setManualCustomCategory] = useState<string>('')
  const [editCustomCategory, setEditCustomCategory] = useState<string>('')

  useEffect(() => {
    loadTrucks()
    loadRepairs()
  }, [])

  const loadTrucks = async () => {
    try {
      const response = await trucksApi.getAll()
      setTrucks(Array.isArray(response.data) ? response.data : [])
    } catch (err) {
      console.error(err)
      setTrucks([])
    }
  }

  const loadRepairs = async () => {
    try {
      setLoading(true)
      const response = await repairsApi.getAll()
      setRepairs(Array.isArray(response.data) ? response.data : [])
    } catch (err: any) {
      setError(err.message || 'Failed to load repairs')
      setRepairs([])
    } finally {
      setLoading(false)
    }
  }

  const showModal = (title: string, message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
    setModalTitle(title)
    setModalMessage(message)
    setModalType(type)
    setModalOpen(true)
  }

  const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info') => {
    setToast({ message, type, isVisible: true })
  }

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadFile) {
      showModal('Error', 'Please select a PDF invoice file', 'error')
      return
    }

    // If VIN was not found, require truck selection
    if (requiresTruckSelection && !selectedTruckForUpload) {
      showModal('Error', 'Please select a truck for this repair', 'error')
      return
    }

    try {
      setUploading(true)
      const response = await repairsApi.upload(uploadFile, uploadImages, selectedTruckForUpload || undefined)
      
      // Check if truck selection is required
      if (response.data.requires_truck_selection) {
        setRequiresTruckSelection(true)
        setExtractedVin(response.data.vin || null)
        const message = response.data.vin 
          ? `${response.data.warning || `VIN ${response.data.vin} found but no matching truck.`}\n\nPlease select the correct truck from the dropdown below and upload the file again.`
          : response.data.warning || 'Please select a truck for this repair and upload again.'
        showModal(
          'Truck Selection Required',
          message,
          'warning'
        )
        return
      }
      
      if (response.data.warning) {
        showToast(`Repair uploaded successfully. ${response.data.warning}`, 'warning')
      } else {
        const vinMessage = response.data.vin_found 
          ? 'Truck identified by VIN from invoice.' 
          : 'Truck selected manually.'
        showToast(`Repair uploaded successfully! ${vinMessage}`, 'success')
      }
      setUploadFile(null)
      setUploadImages([])
      setSelectedTruckForUpload(null)
      setExtractedVin(null)
      setRequiresTruckSelection(false)
      setShowUploadForm(false)
      loadRepairs()
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to upload repair'
      
      // Check if error indicates VIN not found - allow truck selection
      if (errorMessage.includes('Could not extract VIN') || errorMessage.includes('select a truck manually')) {
        setRequiresTruckSelection(true)
        setExtractedVin(null)
        showModal(
          'VIN Not Found',
          'VIN could not be extracted from the invoice. Please select a truck manually.',
          'warning'
        )
      } else {
        showModal('Upload Failed', errorMessage, 'error')
      }
    } finally {
      setUploading(false)
    }
  }

  const handleCreateManual = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!manualFormData.truck_id) {
      showModal('Error', 'Please select a truck', 'error')
      return
    }

    // If "other" category is selected, use custom category value
    const categoryToSave = manualFormData.category === 'other' && manualCustomCategory 
      ? manualCustomCategory 
      : manualFormData.category

    try {
      setCreating(true)
      // Clean up the data - remove undefined values and format dates
      const cleanedData: Partial<Repair> = {
        truck_id: manualFormData.truck_id,
        repair_date: manualFormData.repair_date || undefined,
        description: manualFormData.description || undefined,
        category: categoryToSave || undefined,
        cost: manualFormData.cost || undefined,
        invoice_number: manualFormData.invoice_number || undefined
      }
      
      // Remove undefined values
      Object.keys(cleanedData).forEach(key => {
        if (cleanedData[key as keyof Repair] === undefined) {
          delete cleanedData[key as keyof Repair]
        }
      })
      
      await repairsApi.create(
        cleanedData, 
        manualFormImages.length > 0 ? manualFormImages : undefined
      )
      showToast('Repair created successfully!', 'success')
      setManualFormData({
        truck_id: undefined,
        repair_date: undefined,
        description: '',
        category: '',
        cost: undefined,
        invoice_number: ''
      })
      setManualCustomCategory('')
      setManualFormImages([])
      setShowManualForm(false)
      loadRepairs()
    } catch (err: any) {
      console.error('Error creating repair:', err)
      const errorMessage = err.response?.data?.detail || err.response?.data?.message || err.message || 'Failed to create repair'
      showModal('Creation Failed', errorMessage, 'error')
    } finally {
      setCreating(false)
    }
  }

  const handleEdit = (repair: Repair) => {
    setRepairToEdit(repair)
    const category = repair.category || ''
    // Check if category is not in the standard list (i.e., it's a custom "other" category)
    const standardCategories = ['engine', 'tires', 'maintenance', 'electrical', 'brakes', 'suspension', 'body', 'other']
    const isCustomCategory = category && !standardCategories.includes(category.toLowerCase())
    
    setEditFormData({
      truck_id: repair.truck_id,
      repair_date: repair.repair_date,
      title: repair.title || '',
      details: repair.details || '',
      description: repair.description || '',
      category: isCustomCategory ? 'other' : category,
      cost: repair.cost
    })
    setEditCustomCategory(isCustomCategory ? category : '')
    setEditImages([])
  }

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!repairToEdit) return

    // If "other" category is selected, use custom category value
    const categoryToSave = editFormData.category === 'other' && editCustomCategory 
      ? editCustomCategory 
      : editFormData.category

    try {
      setSaving(true)
      await repairsApi.update(
        repairToEdit.id, 
        { ...editFormData, category: categoryToSave }, 
        editImages.length > 0 ? editImages : undefined
      )
      showToast('Repair updated successfully!', 'success')
      setRepairToEdit(null)
      setEditFormData({})
      setEditCustomCategory('')
      setEditImages([])
      loadRepairs()
    } catch (err: any) {
      showModal('Error', err.response?.data?.detail || err.message || 'Failed to update repair', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!repairToDelete) return
    try {
      await repairsApi.delete(repairToDelete)
      showToast('Repair deleted successfully!', 'success')
      setRepairToDelete(null)
      loadRepairs()
    } catch (err: any) {
      showModal('Error', err.response?.data?.detail || err.message || 'Failed to delete repair', 'error')
      setRepairToDelete(null)
    }
  }

  const handleDeleteImage = async () => {
    if (!imageToDelete) return
    const wasInEditMode = repairToEdit && repairToEdit.id === imageToDelete.repairId
    try {
      await repairsApi.deleteImage(imageToDelete.repairId, imageToDelete.imageIndex)
      showToast('Image deleted successfully!', 'success')
      
      // Reload repairs to get updated data
      await loadRepairs()
      
      // If we were in edit mode, refresh the edit form with updated repair data
      if (wasInEditMode) {
        // Wait a moment for state to update, then refresh edit form
        setTimeout(async () => {
          // Reload repairs again to ensure we have the latest data
          const response = await repairsApi.getAll()
          const updatedRepairs = Array.isArray(response.data) ? response.data : []
          const updatedRepair = updatedRepairs.find(r => r.id === imageToDelete.repairId)
          if (updatedRepair) {
            handleEdit(updatedRepair)
          }
        }, 100)
      }
      
      setImageToDelete(null)
    } catch (err: any) {
      showModal('Error', err.response?.data?.detail || err.message || 'Failed to delete image', 'error')
      setImageToDelete(null)
    }
  }

  const getTruckName = (truckId: number) => {
    const truck = trucks.find((t) => t.id === truckId)
    return truck?.name || `Truck ${truckId}`
  }

  const getImageUrl = (imagePath: string) => {
    if (imagePath.startsWith('http')) return imagePath
    return `/uploads/${encodeURIComponent(imagePath.split('/').pop() || imagePath)}`
  }

  const getPdfUrl = (pdfPath: string) => {
    if (pdfPath.startsWith('http')) return pdfPath
    const filename = pdfPath.split('/').pop() || pdfPath
    return `/uploads/${encodeURIComponent(filename)}`
  }

  if (loading) return <div className="text-center py-8">Loading repairs...</div>
  if (error) return <div className="text-center py-8 text-red-600">{error}</div>

  // Filter repairs based on search term
  const filteredRepairs = repairs.filter(repair => {
    if (!searchFilter.trim()) return true
    
    const searchLower = searchFilter.toLowerCase()
    const truckName = getTruckName(repair.truck_id).toLowerCase()
    const title = (repair.title || '').toLowerCase()
    const details = (repair.details || '').toLowerCase()
    const description = (repair.description || '').toLowerCase()
    const invoiceNumber = (repair.invoice_number || '').toLowerCase()
    const truckId = repair.truck_id.toString()
    
    return (
      truckName.includes(searchLower) ||
      title.includes(searchLower) ||
      details.includes(searchLower) ||
      description.includes(searchLower) ||
      invoiceNumber.includes(searchLower) ||
      truckId.includes(searchLower)
    )
  })

  return (
    <div>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Repairs</h1>
        <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:flex-initial sm:w-64">
            <input
              type="text"
              placeholder="Search by invoice #, description, or truck..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <svg className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            {searchFilter && (
              <button
                onClick={() => setSearchFilter('')}
                className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => {
                setShowManualForm(!showManualForm)
                setShowUploadForm(false)
                if (showManualForm) {
                  // Reset manual form state when closing
                  setManualFormData({
                    truck_id: undefined,
                    repair_date: undefined,
                    title: '',
                    details: '',
                    description: '',
                    category: '',
                    cost: undefined,
                    invoice_number: ''
                  })
                  setManualFormImages([])
                }
              }}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 whitespace-nowrap"
            >
              {showManualForm ? 'Cancel' : 'Add Repair Manually'}
            </button>
            <button
              onClick={() => {
                setShowUploadForm(!showUploadForm)
                setShowManualForm(false)
                if (showUploadForm) {
                  // Reset form state when closing
                  setUploadFile(null)
                  setUploadImages([])
                  setSelectedTruckForUpload(null)
                  setExtractedVin(null)
                  setRequiresTruckSelection(false)
                }
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 whitespace-nowrap"
            >
              {showUploadForm ? 'Cancel' : 'Upload Repair'}
            </button>
          </div>
        </div>
      </div>

      {showUploadForm && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Upload Repair Invoice</h2>
          <p className="text-sm text-gray-600 mb-4">
            {requiresTruckSelection 
              ? extractedVin
                ? `VIN ${extractedVin} was found in the invoice but doesn't match any truck. Please select the correct truck below and upload the file again.`
                : 'VIN could not be extracted from the invoice. Please select a truck manually and upload again.'
              : extractedVin
              ? `VIN found: ${extractedVin}. The truck will be matched automatically, or you can select manually.`
              : 'The truck will be automatically identified by the VIN number extracted from the invoice. If no VIN is found, you must select a truck manually.'}
          </p>
          <form onSubmit={handleUpload}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Truck {requiresTruckSelection ? '*' : '(Optional - will auto-detect from VIN if available)'}
              </label>
              <select
                value={selectedTruckForUpload || ''}
                onChange={(e) => setSelectedTruckForUpload(e.target.value ? Number(e.target.value) : null)}
                required={requiresTruckSelection}
                disabled={uploading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Auto-detect from VIN (or select manually)</option>
                {trucks.map((truck) => (
                  <option key={truck.id} value={truck.id}>
                    {truck.name} {truck.vin ? `(VIN: ${truck.vin})` : ''}
                  </option>
                ))}
              </select>
              {extractedVin && (
                <p className="mt-1 text-xs text-gray-500">
                  VIN {extractedVin} was found in the invoice. {requiresTruckSelection ? 'Please select a truck.' : 'Truck will be matched automatically if VIN matches.'}
                </p>
              )}
              {requiresTruckSelection && !extractedVin && (
                <p className="mt-1 text-xs text-red-600">
                  VIN not found - truck selection is required
                </p>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">PDF Invoice *</label>
                <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100 hover:border-blue-400 transition-colors">
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
                  {requiresTruckSelection 
                    ? 'VIN not found - truck selection required'
                    : 'VIN will be extracted automatically if present in invoice'}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Images (optional)</label>
                <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100 hover:border-blue-400 transition-colors">
                  <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    <svg className="w-10 h-10 mb-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p className="mb-2 text-sm text-gray-500">
                      <span className="font-semibold">Click to upload</span> or drag and drop
                    </p>
                    <p className="text-xs text-gray-500">Images (multiple allowed)</p>
                    {uploadImages.length > 0 && (
                      <p className="mt-2 text-xs font-medium text-blue-600">{uploadImages.length} file{uploadImages.length !== 1 ? 's' : ''} selected</p>
                    )}
                  </div>
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={(e) => setUploadImages(Array.from(e.target.files || []))}
                    disabled={uploading}
                    className="hidden"
                  />
                </label>
              </div>
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
          <h2 className="text-lg font-semibold mb-4">Add Repair Manually</h2>
          <p className="text-sm text-gray-600 mb-4">
            Use this form to add repairs when PDF invoices cannot be parsed or when adding repairs without invoices.
          </p>
          <form onSubmit={handleCreateManual}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Truck *</label>
                <select
                  value={manualFormData.truck_id || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, truck_id: e.target.value ? Number(e.target.value) : undefined })}
                  required
                  disabled={creating}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select a truck...</option>
                  {trucks.map((truck) => (
                    <option key={truck.id} value={truck.id}>
                      {truck.name} {truck.vin ? `(VIN: ${truck.vin})` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Repair Date</label>
                <input
                  type="date"
                  value={manualFormData.repair_date || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, repair_date: e.target.value || undefined })}
                  disabled={creating}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Cost</label>
                <input
                  type="number"
                  step="0.01"
                  value={manualFormData.cost || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, cost: e.target.value ? Number(e.target.value) : undefined })}
                  disabled={creating}
                  placeholder="0.00"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Category</label>
                <select
                  value={manualFormData.category || ''}
                  onChange={(e) => {
                    const selectedCategory = e.target.value || undefined
                    setManualFormData({ ...manualFormData, category: selectedCategory })
                    // Reset custom category if not "other"
                    if (selectedCategory !== 'other') {
                      setManualCustomCategory('')
                    }
                  }}
                  disabled={creating}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select category...</option>
                  <option value="engine">Engine</option>
                  <option value="tires">Tires</option>
                  <option value="maintenance">Maintenance</option>
                  <option value="electrical">Electrical</option>
                  <option value="brakes">Brakes</option>
                  <option value="suspension">Suspension</option>
                  <option value="body">Body</option>
                  <option value="other">Other</option>
                </select>
                {manualFormData.category === 'other' && (
                  <input
                    type="text"
                    value={manualCustomCategory}
                    onChange={(e) => setManualCustomCategory(e.target.value)}
                    disabled={creating}
                    placeholder="Enter custom category..."
                    className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                )}
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Title</label>
                <input
                  type="text"
                  value={manualFormData.title || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, title: e.target.value || undefined })}
                  disabled={creating}
                  placeholder="Short title for this repair..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Details</label>
                <textarea
                  value={manualFormData.details || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, details: e.target.value || undefined })}
                  disabled={creating}
                  rows={4}
                  placeholder="Detailed description of the repair work..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Description (Legacy)</label>
                <textarea
                  value={manualFormData.description || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, description: e.target.value || undefined })}
                  disabled={creating}
                  rows={3}
                  placeholder="Description of repair work..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Invoice Number</label>
                <input
                  type="text"
                  value={manualFormData.invoice_number || ''}
                  onChange={(e) => setManualFormData({ ...manualFormData, invoice_number: e.target.value || undefined })}
                  disabled={creating}
                  placeholder="Optional"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Images (optional)</label>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(e) => setManualFormImages(Array.from(e.target.files || []))}
                  disabled={creating}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {manualFormImages.length > 0 && (
                  <p className="mt-1 text-xs text-gray-500">{manualFormImages.length} image(s) selected</p>
                )}
              </div>
            </div>
            <button
              type="submit"
              disabled={creating || !manualFormData.truck_id}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              {creating ? 'Creating...' : 'Create Repair'}
            </button>
          </form>
        </div>
      )}

      {searchFilter && (
        <div className="mb-4 text-sm text-gray-600">
          Showing {filteredRepairs.length} of {repairs.length} repair{repairs.length !== 1 ? 's' : ''}
        </div>
      )}

      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {filteredRepairs.length === 0 ? (
            <li className="px-6 py-4 text-gray-500 text-center">
              {searchFilter ? `No repairs found matching "${searchFilter}"` : 'No repairs found.'}
            </li>
          ) : (
            filteredRepairs.map((repair) => (
              <li key={repair.id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <h3 className="text-xl font-semibold text-gray-900 mb-1">
                          {repair.title || repair.description || 'Untitled Repair'}
                        </h3>
                        {repair.details && (
                          <p className="text-sm text-gray-600 mb-2">{repair.details}</p>
                        )}
                        <p className="text-sm text-gray-500">
                          {getTruckName(repair.truck_id)} - {new Date(repair.repair_date).toLocaleDateString()}
                          {repair.category && <span className="ml-2 text-xs bg-gray-100 px-2 py-1 rounded">{repair.category}</span>}
                        </p>
                        <p className="text-sm font-semibold text-red-600">${repair.cost.toLocaleString()}</p>
                      </div>
                      {repair.invoice_number && (
                        <div className="text-right">
                          <p className="text-xs text-gray-400 mb-1">Invoice #</p>
                          <p className="text-sm font-mono font-semibold text-gray-700">{repair.invoice_number}</p>
                        </div>
                      )}
                    </div>
                    {repair.receipt_path && (
                      <div className="mt-2">
                        <button
                          onClick={() => window.open(getPdfUrl(repair.receipt_path!), '_blank')}
                          className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          View Invoice
                        </button>
                      </div>
                    )}
                    {repair.image_paths && Array.isArray(repair.image_paths) && repair.image_paths.length > 0 && (
                      <div className="mt-2 flex gap-2 flex-wrap">
                        {repair.image_paths.map((img, idx) => (
                          <div key={idx} className="relative group">
                            <button
                              onClick={() => window.open(getImageUrl(img), '_blank')}
                              className="relative cursor-pointer"
                            >
                              <img
                                src={getImageUrl(img)}
                                alt={`Repair ${idx + 1}`}
                                className="w-20 h-20 object-cover rounded border hover:opacity-80 transition-opacity"
                              />
                              <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-30 rounded border border-transparent group-hover:border-blue-400 transition-all flex items-center justify-center">
                                <svg className="w-5 h-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                                </svg>
                              </div>
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                setImageToDelete({ repairId: repair.id, imageIndex: idx })
                              }}
                              className="absolute -top-2 -right-2 bg-red-600 text-white rounded-full w-6 h-6 flex items-center justify-center hover:bg-red-700 transition-colors shadow-lg z-10"
                              title="Delete image"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEdit(repair)}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setRepairToDelete(repair.id)}
                      className="text-red-600 hover:text-red-800"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </li>
            ))
          )}
        </ul>
      </div>

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={modalTitle} type={modalType}>
        {modalMessage}
      </Modal>

      {repairToEdit && (
        <Modal
          isOpen={repairToEdit !== null}
          onClose={() => {
            setRepairToEdit(null)
            setEditFormData({})
            setEditCustomCategory('')
            setEditImages([])
          }}
          title="Edit Repair"
          type="info"
          showFooter={false}
        >
          <div className="space-y-6">
            {/* PDF Invoice Section */}
            {repairToEdit.receipt_path && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-lg font-medium text-gray-900">Invoice PDF</h4>
                  <button
                    onClick={() => window.open(getPdfUrl(repairToEdit.receipt_path!), '_blank')}
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    Open in New Tab
                  </button>
                </div>
                <div className="w-full h-[600px] border border-gray-300 rounded-lg bg-gray-50 overflow-hidden">
                  <iframe
                    src={getPdfUrl(repairToEdit.receipt_path)}
                    className="w-full h-full border-0"
                    title="Repair Invoice PDF"
                  />
                </div>
              </div>
            )}
            
            {/* Edit Form */}
            <form onSubmit={handleSaveEdit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Truck</label>
              <select
                value={editFormData.truck_id || ''}
                onChange={(e) => setEditFormData({ ...editFormData, truck_id: Number(e.target.value) })}
                required
                disabled={saving}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {trucks.map((truck) => (
                  <option key={truck.id} value={truck.id}>
                    {truck.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Repair Date</label>
              <input
                type="date"
                value={editFormData.repair_date ? new Date(editFormData.repair_date).toISOString().split('T')[0] : ''}
                onChange={(e) => setEditFormData({ ...editFormData, repair_date: e.target.value })}
                required
                disabled={saving}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
              <input
                type="text"
                value={editFormData.title || ''}
                onChange={(e) => setEditFormData({ ...editFormData, title: e.target.value })}
                disabled={saving}
                placeholder="Short title for this repair..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Details</label>
              <textarea
                value={editFormData.details || ''}
                onChange={(e) => setEditFormData({ ...editFormData, details: e.target.value })}
                disabled={saving}
                rows={4}
                placeholder="Detailed description of the repair work..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description (Legacy)</label>
              <textarea
                value={editFormData.description || ''}
                onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
                disabled={saving}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
              <select
                value={editFormData.category || ''}
                onChange={(e) => {
                  const selectedCategory = e.target.value
                  setEditFormData({ ...editFormData, category: selectedCategory })
                  // Reset custom category if not "other"
                  if (selectedCategory !== 'other') {
                    setEditCustomCategory('')
                  }
                }}
                disabled={saving}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select category...</option>
                <option value="engine">Engine</option>
                <option value="tires">Tires</option>
                <option value="electrical">Electrical</option>
                <option value="brakes">Brakes</option>
                <option value="maintenance">Maintenance</option>
                <option value="suspension">Suspension</option>
                <option value="body">Body</option>
                <option value="other">Other</option>
              </select>
              {editFormData.category === 'other' && (
                <input
                  type="text"
                  value={editCustomCategory}
                  onChange={(e) => setEditCustomCategory(e.target.value)}
                  disabled={saving}
                  placeholder="Enter custom category..."
                  className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Cost ($)</label>
              <input
                type="number"
                step="0.01"
                value={editFormData.cost || ''}
                onChange={(e) => setEditFormData({ ...editFormData, cost: parseFloat(e.target.value) })}
                required
                disabled={saving}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Add Images (optional)</label>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => setEditImages(Array.from(e.target.files || []))}
                disabled={saving}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              {repairToEdit.image_paths && Array.isArray(repairToEdit.image_paths) && repairToEdit.image_paths.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-gray-500 mb-2">Existing images ({repairToEdit.image_paths.length}):</p>
                  <div className="flex gap-2 flex-wrap">
                    {repairToEdit.image_paths.map((img, idx) => (
                      <div key={idx} className="relative">
                        <img
                          src={getImageUrl(img)}
                          alt={`Existing ${idx + 1}`}
                          className="w-16 h-16 object-cover rounded border"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            setImageToDelete({ repairId: repairToEdit.id, imageIndex: idx })
                          }}
                          className="absolute -top-1 -right-1 bg-red-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs hover:bg-red-700 shadow-lg"
                          title="Delete image"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {editImages.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-gray-500 mb-2">New images to add ({editImages.length}):</p>
                  <div className="flex gap-2 flex-wrap">
                    {editImages.map((img, idx) => (
                      <div key={idx} className="relative">
                        <img
                          src={URL.createObjectURL(img)}
                          alt={`New ${idx + 1}`}
                          className="w-16 h-16 object-cover rounded border"
                        />
                        <button
                          type="button"
                          onClick={() => setEditImages(editImages.filter((_, i) => i !== idx))}
                          className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs hover:bg-red-600"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-2 justify-end pt-4">
              <button
                type="button"
                onClick={() => {
                  setRepairToEdit(null)
                  setEditFormData({})
                  setEditImages([])
                }}
                disabled={saving}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
            </form>
          </div>
        </Modal>
      )}

      <ConfirmModal
        isOpen={repairToDelete !== null}
        onClose={() => setRepairToDelete(null)}
        onConfirm={handleDelete}
        title="Delete Repair"
        message="Are you sure you want to delete this repair? This action cannot be undone."
        confirmText="Delete"
        type="danger"
      />

      <ConfirmModal
        isOpen={imageToDelete !== null}
        onClose={() => setImageToDelete(null)}
        onConfirm={handleDeleteImage}
        title="Delete Image"
        message="Are you sure you want to delete this image? This action cannot be undone."
        confirmText="Delete"
        type="danger"
      />

      <Toast
        message={toast.message}
        type={toast.type}
        isVisible={toast.isVisible}
        onClose={() => setToast({ ...toast, isVisible: false })}
      />
    </div>
  )
}
