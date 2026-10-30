import type { DieselBridgeFinancialState } from '../../services/api'
import { actualSourcePaidDate, sourceAppliedFees, sourceRailLabel, sourceSettlementNeedsReview } from './dieselBridgeSettlement'
import { repairMoney } from './repairReview'

export default function DieselBridgeSettlementDetails({ state }: { state: DieselBridgeFinancialState }) {
  const settlement = state.source_settlement
  const actualFees = settlement ? sourceAppliedFees(settlement) : null
  const reasons = [...new Set([...(state.source_payment_review_reasons || []), ...(settlement?.review_reasons || [])])]
  return <section className="mt-3 rounded border border-gray-200 p-3" aria-label="DBN settlement and payment records">
    <h4 className="font-semibold text-gray-900">DBN settlement and payment records</h4>
    <dl className="mt-2 space-y-1">
      <div className="flex flex-wrap justify-between gap-2"><dt>Quoted invoice total</dt><dd>{repairMoney(state.source_invoice_total ?? state.invoice_total)}</dd></div>
      <div className="flex flex-wrap justify-between gap-2"><dt>Booked repair cost in EDG</dt><dd className="font-medium">{repairMoney(state.booked_cost ?? state.invoice_total)}</dd></div>
      {settlement && <>
        <div className="flex flex-wrap justify-between gap-2"><dt>DBN settlement principal</dt><dd>{repairMoney(settlement.principal_total)}</dd></div>
        <div className="flex flex-wrap justify-between gap-2"><dt>DBN confirmed principal</dt><dd>{repairMoney(settlement.confirmed_principal)}</dd></div>
        <div className="flex flex-wrap justify-between gap-2"><dt>DBN pending principal</dt><dd>{repairMoney(settlement.pending_principal)}</dd></div>
        <div className="flex flex-wrap justify-between gap-2"><dt>DBN actual confirmed card fees</dt><dd>{actualFees ? repairMoney(actualFees.fee) : 'Needs review'}</dd></div>
        <div className="flex flex-wrap justify-between gap-2"><dt>DBN actual confirmed fee tax</dt><dd>{actualFees ? repairMoney(actualFees.feeTax) : 'Needs review'}</dd></div>
        <div className="flex flex-wrap justify-between gap-2"><dt>Quoted card fee limit</dt><dd>{repairMoney(settlement.max_card_fee)}</dd></div>
        <div className="flex flex-wrap justify-between gap-2"><dt>Quoted card fee tax limit</dt><dd>{repairMoney(settlement.max_card_fee_tax)}</dd></div>
        {state.source_obligation_amount != null && <div className="flex flex-wrap justify-between gap-2"><dt>DBN obligation, including actual fees</dt><dd>{repairMoney(state.source_obligation_amount)}</dd></div>}
        {state.source_confirmed_amount != null && <div className="flex flex-wrap justify-between gap-2"><dt>DBN confirmed applied payments</dt><dd>{repairMoney(state.source_confirmed_amount)}</dd></div>}
        {state.source_recorded_balance != null && <div className="flex flex-wrap justify-between gap-2"><dt>DBN recorded balance</dt><dd>{repairMoney(state.source_recorded_balance)}</dd></div>}
        <div className="flex flex-wrap justify-between gap-2"><dt>DBN unapplied credit</dt><dd>{repairMoney(settlement.unapplied_credit)}</dd></div>
        <div className="flex flex-wrap justify-between gap-2"><dt>DBN refund pending</dt><dd>{repairMoney(settlement.refund_pending)}</dd></div>
      </>}
    </dl>
    <p className="mt-2 text-xs text-gray-600">Quoted fees are not actual charges. The booked cost follows the reviewed settlement and actual fees; taxes and fees are not removed from every invoice.</p>
    <p className="mt-1 text-xs text-gray-600">DBN payment records are separate from verified payments recorded in EDG. A source confirmation alone does not record a payment or withdraw from reserve, and its payment rail does not identify personal or business funding.</p>
    {!settlement && <p className="mt-2 text-gray-600">Detailed DBN settlement evidence is unavailable. Existing EDG costs and verified payments are preserved.</p>}
    {sourceSettlementNeedsReview(state) && <div className="mt-2 rounded bg-amber-50 p-2 text-amber-900"><p className="font-medium">DBN settlement or payment changes need review. Existing EDG costs, payments and reserve entries are preserved.</p>{reasons.map(reason => <p key={reason} className="mt-1 break-words">{reason.replace(/_/g, ' ')}</p>)}</div>}
    {settlement && <p className="mt-2 text-xs text-gray-600">DBN settlement status: {settlement.source_state.replace(/_/g, ' ')} · {settlement.status === 'available' ? 'Evidence available' : 'Review required'}</p>}
    {!!settlement?.payments.length && <details className="mt-2"><summary className="min-h-11 cursor-pointer py-2 text-blue-700">DBN payment attempts ({settlement.payments.length})</summary>
      <ul className="space-y-2">{settlement.payments.map(attempt => {
        const paidDate = actualSourcePaidDate(attempt)
        return <li key={attempt.attempt_id} className="rounded border border-gray-200 bg-gray-50 p-3">
          <p className="font-medium">{sourceRailLabel[attempt.rail]} · {attempt.state}</p>
          <p className="mt-1 break-all text-xs text-gray-600">DBN attempt {attempt.attempt_id}</p>
          <dl className="mt-2 space-y-1">
            <div className="flex flex-wrap justify-between gap-2"><dt>Principal requested</dt><dd>{repairMoney(attempt.principal_amount)}</dd></div>
            <div className="flex flex-wrap justify-between gap-2"><dt>Received principal</dt><dd>{attempt.received_amount === null ? 'Not established' : repairMoney(attempt.received_amount)}</dd></div>
            <div className="flex flex-wrap justify-between gap-2"><dt>Actual gross received</dt><dd>{attempt.gross_received_amount == null ? 'Not established' : repairMoney(attempt.gross_received_amount)}</dd></div>
            <div className="flex flex-wrap justify-between gap-2"><dt>Applied principal</dt><dd>{repairMoney(attempt.applied_principal_amount)}</dd></div>
            <div className="flex flex-wrap justify-between gap-2"><dt>Actual applied card fee</dt><dd>{repairMoney(attempt.applied_card_fee_amount)}</dd></div>
            <div className="flex flex-wrap justify-between gap-2"><dt>Actual applied card fee tax</dt><dd>{repairMoney(attempt.applied_card_fee_tax_amount)}</dd></div>
            <div className="flex flex-wrap justify-between gap-2"><dt>Unapplied amount</dt><dd>{repairMoney(attempt.unapplied_amount)}</dd></div>
          </dl>
          <p className="mt-2">Actual payment date: {paidDate || 'Unknown; verify from payment evidence.'}</p>
          {attempt.confirmed_at && <p className="mt-1 text-xs text-gray-600">Source confirmation recorded at {attempt.confirmed_at}. This is not the actual payment date.</p>}
        </li>
      })}</ul>
    </details>}
  </section>
}
