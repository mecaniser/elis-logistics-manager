import { useState } from 'react'
import Toast from '../components/Toast'
import Modal from '../components/Modal'

interface ExtractedSettlement {
  metadata: {
    settlement_date: string | null
    week_start: string | null
    week_end: string | null
    settlement_type: string | null
    license_plate: string | null
    driver_id: number | null
    driver_name: string | null
  }
  revenue: {
    gross_revenue: number
    net_profit: number
  }
  expenses: {
    total_expenses: number
    categories: { [key: string]: number }
  }
  metrics: {
    miles_driven: number
    blocks_delivered: number
  }
  driver_pay: {
    driver_pay: number
    payroll_fee: number
  }
}

interface ExtractedData {
  source_file: string
  extraction_date: string
  settlement_type: string
  settlements: ExtractedSettlement[]
  pdf_filename?: string
}

export default function Extractor() {
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadFiles, setUploadFiles] = useState<File[]>([])
  const [uploadMode, setUploadMode] = useState<'single' | 'bulk'>('single')
  const [uploading, setUploading] = useState(false)
  const [selectedSettlementType, setSelectedSettlementType] = useState<string>('')
  const [consolidatedMode, setConsolidatedMode] = useState<boolean>(false)
  const [extractedSettlements, setExtractedSettlements] = useState<ExtractedData[]>([])
  const [selectedSettlement, setSelectedSettlement] = useState<{ data: ExtractedData; settlement: ExtractedSettlement; index: number } | null>(null)
  const [showJsonData, setShowJsonData] = useState<boolean>(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info'; isVisible: boolean }>({
    message: '',
    type: 'info',
    isVisible: false
  })

  const SETTLEMENT_TYPES = [
    'Owner Operator Income Sheet',
    '277 Logistics',
    'NBM Transport LLC'
  ]

  const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info') => {
    setToast({ message, type, isVisible: true })
  }

  // Get all PDFs (treating multi-truck PDFs as single units)
  const getAllPDFs = (): Array<{ data: ExtractedData; pdfIndex: number }> => {
    return extractedSettlements.map((extractedData, index) => ({
      data: extractedData,
      pdfIndex: index
    }))
  }

  // Navigate to previous/next PDF (not individual settlements)
  const navigateSettlement = (direction: 'prev' | 'next') => {
    if (!selectedSettlement) return
    
    const allPDFs = getAllPDFs()
    const currentPDFIndex = allPDFs.findIndex(
      pdf => pdf.data.source_file === selectedSettlement.data.source_file
    )
    
    if (currentPDFIndex === -1) return
    
    let newPDFIndex: number
    if (direction === 'prev') {
      newPDFIndex = currentPDFIndex - 1
    } else {
      newPDFIndex = currentPDFIndex + 1
    }
    
    if (newPDFIndex >= 0 && newPDFIndex < allPDFs.length) {
      const newPDF = allPDFs[newPDFIndex]
      // Always show first settlement (index 0) since we display all trucks together for multi-truck PDFs
      setSelectedSettlement({
        data: newPDF.data,
        settlement: newPDF.data.settlements[0],
        index: 0
      })
      // Reset JSON visibility when navigating to a new settlement
      setShowJsonData(false)
    }
  }

  // Get navigation state (count PDFs, not individual settlements)
  const getNavigationState = () => {
    if (!selectedSettlement) return { canGoPrev: false, canGoNext: false, current: 0, total: 0 }
    
    const allPDFs = getAllPDFs()
    const currentPDFIndex = allPDFs.findIndex(
      pdf => pdf.data.source_file === selectedSettlement.data.source_file
    )
    
    if (currentPDFIndex === -1) return { canGoPrev: false, canGoNext: false, current: 0, total: 0 }
    
    return {
      canGoPrev: currentPDFIndex > 0,
      canGoNext: currentPDFIndex < allPDFs.length - 1,
      current: currentPDFIndex + 1,
      total: allPDFs.length
    }
  }

  const handleExtract = async (e: React.FormEvent) => {
    e.preventDefault()
    // Settlement type is optional - extractor will auto-detect if not provided

    try {
      setUploading(true)
      setExtractedSettlements([])
      
      if (uploadMode === 'bulk' && uploadFiles.length > 0) {
        // Bulk extraction - get data first
        const formData = new FormData()
        uploadFiles.forEach((file) => {
          formData.append('files', file)
        })
        if (selectedSettlementType) {
          formData.append('settlement_type', selectedSettlementType)
        }

        // Get extracted data for display
        const dataResponse = await fetch('/api/extractor/extract-bulk-data', {
          method: 'POST',
          body: formData,
        })

        if (!dataResponse.ok) {
          const error = await dataResponse.json()
          throw new Error(error.detail || 'Failed to extract PDFs')
        }

        const dataResult = await dataResponse.json()
        setExtractedSettlements(Array.isArray(dataResult.extracted_data) ? dataResult.extracted_data : [])

        // Also download file (ZIP or consolidated JSON)
        const downloadFormData = new FormData()
        uploadFiles.forEach((file) => {
          downloadFormData.append('files', file)
        })
        if (selectedSettlementType) {
          downloadFormData.append('settlement_type', selectedSettlementType)
        }
        downloadFormData.append('individual_files', consolidatedMode ? 'false' : 'true')
        downloadFormData.append('consolidated', consolidatedMode ? 'true' : 'false')

        const downloadResponse = await fetch('/api/extractor/extract-bulk', {
          method: 'POST',
          body: downloadFormData,
        })

        if (downloadResponse.ok) {
          const blob = await downloadResponse.blob()
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = consolidatedMode ? 'settlements_consolidated.json' : 'settlements_extracted.zip'
          document.body.appendChild(a)
          a.click()
          window.URL.revokeObjectURL(url)
          document.body.removeChild(a)
        }

        showToast(`Successfully extracted ${dataResult.processed_settlements} settlement(s) from ${dataResult.total_files} PDF(s)!`, 'success')
      } else if (uploadFile) {
        // Single file extraction - get data first
        const formData = new FormData()
        formData.append('file', uploadFile)
        if (selectedSettlementType) {
          formData.append('settlement_type', selectedSettlementType)
        }

        // Get extracted data for display
        const dataResponse = await fetch('/api/extractor/extract-data', {
          method: 'POST',
          body: formData,
        })

        if (!dataResponse.ok) {
          const error = await dataResponse.json()
          throw new Error(error.detail || 'Failed to extract PDF')
        }

        const extractedData = await dataResponse.json()
        setExtractedSettlements([extractedData])

        // Also download JSON file
        const downloadFormData = new FormData()
        downloadFormData.append('file', uploadFile)
        if (selectedSettlementType) {
          downloadFormData.append('settlement_type', selectedSettlementType)
        }
        downloadFormData.append('individual_files', 'true')

        const downloadResponse = await fetch('/api/extractor/extract', {
          method: 'POST',
          body: downloadFormData,
        })

        if (downloadResponse.ok) {
          const blob = await downloadResponse.blob()
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          
          const contentDisposition = downloadResponse.headers.get('Content-Disposition')
          let filename = 'settlement_extracted.json'
          if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i)
            if (filenameMatch) {
              filename = filenameMatch[1]
            }
          }
          
          a.download = filename
          document.body.appendChild(a)
          a.click()
          window.URL.revokeObjectURL(url)
          document.body.removeChild(a)
        }

        showToast('Successfully extracted PDF!', 'success')
      } else {
        showToast('Please select a file to extract', 'error')
        setUploading(false)
        return
      }
      
      setUploadFile(null)
      setUploadFiles([])
      setSelectedSettlementType('')
    } catch (err: any) {
      console.error('Extraction error:', err)
      const errorMessage = err.message || 'Failed to extract PDF'
      showToast(errorMessage, 'error')
    } finally {
      setUploading(false)
    }
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value)
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A'
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    } catch {
      return dateString
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Settlement Extractor</h1>
      </div>

      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Extract Settlement PDFs to JSON</h2>
        <p className="text-sm text-gray-600 mb-6">
          Upload settlement PDFs to extract structured JSON data. 
          {uploadMode === 'bulk' && (
            <> Choose between individual JSON files (ZIP) or a single consolidated JSON file ready for database import.</>
          )}
          {uploadMode === 'single' && (
            <> PDFs are processed and then deleted - only the extracted JSON data is kept.</>
          )}
        </p>

        <form onSubmit={handleExtract}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Extraction Mode</label>
            <div className="flex gap-2">
              <label className="cursor-pointer">
                <input
                  type="radio"
                  value="single"
                  checked={uploadMode === 'single'}
                  onChange={(e) => setUploadMode(e.target.value as 'single' | 'bulk')}
                  className="sr-only"
                />
                <div className={`px-3 py-1.5 border-2 rounded-md text-center text-sm transition-colors whitespace-nowrap ${
                  uploadMode === 'single'
                    ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium'
                    : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                }`}>
                  Single File
                </div>
              </label>
              <label className="cursor-pointer">
                <input
                  type="radio"
                  value="bulk"
                  checked={uploadMode === 'bulk'}
                  onChange={(e) => setUploadMode(e.target.value as 'single' | 'bulk')}
                  className="sr-only"
                />
                <div className={`px-3 py-1.5 border-2 rounded-md text-center text-sm transition-colors whitespace-nowrap ${
                  uploadMode === 'bulk'
                    ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium'
                    : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                }`}>
                  Multiple Files
                </div>
              </label>
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Settlement Type <span className="text-gray-400 text-xs">(optional - auto-detected if not selected)</span>
            </label>
            <select
              value={selectedSettlementType}
              onChange={(e) => setSelectedSettlementType(e.target.value)}
              disabled={uploading}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Auto-detect from PDF...</option>
              {SETTLEMENT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              The extractor will automatically detect the settlement type from the PDF content if not specified.
            </p>
          </div>

          {uploadMode === 'bulk' && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">Output Format</label>
              <div className="flex gap-2">
                <label className="cursor-pointer flex-1">
                  <input
                    type="radio"
                    name="outputFormat"
                    checked={!consolidatedMode}
                    onChange={() => setConsolidatedMode(false)}
                    disabled={uploading}
                    className="sr-only"
                  />
                  <div className={`px-3 py-2 border-2 rounded-md text-center text-sm transition-colors ${
                    !consolidatedMode
                      ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium'
                      : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                  }`}>
                    Individual Files (ZIP)
                  </div>
                </label>
                <label className="cursor-pointer flex-1">
                  <input
                    type="radio"
                    name="outputFormat"
                    checked={consolidatedMode}
                    onChange={() => setConsolidatedMode(true)}
                    disabled={uploading}
                    className="sr-only"
                  />
                  <div className={`px-3 py-2 border-2 rounded-md text-center text-sm transition-colors ${
                    consolidatedMode
                      ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium'
                      : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                  }`}>
                    Consolidated JSON
                  </div>
                </label>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {consolidatedMode 
                  ? 'Creates a single JSON file with all settlements ready for database import'
                  : 'Creates a ZIP file with individual JSON files (one per settlement)'}
              </p>
            </div>
          )}

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
              {uploadFiles.length > 0 && (
                <p className="mt-2 text-sm text-gray-600">
                  {uploadFiles.length} file(s) selected
                </p>
              )}
            </div>
          )}

          <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
            <div className="flex items-start">
              <svg className="w-5 h-5 text-blue-600 mt-0.5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="text-sm text-blue-800">
                <p className="font-medium mb-1">How it works:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Each settlement gets its own JSON file</li>
                  <li>For single file: Downloads JSON directly</li>
                  <li>For multiple files: Downloads ZIP file with all JSON files</li>
                  <li>PDF files are not stored - only extracted data</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={uploading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {uploading ? 'Extracting...' : 'Extract to JSON'}
            </button>
            <button
              type="button"
              onClick={() => {
                setUploadFile(null)
                setUploadFiles([])
                setSelectedSettlementType('')
                setExtractedSettlements([])
              }}
              disabled={uploading}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:bg-gray-100 disabled:cursor-not-allowed"
            >
              Clear
            </button>
          </div>
        </form>
      </div>

      {/* Display Extracted Settlements */}
      {extractedSettlements.length > 0 && (
        <div className="space-y-6">
          {extractedSettlements.map((extractedData, dataIdx) => (
            <div key={dataIdx} className="bg-white shadow rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    {extractedData.source_file}
                  </h3>
                  <p className="text-sm text-gray-500 mt-1">
                    Extracted: {formatDate(extractedData.extraction_date)} | Type: {extractedData.settlement_type}
                  </p>
                </div>
                <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                  {extractedData.settlements.length} Settlement{extractedData.settlements.length !== 1 ? 's' : ''}
                </span>
              </div>

              <div className="space-y-4">
                {/* For multi-truck PDFs, show as single card. For single-truck, show individual cards */}
                {extractedData.settlements.length > 1 ? (
                  <div 
                    onClick={() => setSelectedSettlement({ data: extractedData, settlement: extractedData.settlements[0], index: 0 })}
                    className="border-2 border-blue-300 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer bg-blue-50"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-blue-800">Multi-Truck Settlement ({extractedData.settlements.length} trucks)</span>
                      <span className="text-xs text-blue-600 bg-blue-100 px-2 py-1 rounded">Click to view all trucks</span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {extractedData.settlements.map((settlement, idx) => (
                        <div key={idx} className="bg-white rounded p-2 border border-blue-200">
                          <div className="text-xs text-gray-500 mb-1">Truck {idx + 1}</div>
                          <div className="text-sm font-medium">{settlement.metadata.license_plate || 'N/A'}</div>
                          <div className="text-xs text-gray-600 mt-1">
                            Revenue: <span className="font-medium text-green-700">{formatCurrency(settlement.revenue.gross_revenue)}</span>
                          </div>
                          <div className="text-xs text-gray-600">
                            Profit: <span className={`font-medium ${settlement.revenue.net_profit >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                              {formatCurrency(settlement.revenue.net_profit)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <>
                    {extractedData.settlements.map((settlement, idx) => (
                      <div 
                        key={idx} 
                        onClick={() => setSelectedSettlement({ data: extractedData, settlement, index: idx })}
                        className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
                      >
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                      {/* Metadata */}
                      <div className="bg-gray-50 p-3 rounded">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Metadata</h4>
                        <div className="space-y-1 text-sm">
                          <div>
                            <span className="text-gray-500">Date: </span>
                            <span className="font-medium">{formatDate(settlement.metadata.settlement_date)}</span>
                          </div>
                          {settlement.metadata.week_start && (
                            <div>
                              <span className="text-gray-500">Week: </span>
                              <span className="font-medium">
                                {formatDate(settlement.metadata.week_start)} - {formatDate(settlement.metadata.week_end)}
                              </span>
                            </div>
                          )}
                          {settlement.metadata.license_plate && (
                            <div>
                              <span className="text-gray-500">Plate: </span>
                              <span className="font-medium">{settlement.metadata.license_plate}</span>
                            </div>
                          )}
                          {settlement.metadata.driver_name && (
                            <div>
                              <span className="text-gray-500">Driver: </span>
                              <span className="font-medium">{settlement.metadata.driver_name}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Revenue */}
                      <div className="bg-green-50 p-3 rounded">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Revenue</h4>
                        <div className="space-y-1 text-sm">
                          <div>
                            <span className="text-gray-500">Gross: </span>
                            <span className="font-medium text-green-700">{formatCurrency(settlement.revenue.gross_revenue)}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Net Profit: </span>
                            <span className={`font-medium ${settlement.revenue.net_profit >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                              {formatCurrency(settlement.revenue.net_profit)}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Expenses */}
                      <div className="bg-red-50 p-3 rounded">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Expenses</h4>
                        <div className="space-y-1 text-sm">
                          <div>
                            <span className="text-gray-500">Total: </span>
                            <span className="font-medium text-red-700">{formatCurrency(settlement.expenses.total_expenses)}</span>
                          </div>
                          <div className="mt-2 max-h-20 overflow-y-auto">
                            {Object.entries(settlement.expenses.categories)
                              .filter(([_, value]) => value > 0)
                              .map(([key, value]) => {
                                const isDeduction = key === 'custom' && value > 0
                                return (
                                  <div key={key} className={`text-xs ${isDeduction ? 'bg-yellow-100 px-1 py-0.5 rounded' : ''}`}>
                                    <span className={`${isDeduction ? 'font-semibold' : ''} text-gray-600 capitalize`}>
                                      {isDeduction ? 'Deductions' : key.replace('_', ' ')}: 
                                    </span>
                                    <span className={`font-medium ${isDeduction ? 'text-red-800' : ''}`}>
                                      {formatCurrency(value)}
                                    </span>
                                  </div>
                                )
                              })}
                          </div>
                        </div>
                      </div>

                      {/* Metrics */}
                      <div className="bg-blue-50 p-3 rounded">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Metrics</h4>
                        <div className="space-y-1 text-sm">
                          <div>
                            <span className="text-gray-500">Miles: </span>
                            <span className="font-medium">{settlement.metrics.miles_driven.toLocaleString()}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Blocks: </span>
                            <span className="font-medium">{settlement.metrics.blocks_delivered}</span>
                          </div>
                          {settlement.driver_pay.driver_pay > 0 && (
                            <>
                              <div className="mt-2 pt-2 border-t border-blue-200">
                                <span className="text-gray-500">Driver Pay: </span>
                                <span className="font-medium">{formatCurrency(settlement.driver_pay.driver_pay)}</span>
                              </div>
                              <div>
                                <span className="text-gray-500">Payroll Fee: </span>
                                <span className="font-medium">{formatCurrency(settlement.driver_pay.payroll_fee)}</span>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                    ))}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Settlement Detail Modal */}
      {selectedSettlement && (
        <Modal
          title={
            <div className="flex items-center justify-between w-full min-w-0">
              <span className="truncate mr-4">Settlement Details - {selectedSettlement.data.source_file}</span>
              <div className="flex items-center gap-2 flex-shrink-0">
                {(() => {
                  const navState = getNavigationState()
                  return (
                    <>
                      <button
                        onClick={() => navigateSettlement('prev')}
                        disabled={!navState.canGoPrev}
                        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title="Previous settlement"
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                      <span className="text-sm text-gray-500 px-2 whitespace-nowrap">
                        {navState.current} / {navState.total}
                      </span>
                      <button
                        onClick={() => navigateSettlement('next')}
                        disabled={!navState.canGoNext}
                        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title="Next settlement"
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </>
                  )
                })()}
              </div>
            </div>
          }
          isOpen={true}
          onClose={() => setSelectedSettlement(null)}
          showFooter={false}
          size="xlarge"
        >
          <div className="h-full overflow-y-auto">
            <div className="mb-3 p-2 bg-gray-50 rounded-lg">
              <div className="grid grid-cols-2 gap-1.5 text-xs">
                <div>
                  <span className="text-gray-500">Source File: </span>
                  <span className="font-medium">{selectedSettlement.data.source_file}</span>
                </div>
                <div>
                  <span className="text-gray-500">Extraction Date: </span>
                  <span className="font-medium">{formatDate(selectedSettlement.data.extraction_date)}</span>
                </div>
                <div>
                  <span className="text-gray-500">Settlement Type: </span>
                  <span className="font-medium">{selectedSettlement.data.settlement_type}</span>
                </div>
                <div>
                  <span className="text-gray-500">PDF #: </span>
                  <span className="font-medium">{getNavigationState().current} of {getNavigationState().total}</span>
                  {selectedSettlement.data.settlements.length > 1 && (
                    <span className="text-gray-500 ml-2">({selectedSettlement.data.settlements.length} trucks)</span>
                  )}
                </div>
              </div>
            </div>

            {/* PDF Viewer */}
            {selectedSettlement.data.pdf_filename && (
              <div className="mb-3 border border-gray-300 rounded-lg bg-gray-50 overflow-hidden">
                <div className="bg-gray-100 px-3 py-1.5 border-b border-gray-300 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-900">Original PDF Document</h3>
                  <button
                    onClick={() => window.open(`/uploads/${encodeURIComponent(selectedSettlement.data.pdf_filename!)}`, '_blank')}
                    className="text-xs text-blue-600 hover:text-blue-800 flex items-center space-x-1"
                  >
                    <span>📄</span>
                    <span>Open in New Tab</span>
                  </button>
                </div>
                <div className="w-full h-[630px] border-0">
                  <iframe
                    src={`/uploads/${encodeURIComponent(selectedSettlement.data.pdf_filename)}`}
                    className="w-full h-full border-0"
                    title="Settlement PDF"
                  />
                </div>
              </div>
            )}

            {/* Multi-Truck View: Show all trucks side-by-side */}
            {selectedSettlement.data.settlements.length > 1 ? (
              <div className="space-y-3">
                {/* Total Summary Header */}
                <div className="border-2 border-blue-300 bg-blue-50 rounded-lg p-3">
                  <h3 className="text-sm font-bold text-gray-900 mb-3 flex items-center">
                    <span className="mr-2">📊</span>
                    Total Summary (All Trucks Combined)
                  </h3>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-white rounded p-2.5 border border-blue-200">
                      <span className="text-xs text-gray-500 block mb-1">Total Gross Revenue:</span>
                      <p className="text-lg font-bold text-green-700">
                        {formatCurrency(
                          selectedSettlement.data.settlements.reduce(
                            (sum, s) => sum + s.revenue.gross_revenue,
                            0
                          )
                        )}
                      </p>
                    </div>
                    <div className="bg-white rounded p-2.5 border border-blue-200">
                      <span className="text-xs text-gray-500 block mb-1">Total Expenses:</span>
                      <p className="text-lg font-bold text-red-700">
                        {formatCurrency(
                          selectedSettlement.data.settlements.reduce(
                            (sum, s) => sum + s.expenses.total_expenses,
                            0
                          )
                        )}
                      </p>
                    </div>
                    <div className="bg-white rounded p-2.5 border border-blue-200">
                      <span className="text-xs text-gray-500 block mb-1">Total Net Profit:</span>
                      <p className={`text-lg font-bold ${
                        selectedSettlement.data.settlements.reduce(
                          (sum, s) => sum + s.revenue.net_profit,
                          0
                        ) >= 0 ? 'text-green-700' : 'text-red-700'
                      }`}>
                        {formatCurrency(
                          selectedSettlement.data.settlements.reduce(
                            (sum, s) => sum + s.revenue.net_profit,
                            0
                          )
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-gray-600">
                    <span className="font-medium">{selectedSettlement.data.settlements.length} truck(s)</span> in this settlement
                  </div>
                </div>

                {/* Side-by-side truck comparison */}
                <div className={`grid gap-4 ${
                  selectedSettlement.data.settlements.length === 2 
                    ? 'grid-cols-2' 
                    : selectedSettlement.data.settlements.length === 3
                    ? 'grid-cols-3'
                    : 'grid-cols-1'
                }`}>
                  {selectedSettlement.data.settlements.map((settlement, idx) => (
                    <div key={idx} className="border-2 border-gray-300 rounded-lg p-3 bg-white">
                      <div className="mb-3 pb-2 border-b border-gray-200">
                        <h4 className="text-sm font-bold text-gray-900">
                          Truck {idx + 1}: {settlement.metadata.license_plate || 'N/A'}
                        </h4>
                        {settlement.metadata.driver_name && (
                          <p className="text-xs text-gray-600 mt-1">Driver: {settlement.metadata.driver_name}</p>
                        )}
                      </div>

                      {/* Revenue Section */}
                      <div className="mb-3 border border-green-200 bg-green-50 rounded-lg p-2">
                        <h5 className="text-xs font-semibold text-gray-900 mb-2">Revenue</h5>
                        <div className="space-y-1.5">
                          <div>
                            <span className="text-xs text-gray-500">Gross Revenue:</span>
                            <p className="text-base font-bold text-green-700">{formatCurrency(settlement.revenue.gross_revenue)}</p>
                          </div>
                          <div>
                            <span className="text-xs text-gray-500">Net Profit:</span>
                            <p className={`text-base font-bold ${settlement.revenue.net_profit >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                              {formatCurrency(settlement.revenue.net_profit)}
                            </p>
                            {settlement.expenses.categories.custom > 0 && (
                              <p className="text-xs text-gray-500 mt-0.5 italic">
                                (after all expenses including deductions)
                              </p>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Expenses Section */}
                      <div className="mb-3 border border-red-200 bg-red-50 rounded-lg p-2">
                        <h5 className="text-xs font-semibold text-gray-900 mb-2">Expenses</h5>
                        <div className="space-y-1.5">
                          <div>
                            <span className="text-xs text-gray-500">Total Expenses:</span>
                            <p className="text-base font-bold text-red-700">{formatCurrency(settlement.expenses.total_expenses)}</p>
                          </div>
                          <div className="mt-2 max-h-32 overflow-y-auto">
                            {Object.entries(settlement.expenses.categories)
                              .filter(([_, value]) => value > 0)
                              .map(([key, value]) => {
                                const isDeduction = key === 'custom' && value > 0
                                return (
                                  <div key={key} className={`text-xs mb-1 ${isDeduction ? 'bg-yellow-100 p-1 rounded border border-yellow-300' : ''}`}>
                                    <span className={`${isDeduction ? 'font-semibold' : ''} text-gray-600 capitalize`}>
                                      {isDeduction ? 'Deductions' : key.replace('_', ' ')}: 
                                    </span>
                                    <span className={`font-medium ${isDeduction ? 'text-red-800' : ''}`}>
                                      {formatCurrency(value)}
                                    </span>
                                    {isDeduction && (
                                      <span className="text-xs text-gray-500 ml-1">(subtracted from net profit)</span>
                                    )}
                                  </div>
                                )
                              })}
                          </div>
                        </div>
                      </div>

                      {/* Metrics Section */}
                      <div className="border border-blue-200 bg-blue-50 rounded-lg p-2">
                        <h5 className="text-xs font-semibold text-gray-900 mb-2">Metrics</h5>
                        <div className="space-y-1 text-xs">
                          <div>
                            <span className="text-gray-500">Miles: </span>
                            <span className="font-medium">{settlement.metrics.miles_driven.toLocaleString()}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Blocks: </span>
                            <span className="font-medium">{settlement.metrics.blocks_delivered}</span>
                          </div>
                          {settlement.driver_pay.driver_pay > 0 && (
                            <>
                              <div className="mt-1 pt-1 border-t border-blue-200">
                                <span className="text-gray-500">Driver Pay: </span>
                                <span className="font-medium">{formatCurrency(settlement.driver_pay.driver_pay)}</span>
                              </div>
                              <div>
                                <span className="text-gray-500">Payroll Fee: </span>
                                <span className="font-medium">{formatCurrency(settlement.driver_pay.payroll_fee)}</span>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Common Metadata */}
                <div className="border border-gray-200 rounded-lg p-2.5 bg-gray-50">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">Common Metadata</h3>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-gray-500">Settlement Date:</span>
                      <p className="font-medium">{formatDate(selectedSettlement.settlement.metadata.settlement_date)}</p>
                    </div>
                    {selectedSettlement.settlement.metadata.week_start && (
                      <>
                        <div>
                          <span className="text-gray-500">Week Start:</span>
                          <p className="font-medium">{formatDate(selectedSettlement.settlement.metadata.week_start)}</p>
                        </div>
                        <div>
                          <span className="text-gray-500">Week End:</span>
                          <p className="font-medium">{formatDate(selectedSettlement.settlement.metadata.week_end)}</p>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              /* Single Truck View: Show single settlement details */
              <div className="space-y-2">
                {/* Metadata Section */}
                <div className="border border-gray-200 rounded-lg p-2.5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">Metadata</h3>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-xs text-gray-500">Settlement Date:</span>
                      <p className="text-sm font-medium">{formatDate(selectedSettlement.settlement.metadata.settlement_date)}</p>
                    </div>
                    {selectedSettlement.settlement.metadata.week_start && (
                      <>
                        <div>
                          <span className="text-xs text-gray-500">Week Start:</span>
                          <p className="text-sm font-medium">{formatDate(selectedSettlement.settlement.metadata.week_start)}</p>
                        </div>
                        <div>
                          <span className="text-xs text-gray-500">Week End:</span>
                          <p className="text-sm font-medium">{formatDate(selectedSettlement.settlement.metadata.week_end)}</p>
                        </div>
                      </>
                    )}
                    {selectedSettlement.settlement.metadata.license_plate && (
                      <div>
                        <span className="text-xs text-gray-500">License Plate:</span>
                        <p className="text-sm font-medium">{selectedSettlement.settlement.metadata.license_plate}</p>
                      </div>
                    )}
                    {selectedSettlement.settlement.metadata.driver_id && (
                      <div>
                        <span className="text-xs text-gray-500">Driver ID:</span>
                        <p className="text-sm font-medium">{selectedSettlement.settlement.metadata.driver_id}</p>
                      </div>
                    )}
                    {selectedSettlement.settlement.metadata.driver_name && (
                      <div>
                        <span className="text-xs text-gray-500">Driver Name:</span>
                        <p className="text-sm font-medium">{selectedSettlement.settlement.metadata.driver_name}</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Revenue Section */}
                <div className="border border-green-200 bg-green-50 rounded-lg p-2.5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">Revenue</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-xs text-gray-500">Gross Revenue:</span>
                      <p className="text-lg font-bold text-green-700">{formatCurrency(selectedSettlement.settlement.revenue.gross_revenue)}</p>
                    </div>
                    <div>
                      <span className="text-xs text-gray-500">Net Profit:</span>
                      <p className={`text-lg font-bold ${selectedSettlement.settlement.revenue.net_profit >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                        {formatCurrency(selectedSettlement.settlement.revenue.net_profit)}
                      </p>
                      {selectedSettlement.settlement.expenses.categories.custom > 0 && (
                        <p className="text-xs text-gray-500 mt-0.5 italic">
                          (after all expenses including deductions)
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Expenses Section */}
                <div className="border border-red-200 bg-red-50 rounded-lg p-2.5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">Expenses</h3>
                  <div className="mb-2">
                    <span className="text-xs text-gray-500">Total Expenses:</span>
                    <p className="text-lg font-bold text-red-700">{formatCurrency(selectedSettlement.settlement.expenses.total_expenses)}</p>
                    <p className="text-xs text-gray-600 mt-1 italic">
                      Note: Deductions are included in total expenses and subtracted from net profit
                    </p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {Object.entries(selectedSettlement.settlement.expenses.categories)
                      .filter(([_, value]) => value > 0)
                      .sort(([_, a], [__, b]) => (b as number) - (a as number))
                      .map(([key, value]) => {
                        const isDeduction = key === 'custom' && value > 0
                        return (
                          <div key={key} className={`bg-white p-1.5 rounded border ${isDeduction ? 'border-yellow-400 bg-yellow-50' : 'border-red-100'}`}>
                            <span className={`text-xs ${isDeduction ? 'font-semibold' : ''} text-gray-500 capitalize block`}>
                              {isDeduction ? 'Deductions' : key.replace(/_/g, ' ')}
                            </span>
                            <span className={`text-xs font-semibold ${isDeduction ? 'text-red-800' : 'text-red-700'}`}>
                              {formatCurrency(value)}
                            </span>
                          </div>
                        )
                      })}
                  </div>
                </div>

              {/* Metrics Section */}
              <div className="border border-blue-200 bg-blue-50 rounded-lg p-2.5">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">Metrics</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <span className="text-xs text-gray-500">Miles Driven:</span>
                    <p className="text-base font-semibold text-blue-700">{selectedSettlement.settlement.metrics.miles_driven.toLocaleString()}</p>
                  </div>
                  <div>
                    <span className="text-xs text-gray-500">Blocks Delivered:</span>
                    <p className="text-base font-semibold text-blue-700">{selectedSettlement.settlement.metrics.blocks_delivered}</p>
                  </div>
                </div>
              </div>

              {/* Driver Pay Section */}
              {(selectedSettlement.settlement.driver_pay.driver_pay > 0 || selectedSettlement.settlement.driver_pay.payroll_fee > 0) && (
                <div className="border border-purple-200 bg-purple-50 rounded-lg p-2.5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">Driver Pay</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-xs text-gray-500">Driver Pay:</span>
                      <p className="text-base font-semibold text-purple-700">{formatCurrency(selectedSettlement.settlement.driver_pay.driver_pay)}</p>
                    </div>
                    <div>
                      <span className="text-xs text-gray-500">Payroll Fee:</span>
                      <p className="text-base font-semibold text-purple-700">{formatCurrency(selectedSettlement.settlement.driver_pay.payroll_fee)}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Raw JSON View - Collapsible */}
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <button
                  onClick={() => setShowJsonData(!showJsonData)}
                  className="w-full px-3 py-2 bg-gray-50 hover:bg-gray-100 flex items-center justify-between transition-colors"
                >
                  <h3 className="text-sm font-semibold text-gray-900">Raw JSON Data</h3>
                  <svg
                    className={`w-5 h-5 text-gray-600 transition-transform ${showJsonData ? 'rotate-180' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showJsonData && (
                  <div className="p-4">
                    <div className="bg-gray-900 text-gray-100 p-4 rounded overflow-x-auto mb-3">
                      <pre className="text-xs">
                        {JSON.stringify({
                          source_file: selectedSettlement.data.source_file,
                          extraction_date: selectedSettlement.data.extraction_date,
                          settlement_type: selectedSettlement.data.settlement_type,
                          settlement: selectedSettlement.settlement
                        }, null, 2)}
                      </pre>
                    </div>
                    <button
                      onClick={() => {
                        const jsonStr = JSON.stringify({
                          source_file: selectedSettlement.data.source_file,
                          extraction_date: selectedSettlement.data.extraction_date,
                          settlement_type: selectedSettlement.data.settlement_type,
                          settlement: selectedSettlement.settlement
                        }, null, 2)
                        const blob = new Blob([jsonStr], { type: 'application/json' })
                        const url = window.URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        const license_plate = selectedSettlement.settlement.metadata.license_plate || ''
                        const settlement_date = selectedSettlement.settlement.metadata.settlement_date?.replace(/-/g, '') || ''
                        a.download = `${selectedSettlement.data.source_file.replace('.pdf', '')}_${license_plate}_${settlement_date}.json`
                        document.body.appendChild(a)
                        a.click()
                        window.URL.revokeObjectURL(url)
                        document.body.removeChild(a)
                      }}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                    >
                      Download JSON
                    </button>
                  </div>
                )}
              </div>
              </div>
            )}
          </div>
        </Modal>
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

