import type { DieselBridgeRepairHistoryRow } from '../../services/api'

export function historyDate(value: string): string {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  return parts ? `${parts[2]}/${parts[3]}/${parts[1]}` : 'Date unavailable'
}

export function historyTitle(row: DieselBridgeRepairHistoryRow): string {
  return row.service?.order_number || `Repair order ${row.repair_order_id}`
}

export function historyReviewMessage(reason: string): string {
  const messages: Record<string, string> = {
    missing_vin: 'The source repair order needs a VIN before a truck can be assigned.',
    unmatched_vin: 'No EDG truck currently matches the source VIN.',
    duplicate_vin: 'More than one EDG truck has this VIN. Review the truck directory.',
    vehicle_type_mismatch: 'The source VIN does not identify an EDG truck.',
    truck_identity_changed: 'The source vehicle identity changed. Review the existing truck assignment.',
  }
  return messages[reason] || 'Review the source repair order and truck assignment.'
}

export function sortHistory(rows: DieselBridgeRepairHistoryRow[]): DieselBridgeRepairHistoryRow[] {
  return [...rows].sort((a, b) => (b.service?.service_date || '').localeCompare(a.service?.service_date || '') || historyTitle(a).localeCompare(historyTitle(b)))
}
