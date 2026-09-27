import type { EarningsPlan } from '../../services/finance'
const cents=(value:string)=>{const result=Number(value)*100;return Number.isFinite(result)?Math.round(result):NaN}
export function ownerEarningsModel(plan:EarningsPlan){
 const totals=new Map<string,number>()
 for(const pair of plan.pairs)for(const row of pair.bridge)totals.set(row.label,(totals.get(row.label)??0)+cents(row.amount))
 const take=(key:string)=>{const value=totals.get(key)??0;totals.delete(key);return value}
 const start=take('Statement remainder')+take('Saved settlements not yet posted (unverified)')
 const repair=plan.pairs.reduce((sum,p)=>sum+cents(p.repair_target),0)
 const capital=plan.pairs.reduce((sum,p)=>sum+cents(p.capital_target),0)
 const funded=take('New repair and capital funding')-plan.pairs.reduce((sum,p)=>sum+cents(p.additional_protection),0)
 const adjustments=funded+repair+capital
 const entries=[
  {label:'Repairs outside settlements',amount:take('Historical repairs not yet posted to Accounting'),tone:'repair'},
  {label:'Other recorded costs & income · includes posted repairs and interest',amount:take('Outside costs and income, including incurred interest'),tone:'cost'},
  {label:'Shared company costs & income',amount:take('Shared company result allocated by freight'),tone:'cost'},
  {label:'Repair costs covered by existing reserves',amount:take('Repair costs covered by protected funds'),tone:'repair'},
  {label:'Repair reserve',amount:-repair,tone:'repair',always:true},
  {label:'Equipment capital recovery',amount:-capital,tone:'capital',always:true},
  {label:'Reserve funding adjustments',amount:adjustments,tone:'capital'},
  {label:'Recorded equipment principal payments',amount:take('Business-paid equipment obligations'),tone:'loan',always:true},
  ...[...totals].map(([label,amount])=>({label,amount,tone:'cost'})),
  {label:'Unassigned costs & income',amount:cents(plan.unassigned_result),tone:'cost'},
 ].filter(row=>row.amount!==0||('always' in row&&row.always))
 let running=start
 const rows=entries.map(row=>{const before=running;running+=row.amount;return {...row,before,after:running}})
 const expected=cents(plan.planning_subtotal)+cents(plan.unassigned_result)
 const allocationKnown=plan.pairs.length>0&&plan.pairs.every(p=>p.allocation_split)
 const allocation=allocationKnown?plan.pairs.reduce((sum,p)=>sum+cents(p.allocation_split!.trailer_allocation),0):null
 const trailerRecovery=allocationKnown?plan.pairs.reduce((sum,p)=>sum+cents(p.allocation_split!.trailer_capital_target),0):null
 return {start,rows,end:running,reconciled:Number.isSafeInteger(running)&&running===expected,allocation,trailerRecovery,
  capitalIncomplete:plan.pairs.some(p=>p.capital_complete===false),
  min:Math.min(0,start,...rows.map(r=>r.after)),max:Math.max(0,start,...rows.map(r=>r.after))}
}
