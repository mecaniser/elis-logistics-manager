export type FundingProposal = {
  charge: {id:string; description:string; date:string; pending:boolean}
  accountName: string
  last4: string
  amount?: number
  routes: {route_id:string; source_name:string; source_last4:string; profileName:string}[]
}
export type FundingProposalState = {tenantId:number; items:FundingProposal[]}

const money = (amount?: number) => amount == null ? 'Unavailable' : (amount / 100).toLocaleString('en-US', {style:'currency', currency:'USD'})
export default function FundingProposals({items, busy, onReview, openSettings}: {
  items:FundingProposal[]; busy:boolean; onReview:(chargeId:string, routeId:string)=>void; openSettings:()=>void
}) {
  if (!items.length) return null
  return <section aria-label="Charges to fund" className="border-b border-slate-200">
    <h3 className="px-5 pt-5 text-sm font-semibold text-slate-900">Charges to fund</h3>
    <div className="divide-y divide-slate-100">{items.map(item => <article key={item.charge.id} className="grid gap-3 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="min-w-0">
        <p className="text-lg font-semibold tabular-nums text-slate-950">{money(item.amount)} <span className="text-sm font-medium">· {item.charge.description}</span></p>
        <p className="mt-1 text-sm text-slate-600">{item.accountName} · ••{item.last4}</p>
        <p className="mt-1 text-xs text-slate-500">{item.charge.date} · {item.charge.pending ? 'Pending charge' : 'Posted charge'}</p>
        {!item.routes.length && <p className="mt-2 text-sm text-amber-800">No enabled source can cover this full charge.</p>}
      </div>
      <div className="space-y-2">{item.routes.map(route => <div key={route.route_id}>
        <button type="button" disabled={busy} onClick={()=>onReview(item.charge.id, route.route_id)} className="min-h-11 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-45">Review funding from ••{route.source_last4}</button>
        <p className="mt-1 max-w-xs text-xs text-slate-500">{route.profileName}</p>
      </div>)}{!item.routes.length && <button type="button" onClick={openSettings} className="min-h-11 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700">Review funding settings</button>}</div>
    </article>)}</div>
  </section>
}
