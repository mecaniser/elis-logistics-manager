import type { DieselBridgeReconciliationNote, DieselBridgeReconciliationNoteInput } from '../../services/api'

export type ReconciliationDraft = {
  note: string
  references: string
  serviceDate: string
  invoiceDate: string
  discrepancy: string
  supersedes: string
}
export const emptyReconciliationDraft = (): ReconciliationDraft => ({ note: '', references: '', serviceDate: '', invoiceDate: '', discrepancy: '', supersedes: '' })

function validDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value
}
export function reconciliationInput(draft: ReconciliationDraft): DieselBridgeReconciliationNoteInput | null {
  const note = draft.note.trim()
  const source_references = draft.references.split('\n').map(value => value.trim()).filter(Boolean)
  const amount_discrepancy = draft.discrepancy.trim()
  if (note.length < 3 || note.length > 4000 || source_references.length > 10 || source_references.some(value => value.length > 300) || amount_discrepancy.length > 1000) return null
  if ((draft.serviceDate && !validDate(draft.serviceDate)) || (draft.invoiceDate && !validDate(draft.invoiceDate))) return null
  if (draft.supersedes && (!/^[1-9]\d*$/.test(draft.supersedes) || !Number.isSafeInteger(Number(draft.supersedes)))) return null
  return { note, source_references,
    ...(draft.serviceDate ? { confirmed_service_date: draft.serviceDate } : {}),
    ...(draft.invoiceDate ? { original_invoice_date: draft.invoiceDate } : {}),
    ...(amount_discrepancy ? { amount_discrepancy } : {}),
    ...(draft.supersedes ? { supersedes_note_id: Number(draft.supersedes) } : {}) }
}

// Never borrow notes from another source RO, even when a stale request completes.
export function mergeReconciliationNotes(repairOrderId: string, ...groups: DieselBridgeReconciliationNote[][]): DieselBridgeReconciliationNote[] {
  const byId = new Map<number, DieselBridgeReconciliationNote>()
  for (const notes of groups) for (const note of notes) {
    if (note.repair_order_id === repairOrderId && Number.isSafeInteger(note.id) && note.id > 0 && !byId.has(note.id)) byId.set(note.id, note)
  }
  return [...byId.values()].sort((left, right) => left.id - right.id)
}

export function nextReconciliationCursor(previous: number, next: number | null, seen: Set<number>) {
  if (next === null) return null
  if (!Number.isSafeInteger(next) || next <= previous || seen.has(next)) throw new Error('Reconciliation history could not be completed. Please retry.')
  return next
}
