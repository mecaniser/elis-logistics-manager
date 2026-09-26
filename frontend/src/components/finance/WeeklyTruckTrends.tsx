import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { HistoryReport } from './historyTypes'
import type { TrendRange } from './historyTrendModel'
import { truckDowntime, weeklyTruckPoints } from './weeklyTruckModel'
import { vehicleIdentities } from './vehicleIdentity'
import { dollars } from '../../services/finance'
const shortDate=(date:string)=>new Date(`${date}T00:00:00Z`).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'2-digit',timeZone:'UTC'})
const colors=['#7c3aed','#2563eb','#0f766e','#b45309','#be185d']
const color=(id:number)=>colors[(id-1)%colors.length]
export default function WeeklyTruckTrends({history,range}:{history:HistoryReport;range:TrendRange}) {
  const [mode,setMode]=useState('single')
  const [truck,setTruck]=useState<number|null>(null)
  const [compared,setCompared]=useState<number[]>([])
  const [average,setAverage]=useState(false)
  const [view,setView]=useState('lines')
  const [week,setWeek]=useState('')
  const identities=vehicleIdentities(history.rows)
  const trucks=[...identities].filter(([id])=>history.rows.some(r=>r.asset_id===id && r.vehicle_type==='truck'))
  const series=trucks.map(([id,identity])=>{const downtime=truckDowntime(history.rows,history.tenant_id,id);return {id,identity,downtime,points:weeklyTruckPoints(history.rows,id,range,downtime)}})
  const activeId=series.some(s=>s.id===truck)?truck:series[0]?.id
  const comparison=compared.length?compared:series.slice(0,2).map(s=>s.id)
  const visible=series.filter(s=>mode==='fleet'||(mode==='single'?s.id===activeId:comparison.includes(s.id)))
  const points=(series[0]?.points||[]).map((p,index)=>{
    const values=visible.map(s=>s.points[index].value)
    const known=values.filter((v):v is number=>v!==null)
    return {date:p.date,through:p.through,fleet:known.length?known.reduce((a,b)=>Math.round((a+b)*100)/100,0):null,partial:known.length<visible.length,
      ...Object.fromEntries(visible.map(s=>[`truck${s.id}`,s.points[index].value])),average:mode==='single'?visible[0]?.points[index].average:null as number|null}
  })
  if(mode==='fleet')points.forEach((p,index)=>{const window=points.slice(Math.max(0,index-3),index+1);p.average=window.length===4&&window.every(w=>!w.partial&&w.fleet!==null&&(Date.parse(w.through)-Date.parse(w.date))===6*86400000)?window.reduce((n,w)=>n+w.fleet!,0)/4:null})
  const selected=points.find(p=>p.date===week)
  const selectedRows=visible.flatMap(s=>s.points.find(p=>p.date===week)?.records||[])
  const days=Math.round((Date.parse(range.end)-Date.parse(range.start))/86400000)+1
  const title=mode==='fleet'?(view==='heatmap'?'Weekly remainder by truck':'Fleet statement remainder'):mode==='compare'?'Compare trucks':visible[0]?.identity.label||'Truck history'
  return <div className="weekly-trucks">
    <div className="chart-view-switch" role="group" aria-label="Chart representation">{['lines','columns','heatmap'].map(option=><button type="button" key={option} aria-pressed={view===option} onClick={()=>setView(option)}>{option==='lines'?'Lines':option==='columns'?'Columns':'Heatmap'}</button>)}</div>
    <div className="history-trend-controls compact-chart-controls">
      <label>Scope<select aria-label="Chart scope" value={mode} onChange={e=>{setMode(e.target.value);setWeek('')}}><option value="single">Single truck</option><option value="fleet">{view==='heatmap'?'All trucks':'Fleet total'}</option><option value="compare">Compare up to 3</option></select></label>
      {mode==='single'&&<label>Truck<select aria-label="Selected truck" value={activeId||''} onChange={e=>{setTruck(Number(e.target.value));setWeek('')}}>{series.map(s=><option key={s.id} value={s.id}>{s.identity.label}</option>)}</select></label>}
      {view!=='heatmap'&&mode!=='compare'&&<label className="weekly-average"><input type="checkbox" checked={average} onChange={e=>setAverage(e.target.checked)}/> Four-week average</label>}
    </div>
    <p className="finance-help">Weekly settlement remainder before outside expenses, grouped by statement date. Multiple statements can fall in one week. {mode==='fleet'&&view!=='heatmap'?'Fleet charts sum available verified amounts; weeks with incomplete coverage are provisional.':'Blank weeks are not zero earnings.'}</p>
    <div className="compact-chart-heading"><h3>{title}</h3>{mode==='single'&&<span>Current: {visible[0]?.identity.currentName}</span>}</div>
    {view==='heatmap'?<>
      <p className="finance-help">Each row is a truck; each cell is one week. Darker teal means a higher positive remainder; red means negative. Select a cell to inspect the statements.</p>
      <div className="truck-heatmap" tabIndex={0} role="region" aria-label="Weekly truck heatmap, scroll horizontally for all dates"><table><thead><tr><th scope="col">Truck / week</th>{points.map(p=><th scope="col" key={p.date}>{shortDate(p.date)}</th>)}</tr></thead><tbody>{visible.map(s=>{const max=Math.max(1,...visible.flatMap(v=>v.points.map(p=>Math.abs(p.value||0))));return <tr key={s.id}><th scope="row">{s.identity.label}</th>{s.points.map(p=>{
        const state=p.value!==null?'value':p.status==='Review evidence'?'review':p.offRoad?'offroad':'unknown'
        const darkBand=p.value!==null&&p.value/max>0.66
        const background=p.value===null?undefined:p.value<0?'#fee2e2':p.value===0?'#f1f5f9':darkBand?'#0f766e':p.value/max>0.33?'#b4d8d0':'#e2f1ed'
        const label=`${s.identity.label}, ${shortDate(p.date)} through ${shortDate(p.through)}: ${p.value!==null?dollars(p.value):p.status}${p.offRoad?'; owner-reported downtime':''}`
        return <td key={p.date}><button type="button" className={`heat-cell is-${state}`} style={{background,color:darkBand?'#fff':'#172f3b'}} aria-label={label} title={label} aria-pressed={week===p.date} onClick={()=>setWeek(p.date)}>{p.value!==null?dollars(p.value):state==='offroad'?'Off road':state==='review'?'Review':'No record'}</button></td>
      })}</tr>})}</tbody></table></div>
      <p className="weekly-key">Teal: positive · Red: negative · Gray: downtime · Amber hatch: review · Pale: no statement. Values share one scale across visible trucks.</p>
    </>:<div role="img" aria-label={`${title}, weekly statement remainder from ${range.start} through ${range.end}`}>
      <ResponsiveContainer width="100%" height={280}><ComposedChart data={points} margin={{top:16,right:12,bottom:0,left:0}}>
        <CartesianGrid vertical={false} stroke="#e2e8f0"/>
        <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={55} tick={{fontSize:11}}/>
        <YAxis width={56} tickFormatter={v=>v===0?'$0':`${v<0?'-':''}$${Math.abs(v)/1000}k`} tick={{fontSize:11}}/>
        {mode==='single'&&visible[0]?.downtime.map(d=>{const covered=points.filter(p=>p.through>=d.start&&p.date<=d.end);return covered.length?<ReferenceArea key={d.start} x1={covered[0].date} x2={covered[covered.length-1].date} fill="#c4cbd0" fillOpacity={0.38} strokeOpacity={0}/>:null})}
        <ReferenceLine y={0} stroke="#82919c"/>
        <Tooltip wrapperStyle={{maxWidth:220,pointerEvents:'none'}} content={({active,payload})=>{const p=payload?.[0]?.payload as typeof selected;if(!active||!p)return null;return <div className="weekly-tooltip"><strong>{shortDate(p.date)}–{shortDate(p.through)}</strong>{payload?.map(item=><p key={String(item.dataKey)}>{item.name}: {dollars(item.value)}</p>)}{mode==='fleet'&&p.partial&&<strong>Partial fleet coverage</strong>}<small>Choose this week below to inspect statements.</small></div>}}/>
        {view==='columns'?(mode==='fleet'?<Bar name="Fleet subtotal" dataKey="fleet" fill="#2563eb" maxBarSize={26} isAnimationActive={false} onClick={data=>setWeek(data.payload.date)}/>:visible.map(s=><Bar key={s.id} name={s.identity.label} dataKey={`truck${s.id}`} fill={color(s.id)} maxBarSize={26} isAnimationActive={false} onClick={data=>setWeek(data.payload.date)}/>)):(mode==='fleet'?<Line name="Fleet subtotal" dataKey="fleet" type="linear" stroke="#2563eb" strokeWidth={2} dot={{r:3}} connectNulls={false} isAnimationActive={false}/>:visible.map(s=><Line key={s.id} name={s.identity.label} dataKey={`truck${s.id}`} type="linear" stroke={color(s.id)} strokeWidth={2} dot={{r:3}} connectNulls={false} isAnimationActive={false}/>))}
        {average&&mode!=='compare'&&<Line name="Four-week average" dataKey="average" stroke="#172f3b" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false}/>}
      </ComposedChart></ResponsiveContainer>
    </div>}
    {view!=='heatmap'&&mode!=='fleet'&&visible.map(s=><div className="compact-status" key={s.id}><span style={{color:color(s.id)}}>{s.identity.label}</span><div className="weekly-status-track" aria-label={`${s.identity.label} operating status`}>{s.points.map(p=><span key={p.date} className={p.offRoad?'is-offroad':p.status==='Review evidence'?'is-review':p.value===null?'is-unknown':'is-recorded'} title={`${p.date}: ${p.status}`}/>)}</div></div>)}
    {mode==='single'&&visible[0]?.downtime.filter(d=>d.end>=range.start&&d.start<=range.end).map(d=><p className="weekly-downtime" key={d.start}><strong>Out of service · {shortDate(d.start)}–{shortDate(d.end)}</strong><span>{d.description}</span></p>)}
    {view!=='heatmap'&&mode!=='fleet'&&<p className="weekly-key">Gray: owner-reported downtime · Amber hatch: evidence review · Pale: no statement</p>}
    <label className="weekly-inspect">Inspect a week<select aria-label="Inspect chart week" value={selected?week:''} onChange={e=>setWeek(e.target.value)}><option value="">Choose a week…</option>{points.map(p=><option value={p.date} key={p.date}>{shortDate(p.date)}–{shortDate(p.through)}</option>)}</select></label>
    {selected&&<section className="weekly-selected" aria-live="polite"><h3>Statements dated {shortDate(selected.date)}–{shortDate(selected.through)}</h3>{!selectedRows.length&&<p>No statement recorded in this week; this is not a zero-earnings claim.</p>}{selectedRows.map(r=><Link key={r.id} to={`/settlements/reconciliation?asset=${r.asset_id}&id=${r.id}#review-records`}>{identities.get(r.asset_id)?.label} · {r.date} · {r.provider} · {dollars(r.remainder)} — review statement</Link>)}</section>}
    <div className="compact-fleet-table"><table><caption>{mode==='compare'?'Select up to three trucks to compare':'Select a truck to inspect its chart'}</caption><thead><tr><th>Truck</th><th>Plotted remainder</th><th>Per calendar day</th><th>Statement coverage</th></tr></thead><tbody>{series.map(s=>{const period=history.rows.filter(r=>r.asset_id===s.id&&r.date>=range.start&&r.date<=range.end);const verified=period.filter(r=>r.status==='arithmetic_matched').length;const values=s.points.filter(p=>p.value!==null);const total=values.reduce((sum,p)=>sum+Math.round(p.value!*100),0)/100;return <tr key={s.id} className={visible.some(v=>v.id===s.id)&&mode!=='fleet'?'is-selected':''}><th scope="row">{mode==='compare'?<label><input type="checkbox" aria-label={`Compare ${s.identity.label}`} checked={comparison.includes(s.id)} disabled={comparison.includes(s.id)?comparison.length===1:comparison.length>=3} onChange={e=>{const next=e.target.checked?[...comparison,s.id]:comparison.filter(id=>id!==s.id);if(next.length)setCompared(next)}}/>{s.identity.label}</label>:<button type="button" className="compact-truck-button" onClick={()=>{setMode('single');setTruck(s.id);setWeek('')}}>{s.identity.label}</button>}<small className="history-identity-secondary">{s.identity.currentName}</small></th><td>{values.length?dollars(total):'Not established'}</td><td>{values.length?dollars(total/days):'Not established'}</td><td>{verified} / {period.length} verified</td></tr>})}</tbody></table></div>
    <p className="finance-help">Subtotals include only plotted verified weeks. Calendar-day figures include downtime; missing evidence leaves them provisional. Coverage counts saved statements, not expected operating weeks.</p>
  </div>
}
