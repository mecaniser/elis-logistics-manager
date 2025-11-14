import { useEffect, useState } from 'react'
import { settlementsApi, trucksApi, Settlement, Truck } from '../services/api'
import Modal from '../components/Modal'
import ConfirmModal from '../components/ConfirmModal'

export default function Settlements() {
  const [settlements, setSettlements] = useState<Settlement[]>([])
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTruck, setSelectedTruck] = useState<number | null>(null)
  const [showUploadForm, setShowUploadForm] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadFiles, setUploadFiles] = useState<File[]>([])
  const [uploadMode, setUploadMode] = useState<'single' | 'bulk'>('single')
  const [uploading, setUploading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalMessage, setModalMessage] = useState<string | React.ReactNode>('')
  const [modalType, setModalType] = useState<'success' | 'error' | 'warning' | 'info'>('info')
  const [settlementToDelete, setSettlementToDelete] = useState<number | null>(null)
  const [selectedSettlements, setSelectedSettlements] = useState<Set<number>>(new Set())
  const [deleteMode, setDeleteMode] = useState(false)
  const [selectedTruckForUpload, setSelectedTruckForUpload] = useState<number | null>(null)
  const [selectedSettlementType, setSelectedSettlementType] = useState<string>('')
  const [editingSettlement, setEditingSettlement] = useState<Settlement | null>(null)
  const [editFormData, setEditFormData] = useState<Partial<Settlement>>({})
  const [expenseCategoryInputs, setExpenseCategoryInputs] = useState<{ [key: string]: string }>({})
  
  const SETTLEMENT_TYPES = [
    'Owner Operator Income Sheet',
    '277 Logistics',
    'NBM Transport LLC'
  ]

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
      setTrucks(response.data)
    } catch (err) {
      console.error(err)
    }
  }

  const loadSettlements = async () => {
    try {
      setLoading(true)
      const response = await settlementsApi.getAll(selectedTruck || undefined)
      setSettlements(response.data)
    } catch (err: any) {
      setError(err.message || 'Failed to load settlements')
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
    if (!selectedSettlementType) {
      showModal('Error', 'Please select a settlement type', 'error')
      return
    }

    try {
      setUploading(true)
      if (uploadMode === 'bulk' && uploadFiles.length > 0) {
        const response = await settlementsApi.uploadBulk(uploadFiles, selectedTruckForUpload || undefined, selectedSettlementType)
        const { successful, failed, results } = response.data
        
        if (failed > 0) {
          const errorList = results
            .filter(r => !r.success)
            .map(r => `• ${r.filename}: ${r.error || 'Unknown error'}`)
            .join('\n')
          
          showModal(
            'Bulk Upload Partial Success',
            <div className="max-h-96 overflow-y-auto">
              <p className="mb-2">Uploaded {successful} of {results.length} settlement(s). {failed} failed.</p>
              <div className="text-left">
                <p className="font-semibold mb-1">Errors:</p>
                <pre className="text-xs whitespace-pre-wrap">{errorList}</pre>
              </div>
            </div>,
            'warning'
          )
        } else {
          showModal('Success', `Successfully uploaded ${successful} settlement(s)!`, 'success')
        }
      } else if (uploadFile) {
        await settlementsApi.upload(uploadFile, selectedTruckForUpload || undefined, selectedSettlementType)
        showModal('Success', 'Settlement uploaded successfully!', 'success')
      }
      
      setUploadFile(null)
      setUploadFiles([])
      setSelectedTruckForUpload(null)
      setSelectedSettlementType('')
      setShowUploadForm(false)
      loadSettlements()
    } catch (err: any) {
      showModal('Upload Failed', err.response?.data?.detail || err.message || 'Failed to upload settlement', 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async () => {
    if (!settlementToDelete) return
    try {
      await settlementsApi.delete(settlementToDelete)
      showModal('Success', 'Settlement deleted successfully!', 'success')
      setSettlementToDelete(null)
      loadSettlements()
    } catch (err: any) {
      showModal('Error', err.response?.data?.detail || err.message || 'Failed to delete settlement', 'error')
      setSettlementToDelete(null)
    }
  }

  const handleBulkDelete = async () => {
    try {
      await Promise.all(Array.from(selectedSettlements).map(id => settlementsApi.delete(id)))
      showModal('Success', `Successfully deleted ${selectedSettlements.size} settlement(s)!`, 'success')
      setSelectedSettlements(new Set())
      setDeleteMode(false)
      loadSettlements()
    } catch (err: any) {
      showModal('Error', err.response?.data?.detail || err.message || 'Failed to delete settlements', 'error')
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
    if (selectedSettlements.size === settlements.length) {
      setSelectedSettlements(new Set())
    } else {
      setSelectedSettlements(new Set(settlements.map(s => s.id)))
    }
  }

  const getTruckName = (truckId: number) => {
    const truck = trucks.find((t) => t.id === truckId)
    return truck?.name || `Truck ${truckId}`
  }

  const getPdfUrl = (pdfPath: string) => {
    if (pdfPath.startsWith('http')) return pdfPath
    const filename = pdfPath.split('/').pop() || pdfPath
    return `/uploads/${encodeURIComponent(filename)}`
  }

  const handleEditSettlement = (settlement: Settlement) => {
    setEditingSettlement(settlement)
    const categories = settlement.expense_categories || {}
    setEditFormData({
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
      net_profit: settlement.net_profit || undefined,
      license_plate: settlement.license_plate || undefined,
      settlement_type: settlement.settlement_type || undefined,
    })
    const inputValues: { [key: string]: string } = {}
    Object.entries(categories).forEach(([key, value]) => {
      inputValues[key] = value === 0 ? '' : String(value)
    })
    setExpenseCategoryInputs(inputValues)
  }

  const handleCancelEdit = () => {
    setEditingSettlement(null)
    setEditFormData({})
    setExpenseCategoryInputs({})
  }

  const handleSaveEdit = async () => {
    if (!editingSettlement) return
    try {
      await settlementsApi.update(editingSettlement.id, editFormData)
      await loadSettlements()
      showModal('Success', 'Settlement updated successfully!', 'success')
      handleCancelEdit()
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to update settlement'
      showModal('Update Failed', errorMessage, 'error')
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
    const totalExpenses = Object.values(updated).reduce((sum, val) => sum + (val || 0), 0)
    setEditFormData({
      ...editFormData,
      expense_categories: updated,
      expenses: totalExpenses,
      net_profit: editFormData.gross_revenue && totalExpenses 
        ? editFormData.gross_revenue - totalExpenses 
        : editFormData.net_profit
    })
  }

  const handleExpenseCategoryAmountChange = (key: string, value: string) => {
    setExpenseCategoryInputs(prev => ({ ...prev, [key]: value }))
    if (!editFormData.expense_categories) {
      setEditFormData({ ...editFormData, expense_categories: {} })
      return
    }
    if (value === '' || value === '.') {
      const updated = { ...editFormData.expense_categories }
      updated[key] = 0
      const totalExpenses = Object.values(updated).reduce((sum, val) => sum + (val || 0), 0)
      setEditFormData({
        ...editFormData,
        expense_categories: updated,
        expenses: totalExpenses,
        net_profit: editFormData.gross_revenue && totalExpenses 
          ? editFormData.gross_revenue - totalExpenses 
          : editFormData.net_profit
      })
      return
    }
    let cleanedValue = value
    if (value.startsWith('0') && value.length > 1 && value[1] !== '.') {
      cleanedValue = value.replace(/^0+(?=\d)/, '')
    }
    const numValue = parseFloat(cleanedValue)
    const updated = { ...editFormData.expense_categories }
    updated[key] = isNaN(numValue) ? 0 : numValue
    const totalExpenses = Object.values(updated).reduce((sum, val) => sum + (val || 0), 0)
    setEditFormData({
      ...editFormData,
      expense_categories: updated,
      expenses: totalExpenses,
      net_profit: editFormData.gross_revenue && totalExpenses 
        ? editFormData.gross_revenue - totalExpenses 
        : editFormData.net_profit
    })
  }

  const handleAddExpenseCategory = () => {
    const newKey = prompt('Enter category name:')
    if (newKey && newKey.trim()) {
      const updated = {
        ...editFormData.expense_categories,
        [newKey.trim()]: 0
      }
      setEditFormData({ ...editFormData, expense_categories: updated })
      setExpenseCategoryInputs(prev => ({ ...prev, [newKey.trim()]: '' }))
    }
  }

  const handleRemoveExpenseCategory = (key: string) => {
    if (!editFormData.expense_categories) return
    const updated = { ...editFormData.expense_categories }
    delete updated[key]
    const totalExpenses = Object.values(updated).reduce((sum, val) => sum + (val || 0), 0)
    setEditFormData({
      ...editFormData,
      expense_categories: updated,
      expenses: totalExpenses,
      net_profit: editFormData.gross_revenue && totalExpenses 
        ? editFormData.gross_revenue - totalExpenses 
        : editFormData.net_profit
    })
    const newInputs = { ...expenseCategoryInputs }
    delete newInputs[key]
    setExpenseCategoryInputs(newInputs)
  }

  if (loading) return <div className="text-center py-8">Loading settlements...</div>
  if (error) return <div className="text-center py-8 text-red-600">{error}</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Settlements</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setDeleteMode(!deleteMode)}
            className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            {deleteMode ? 'Cancel Delete' : 'Delete Mode'}
          </button>
          <button
            onClick={() => setShowUploadForm(!showUploadForm)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            {showUploadForm ? 'Cancel' : 'Upload Settlement'}
          </button>
        </div>
      </div>

      {showUploadForm && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Upload Settlement</h2>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">Upload Mode</label>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  value="single"
                  checked={uploadMode === 'single'}
                  onChange={(e) => setUploadMode(e.target.value as 'single' | 'bulk')}
                  className="mr-2"
                />
                Single File
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  value="bulk"
                  checked={uploadMode === 'bulk'}
                  onChange={(e) => setUploadMode(e.target.value as 'single' | 'bulk')}
                  className="mr-2"
                />
                Multiple Files
              </label>
            </div>
          </div>
          <form onSubmit={handleUpload}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Settlement Type *</label>
              <select
                value={selectedSettlementType}
                onChange={(e) => setSelectedSettlementType(e.target.value)}
                required
                disabled={uploading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select settlement type...</option>
                {SETTLEMENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Truck (Optional - will auto-detect from license plate if not selected)
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
                    {truck.name} {truck.license_plate ? `(${truck.license_plate})` : ''}
                  </option>
                ))}
              </select>
            </div>
            {uploadMode === 'single' ? (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">PDF File *</label>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  required
                  disabled={uploading}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            ) : (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">PDF Files *</label>
                <input
                  type="file"
                  accept=".pdf"
                  multiple
                  onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
                  required
                  disabled={uploading}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            )}
            <button
              type="submit"
              disabled={uploading || !selectedSettlementType || (uploadMode === 'single' ? !uploadFile : uploadFiles.length === 0)}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </form>
        </div>
      )}

      {deleteMode && selectedSettlements.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div className="flex justify-between items-center">
            <div className="text-sm font-medium text-blue-900">
              {selectedSettlements.size} settlement{selectedSettlements.size !== 1 ? 's' : ''} selected
            </div>
            <button
              onClick={() => setSettlementToDelete(0)}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
            >
              Delete Selected
            </button>
          </div>
        </div>
      )}

      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {settlements.length === 0 ? (
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
                  className={`px-6 py-4 ${deleteMode ? 'hover:bg-gray-50' : 'hover:bg-gray-50 cursor-pointer'} transition-colors`}
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
                          {settlement.net_profit && (
                            <div>
                              <span className="text-gray-500">Profit: </span>
                              <span className="font-medium text-blue-600">
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
              className="relative transform overflow-hidden rounded-lg bg-white shadow-xl transition-all w-full max-w-7xl mx-4 max-h-[90vh] flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
                <h3 className="text-xl font-semibold text-gray-900">
                  Edit Settlement - {getTruckName(editingSettlement.truck_id)} - {new Date(editingSettlement.settlement_date).toLocaleDateString()}
                </h3>
                <button onClick={handleCancelEdit} className="text-gray-400 hover:text-gray-500">
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="lg:sticky lg:top-0">
                    <h4 className="text-lg font-medium text-gray-900 mb-3">PDF Document</h4>
                    {editingSettlement.pdf_file_path ? (
                      <iframe
                        src={getPdfUrl(editingSettlement.pdf_file_path)}
                        className="w-full h-[600px] border border-gray-300 rounded-lg"
                        title="Settlement PDF"
                      />
                    ) : (
                      <div className="w-full h-[600px] border border-gray-300 rounded-lg flex items-center justify-center bg-gray-50">
                        <p className="text-gray-500">No PDF available</p>
                      </div>
                    )}
                  </div>
                  <div className="space-y-4">
                    <h4 className="text-lg font-medium text-gray-900 mb-3">Settlement Data</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Truck</label>
                        <select
                          value={editFormData.truck_id || ''}
                          onChange={(e) => setEditFormData({ ...editFormData, truck_id: Number(e.target.value) })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          {trucks.map((truck) => (
                            <option key={truck.id} value={truck.id}>{truck.name}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Settlement Date</label>
                        <input
                          type="date"
                          value={editFormData.settlement_date || ''}
                          onChange={(e) => setEditFormData({ ...editFormData, settlement_date: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Gross Revenue</label>
                        <input
                          type="number"
                          step="0.01"
                          value={editFormData.gross_revenue || ''}
                          onChange={(e) => {
                            const revenue = e.target.value ? Number(e.target.value) : undefined
                            const expenses = editFormData.expenses || 0
                            setEditFormData({
                              ...editFormData,
                              gross_revenue: revenue,
                              net_profit: revenue && expenses ? revenue - expenses : editFormData.net_profit
                            })
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Total Expenses</label>
                        <input
                          type="number"
                          step="0.01"
                          value={editFormData.expenses || ''}
                          onChange={(e) => {
                            const expenses = e.target.value ? Number(e.target.value) : undefined
                            const revenue = editFormData.gross_revenue || 0
                            setEditFormData({
                              ...editFormData,
                              expenses: expenses,
                              net_profit: revenue && expenses ? revenue - expenses : editFormData.net_profit
                            })
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Net Profit</label>
                        <input
                          type="number"
                          step="0.01"
                          value={editFormData.net_profit || ''}
                          onChange={(e) => {
                            const profit = e.target.value ? Number(e.target.value) : undefined
                            const revenue = editFormData.gross_revenue || 0
                            setEditFormData({
                              ...editFormData,
                              net_profit: profit,
                              expenses: revenue && profit ? revenue - profit : editFormData.expenses
                            })
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    </div>
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
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {editFormData.expense_categories && Object.entries(editFormData.expense_categories).map(([key, value]) => (
                          <div key={key} className="flex items-center gap-2">
                            <input
                              type="text"
                              value={key}
                              onChange={(e) => {
                                const newKey = e.target.value
                                if (newKey !== key) {
                                  handleExpenseCategoryChange(key, newKey, value || 0)
                                }
                              }}
                              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                            />
                            <input
                              type="text"
                              inputMode="decimal"
                              value={expenseCategoryInputs[key] !== undefined ? expenseCategoryInputs[key] : (value === 0 ? '' : String(value))}
                              onChange={(e) => {
                                const inputValue = e.target.value
                                if (inputValue === '' || /^\d*\.?\d*$/.test(inputValue)) {
                                  handleExpenseCategoryAmountChange(key, inputValue)
                                }
                              }}
                              onBlur={(e) => {
                                const inputValue = e.target.value.trim()
                                if (inputValue === '' || inputValue === '.') {
                                  handleExpenseCategoryChange(key, key, 0)
                                  setExpenseCategoryInputs(prev => ({ ...prev, [key]: '' }))
                                } else {
                                  const numValue = parseFloat(inputValue)
                                  if (!isNaN(numValue)) {
                                    handleExpenseCategoryChange(key, key, numValue)
                                    setExpenseCategoryInputs(prev => ({ ...prev, [key]: String(numValue) }))
                                  }
                                }
                              }}
                              className="w-32 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                              placeholder="0.00"
                            />
                            <button
                              type="button"
                              onClick={() => handleRemoveExpenseCategory(key)}
                              className="text-red-600 hover:text-red-800 px-2"
                            >
                              ✕
                            </button>
                          </div>
                        ))}
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
    </div>
  )
}
