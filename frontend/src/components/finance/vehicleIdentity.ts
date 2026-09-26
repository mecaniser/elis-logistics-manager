import type { HistoryRow } from './historyTypes'

type Vehicle = Pick<HistoryRow, 'asset_id' | 'name' | 'vin' | 'vehicle_type'>

// Keep the database identity as the key. A VIN label never merges vehicle records.
export function vehicleIdentities(rows: Vehicle[]) {
  const vehicles = [...new Map(rows.map(row => [row.asset_id, row])).values()]
  const normalized = (row: Vehicle) => row.vin?.trim().toUpperCase() || ''
  return new Map(vehicles.sort((a, b) => a.asset_id - b.asset_id).map(row => {
    const vin = normalized(row)
    const kind = row.vehicle_type === 'trailer' ? 'Trailer' : row.vehicle_type === 'suv' ? 'Vehicle' : 'Truck'
    const suffix = vin.slice(-6)
    const ambiguous = vin && vehicles.some(other => other.asset_id !== row.asset_id && normalized(other).slice(-6) === suffix)
    const duplicate = vin && vehicles.some(other => other.asset_id !== row.asset_id && normalized(other) === vin)
    const label = vin ? `${kind}${duplicate ? ` #${row.asset_id}` : ''} · VIN ${ambiguous ? vin : `…${suffix}`}` : `${kind} #${row.asset_id} · VIN not recorded`
    return [row.asset_id, {label, vin, currentName: row.name}] as const
  }))
}
