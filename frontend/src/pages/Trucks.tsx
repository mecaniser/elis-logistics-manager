import { useEffect, useState } from 'react'
import { trucksApi, Truck } from '../services/api'
import Modal from '../components/Modal'
import ConfirmModal from '../components/ConfirmModal'

export default function Trucks() {
  const [trucks, setTrucks] = useState<Truck[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingTruck, setEditingTruck] = useState<Truck | null>(null)
  const [formData, setFormData] = useState({ name: '', vin: '', license_plate: '' })
  const [truckToDelete, setTruckToDelete] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalMessage, setModalMessage] = useState('')
  const [modalType, setModalType] = useState<'success' | 'error' | 'warning' | 'info'>('info')

  useEffect(() => {
    loadTrucks()
  }, [])

  const loadTrucks = async () => {
    try {
      setLoading(true)
      const response = await trucksApi.getAll()
      setTrucks(response.data)
    } catch (err: any) {
      setError(err.message || 'Failed to load trucks')
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingTruck) {
        await trucksApi.update(editingTruck.id, { name: formData.name })
        showModal('Success', 'Truck updated successfully!', 'success')
      } else {
        await trucksApi.create({
          name: formData.name,
          vin: formData.vin || undefined,
          license_plate: formData.license_plate || undefined,
        })
        showModal('Success', 'Truck created successfully!', 'success')
      }
      setShowForm(false)
      setEditingTruck(null)
      setFormData({ name: '', vin: '', license_plate: '' })
      loadTrucks()
    } catch (err: any) {
      showModal('Error', err.response?.data?.detail || err.message || 'Failed to save truck', 'error')
    }
  }

  const handleDelete = async () => {
    if (!truckToDelete) return
    try {
      await trucksApi.delete(truckToDelete)
      showModal('Success', 'Truck deleted successfully!', 'success')
      setTruckToDelete(null)
      loadTrucks()
    } catch (err: any) {
      showModal('Error', err.response?.data?.detail || err.message || 'Failed to delete truck', 'error')
      setTruckToDelete(null)
    }
  }

  if (loading) return <div className="text-center py-8">Loading trucks...</div>
  if (error) return <div className="text-center py-8 text-red-600">{error}</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Trucks</h1>
        <button
          onClick={() => {
            setEditingTruck(null)
            setFormData({ name: '', vin: '', license_plate: '' })
            setShowForm(true)
          }}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Add Truck
        </button>
      </div>

      {showForm && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">{editingTruck ? 'Edit Truck' : 'Add Truck'}</h2>
          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {!editingTruck && (
              <>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">VIN</label>
                  <input
                    type="text"
                    value={formData.vin}
                    onChange={(e) => setFormData({ ...formData, vin: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">License Plate</label>
                  <input
                    type="text"
                    value={formData.license_plate}
                    onChange={(e) => setFormData({ ...formData, license_plate: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </>
            )}
            <div className="flex gap-3">
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                {editingTruck ? 'Update' : 'Create'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false)
                  setEditingTruck(null)
                  setFormData({ name: '', vin: '', license_plate: '' })
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
          {trucks.length === 0 ? (
            <li className="px-6 py-4 text-gray-500 text-center">No trucks found.</li>
          ) : (
            trucks.map((truck) => (
              <li key={truck.id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">{truck.name}</h3>
                    {truck.vin && <p className="text-sm text-gray-500">VIN: {truck.vin}</p>}
                    {truck.license_plate && (
                      <p className="text-sm text-gray-500">License Plate: {truck.license_plate}</p>
                    )}
                    {truck.license_plate_history && truck.license_plate_history.length > 0 && (
                      <p className="text-xs text-gray-400">
                        History: {truck.license_plate_history.join(', ')}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setEditingTruck(truck)
                        setFormData({ name: truck.name, vin: truck.vin || '', license_plate: truck.license_plate || '' })
                        setShowForm(true)
                      }}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setTruckToDelete(truck.id)}
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

      <ConfirmModal
        isOpen={truckToDelete !== null}
        onClose={() => setTruckToDelete(null)}
        onConfirm={handleDelete}
        title="Delete Truck"
        message="Are you sure you want to delete this truck? This action cannot be undone."
        confirmText="Delete"
        type="danger"
      />
    </div>
  )
}
