import type { Evidence, Workspace } from '../../services/finance'
import type { HistoryRow } from './historyTypes'
import type { RepairReviewRow } from '../repairs/repairReview'

export function documentRows(evidence:Evidence[], repairs:RepairReviewRow[], settlements:HistoryRow[], legacyRepairs:Workspace['legacy_repairs']) {
  return evidence.map(doc=>{
    const confirmation=doc.source_key.startsWith('repair-confirmation:')
    const related=repairs.filter(r=>r.evidence.some(e=>e.id===doc.id)||r.confirmation?.id===doc.id||(confirmation&&r.legacy_id===Number(doc.source_key.split(':')[1])))
    const repair=related[0]
    const settlement=settlements.find(s=>s.evidence_id===doc.id||(doc.source_key.startsWith('legacy-settlement:')&&s.id===Number(doc.source_key.split(':')[1])))
    const category=confirmation?'confirmation':doc.source_key.startsWith('recovered-repair:')||repair?'repair':settlement||doc.source_key.startsWith('legacy-settlement:')?'settlement':'other'
    const categoryLabel={confirmation:'Payment confirmation',repair:'Repair',settlement:'Settlement',other:'Document'}[category]
    const title=(confirmation&&typeof doc.extracted.payee==='string'?doc.extracted.payee:null)||repair?.payee.name||settlement?.provider||({confirmation:'Saved repair payment details',repair:'Repair invoice or receipt',settlement:'Carrier settlement',other:'Supporting document'}[category])
    const date=confirmation&&typeof doc.extracted.paid_date==='string'?doc.extracted.paid_date:repair?.date||settlement?.date
    const amount=confirmation?doc.extracted.paid_amount:repair?.recorded_cost??settlement?.remainder
    const assetId=legacyRepairs.find(r=>r.id===repair?.legacy_id)?.asset_id
    const repairVin=settlements.find(r=>r.asset_id===assetId&&r.vin)?.vin
    const equipment=repairVin?`VIN …${repairVin.slice(-6)}`:settlement?.vin?`VIN …${settlement.vin.slice(-6)}`:repair?.asset_name||settlement?.name
    const action=repair?.issues.some(i=>['invoice_amount_difference','conflicting_invoice_totals'].includes(i))?'Invoice amount differs from saved repair. Review it in Repairs.':settlement?.status==='needs_review'?'Settlement amounts need review.':null
    return {doc,category,categoryLabel,title,date,amount,equipment,repair,settlement,action,related}
  })
}
