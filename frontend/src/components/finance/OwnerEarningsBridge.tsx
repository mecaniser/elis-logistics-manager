import OwnerContributionDetails from './OwnerContributionDetails'
import InvestmentDeductions from './InvestmentDeductions'
import {useState} from 'react'
import {Link} from 'react-router-dom'
import {dollars,type EarningsPlan} from '../../services/finance'
import {ownerEarningsModel} from './ownerEarningsModel'
import './OwnerEarningsBridge.css'
export default function OwnerEarningsBridge({plan,period}:{plan:EarningsPlan;period?:{start:string;end:string}}){
 const [trailerOpen,setTrailerOpen]=useState(false)
 const model=ownerEarningsModel(plan)
 if(!model.reconciled)return <p role="status" className="finance-error">The earnings breakdown needs reconciliation. Review the pair calculations below.</p>
 const position=(value:number)=>(value-model.min)/(model.max-model.min||1)*100
 return <div className="owner-earnings-bridge" aria-label="Statement remainder to owner earnings">
  <div className="owner-earnings-start"><span>Statement remainder</span><strong>{dollars(model.start/100)}</strong></div>
  <div className="owner-earnings-steps">{model.rows.map((row,index)=><div key={index} className={`owner-earnings-step earnings-tone-${row.tone}`}>
   <div>{row.label==='Equipment capital recovery'||row.label==='Additional planned loan payments'?<InvestmentDeductions plan={plan} kind={row.label==='Equipment capital recovery'?'capital':'loan'} label={row.label}/>:<span>{row.label}</span>}<strong>{row.tone==='loan'&&row.amount===0?'No recorded payments':`${row.amount<0?'−':row.amount>0?'+':''}${dollars(Math.abs(row.amount)/100)}`}</strong></div>
   <div className="owner-earnings-track" aria-hidden="true"><i style={{left:`${position(Math.min(row.before,row.after))}%`,width:`${Math.abs(position(row.after)-position(row.before))}%`}}/></div>
  </div>)}</div>
  {model.allocation!==null&&<div className="owner-trailer-split"><button type="button" aria-expanded={trailerOpen} onClick={()=>setTrailerOpen(!trailerOpen)}>Trailer allocation · {dollars(model.allocation/100)}<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{transform:trailerOpen?'rotate(90deg)':undefined}}><path d="m9 18 6-6-6-6"/></svg></button>{trailerOpen&&<dl className="finance-waterfall"><div><dt>Kept for trailer recovery · included above</dt><dd>{dollars(model.trailerRecovery!/100)}</dd></div><div><dt>Trailer earnings before other costs & financing · stays in the result</dt><dd>{dollars((model.allocation-model.trailerRecovery!)/100)}</dd></div></dl>}</div>}
  <div className="owner-earnings-final"><div><OwnerContributionDetails plan={plan} period={period} label={model.end<0?'Estimated funding shortfall':'Estimated left for you'}/><strong>{dollars(model.end/100)}</strong></div><span>After costs and money kept in the business</span></div>
  <p className="finance-help">Based on your business records and repayment plans{model.capitalIncomplete?'. Some equipment recovery plans are incomplete.':'.'} <Link to="/finance/money">Review money details</Link></p>
 </div>
}
