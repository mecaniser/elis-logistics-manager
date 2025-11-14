import { useEffect, useState } from 'react'
import { repairsApi, trucksApi, Repair, Truck } from '../services/api'
import Modal from '../components/Modal'
import ConfirmModal from '../components/ConfirmModal'

export default function Repairs() {
  const [repairs, setRepairs] = useState<Repair[]>([])
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showUploadForm, setShowUploadForm] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadImages, setUploadImages] = useState<File[]>([])
  const [selectedTruck, setSelectedTruck] = useState<number | null>(null)
  const [uploading, setUploading] = useState(false)
  const [repairToDelete, setRepairToDelete] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalMessage, setModalMessage] = useState('')
  const [modalType, setModalType] = useState<'success' | 'error' | 'warning' | 'info'>('info')

  useEffect(() => {
    loadTrucks()
    loadRepairs()
  }, [])

  const loadTrucks = async () => {
    try {
      const response = await trucksApi.getAll()
      setTrucks(response.data)
    } catch (err) {
      console.error(err)
    }
  }

  const loadRepairs = async () => {
    try {
      setLoading(true)
      const response = await repairsApi.getAll()
      setRepairs(response.data)
    } catch (err: any) {
      setError(err.message || 'Failed to load repairs')
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

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadFile || !selectedTruck) {
      showModal('Error', 'Please select a truck and PDF file', 'error')
      return
    }

    try {
      setUploading(true)
      const response = await repairsApi.upload(uploadFile, uploadImages, selectedTruck)
      if (response.data.warning) {
        showModal('Upload Successful', `Repair uploaded successfully. ${response.data.warning}`, 'warning')
      } else {
        showModal('Success', 'Repair uploaded successfully!', 'success')
      }
      setUploadFile(null)
      setUploadImages([])
      setSelectedTruck(null)
      setShowUploadForm(false)
      loadRepairs()
    } catch (err: any) {
      showModal('Upload Failed', err.response?.data?.detail || err.message || 'Failed to upload repair', 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async () => {
    if (!repairToDelete) return
    try {
      await repairsApi.delete(repairToDelete)
      showModal('Success', 'Repair deleted successfully!', 'success')
      setRepairToDelete(null)
      loadRepairs()
    } catch (err: any) {
      showModal('Error', err.response?.data?.detail || err.message || 'Failed to delete repair', 'error')
      setRepairToDelete(null)
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

  if (loading) return <div className="text-center py-8">Loading repairs...</div>
  if (error) return <div className="text-center py-8 text-red-600">{error}</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Repairs</h1>
        <button
          onClick={() => setShowUploadForm(!showUploadForm)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          {showUploadForm ? 'Cancel' : 'Upload Repair'}
        </button>
      </div>

      {showUploadForm && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Upload Repair Invoice</h2>
          <form onSubmit={handleUpload}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Truck *</label>
              <select
                value={selectedTruck || ''}
                onChange={(e) => setSelectedTruck(e.target.value ? Number(e.target.value) : null)}
                required
                disabled={uploading}
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
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">PDF Invoice *</label>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                required
                disabled={uploading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Images (optional)</label>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => setUploadImages(Array.from(e.target.files || []))}
                disabled={uploading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
            <button
              type="submit"
              disabled={uploading || !uploadFile || !selectedTruck}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </form>
        </div>
      )}

      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {repairs.length === 0 ? (
            <li className="px-6 py-4 text-gray-500 text-center">No repairs found.</li>
          ) : (
            repairs.map((repair) => (
              <li key={repair.id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">{repair.description}</h3>
                    <p className="text-sm text-gray-500">
                      {getTruckName(repair.truck_id)} - {new Date(repair.repair_date).toLocaleDateString()}
                    </p>
                    <p className="text-sm font-semibold text-red-600">${repair.cost.toLocaleString()}</p>
                    {repair.image_paths && repair.image_paths.length > 0 && (
                      <div className="mt-2 flex gap-2 flex-wrap">
                        {repair.image_paths.map((img, idx) => (
                          <img
                            key={idx}
                            src={getImageUrl(img)}
                            alt={`Repair ${idx + 1}`}
                            className="w-20 h-20 object-cover rounded border"
                          />
                        ))}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => setRepairToDelete(repair.id)}
                    className="text-red-600 hover:text-red-800"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))
          )}
        </ul>
      </div>

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={modalTitle} type={modalType}>
        {modalMessage}
      </Modal>

      <ConfirmModal
        isOpen={repairToDelete !== null}
        onClose={() => setRepairToDelete(null)}
        onConfirm={handleDelete}
        title="Delete Repair"
        message="Are you sure you want to delete this repair? This action cannot be undone."
        confirmText="Delete"
        type="danger"
      />
    </div>
  )
}
