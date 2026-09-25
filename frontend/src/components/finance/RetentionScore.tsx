import { FormEvent, useRef, useState } from 'react'
import { Report, dollars, financeApi, financeError } from '../../services/finance'
import './RetentionScore.css'
import { Link } from 'react-router-dom'

type Retention = Report['retention']
const bands = {target_met:'Target met', acceptable:'Acceptable', below_floor:'Below acceptable', no_revenue:'No positive freight revenue'}

export function RetentionTargets({data, onSaved}: {data:Retention; onSaved:()=>Promise<void>}) {
  const [target,setTarget] = useState(data.targets.target_percent)
  const [floor,setFloor] = useState(data.targets.acceptable_percent)
  const [when,setWhen] = useState(data.minimum_effective_date)
  const request = useRef({body:'',key:''})
  const [busy,setBusy] = useState(false)
  const [message,setMessage] = useState('')
  const [error,setError] = useState('')
  async function save(e:FormEvent) {
    e.preventDefault();setError('');setMessage('')
    if (![target,floor].every(v=>/^\d+(\.\d{1,2})?$/.test(v)) || Number(floor)<=0 || Number(floor)>Number(target) || Number(target)>100) {
      setError('Enter percentages above 0 and at most 100. The acceptable floor cannot exceed the target.');return
    }
    setBusy(true)
    try {
      const payload = {kind:'retention_targets',target_percent:Number(target).toFixed(2),acceptable_percent:Number(floor).toFixed(2)}
      const body = JSON.stringify({when,payload})
      if(request.current.body!==body) request.current={body,key:crypto.randomUUID()}
      await financeApi.command(when,payload,request.current.key)
      await onSaved();setMessage(`Targets saved from ${when}. Reports use the targets effective at their period start.`)
    } catch(e) {setError(financeError(e))} finally {setBusy(false)}
  }
  return <details className="owner-details retention-targets"><summary>Adjust retention targets</summary>
    <form onSubmit={save}><p className="finance-help">Changes apply prospectively. A report uses the targets effective at its period start, so earlier results keep their benchmark. Dates use {data.settings_timezone}{data.settings_timezone==='UTC'?' until the business timezone is confirmed':''}.</p>{data.scheduled_targets.map((t,i)=><p className="finance-help" key={`${t.effective_date}-${i}`}>Recorded from {t.effective_date}: target {t.target_percent}%, acceptable {t.acceptable_percent}%. Later revisions on the same date take precedence.</p> )}
      <div className="retention-target-fields"><label>Target retained (%)<input required inputMode="decimal" value={target} onChange={e=>setTarget(e.target.value)}/></label><label>Acceptable retained (%)<input required inputMode="decimal" value={floor} onChange={e=>setFloor(e.target.value)}/></label><label>Effective from<input required type="date" min={data.minimum_effective_date} value={when} onChange={e=>setWhen(e.target.value)}/></label></div>
      {error&&<p role="alert" className="finance-error">{error}</p>}{message&&<p role="status" className="finance-success">{message}</p>}
      <button className="finance-secondary" disabled={busy}>{busy?'Saving targets…':'Save targets'}</button>
    </form></details>
}

export default function RetentionScore({pair, data}: {pair:Retention['pairs'][number]; data:Retention}) {
  const value = Number(pair.retained_per_100)
  const target = Number(data.targets.target_percent)
  const floor = Number(data.targets.acceptable_percent)
  const values = data.pairs.map(p=>Number(p.retained_per_100))
  const low = Math.min(0,...values)
  const high = Math.max(target*1.3,...values)
  const at = (v:number) => (v-low)/(high-low)*100
  const noRevenue = pair.score===null
  return <div className="retention-score">
    <div className="retention-result"><p><strong>{noRevenue?'—':Number(pair.score).toFixed(1)}</strong><span>retention score · 100 = target</span></p><p><strong>{noRevenue?'—':dollars(pair.retained_per_100)}</strong><span>retained per $100 of freight</span></p></div>
    <p className="retention-status">Provisional · {bands[pair.band]}</p>
    {!noRevenue && <div className="retention-chart" role="img" aria-label={`${dollars(pair.retained_per_100)} retained per $100. Acceptable ${dollars(data.targets.acceptable_percent)}, target ${dollars(data.targets.target_percent)}. Provisional.`}>
      <div className="retention-track"><span className="retention-range" style={{left:`${at(floor)}%`,width:`${at(target)-at(floor)}%`}}/><span className={`retention-bar ${value<0?'is-loss':''}`} style={{left:`${at(Math.min(0,value))}%`,width:`${Math.abs(at(value)-at(0))}%`}}/>
        <i className="retention-floor" style={{left:`${at(floor)}%`}}/><i className="retention-target" style={{left:`${at(target)}%`}}/>
      </div><div className="retention-axis"><span>{dollars(low)}</span><span>Dashed: acceptable · solid: target</span><span>{dollars(high)}</span></div>
    </div>}
    <details className="owner-details"><summary>How this score is calculated</summary><dl className="finance-waterfall">{pair.bridge.map(row=><div key={row.label}><dt>{row.label}</dt><dd>{dollars(row.amount)}</dd></div>)}<div><dt>Recorded retained contribution</dt><dd><strong>{dollars(pair.retained)}</strong></dd></div><div><dt>Freight revenue</dt><dd>{dollars(pair.freight)}</dd></div></dl>
      <p className="finance-help">Recorded amounts only. Zero means no amount recorded in this calculation; it does not confirm that a cost is absent. Book depreciation and equipment sale results are kept in the ownership reports.</p>
      {Boolean(pair.source_repair_ids?.length) && <p className="finance-help"><Link to="/repairs">Review {pair.source_repair_ids!.length} included historical repair records</Link> · references {pair.source_repair_ids!.join(', ')}</p>}
      <h4>Before relying on the score</h4><ul className="retention-gaps">{pair.issues.map(issue=><li key={issue}>{issue}</li>)}</ul>
    </details>
  </div>
}
