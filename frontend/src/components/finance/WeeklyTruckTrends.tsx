import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { HistoryReport } from './historyTypes'
import type { TrendRange } from './historyTrendModel'
import { truckDowntime, weeklyTruckPoints } from './weeklyTruckModel'
import { vehicleIdentities } from './vehicleIdentity'
import { dollars } from '../../services/finance'
const shortDate=(date:string)=>new Date(`${date}T00:00:00Z`).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'2-digit',timeZone:'UTC'})
export default function WeeklyTruckTrends({history,range}:{history:HistoryReport;range:TrendRange}) {
  const [average,setAverage]=useState(true)
  const [selection,setSelection]=useState<{assetId:number;date:string}|null>(null)
  const identities=vehicleIdentities(history.rows)
  const trucks=[...identities].filter(([id])=>history.rows.some(r=>r.asset_id===id && r.vehicle_type==='truck'))
  const series=trucks.map(([id,identity])=>{const downtime=truckDowntime(history.rows,history.tenant_id,id);return {id,identity,downtime,points:weeklyTruckPoints(history.rows,id,range,downtime)}})
  const values=series.flatMap(s=>s.points.flatMap(p=>p.value===null?[]:[p.value]))
  const selected=series.find(s=>s.id===selection?.assetId)?.points.find(p=>p.date===selection?.date)
  const domain:[number,number]=[Math.floor(Math.min(0,...values)/1000)*1000,Math.ceil(Math.max(100,...values)/1000)*1000]
  return <div className="weekly-trucks">
    <div className="weekly-explainer"><p className="finance-help">One column per calendar week, using statement dates. Both trucks share the same scale. A week can contain multiple statements. Outside repairs are not deducted here yet.</p><label><input type="checkbox" checked={average} onChange={e=>setAverage(e.target.checked)}/> Four-week average</label></div>
    {series.map(({id,identity,points,downtime})=><section className="weekly-truck" key={id}>
      <header><div><h3 title={identity.vin}>{identity.label}</h3><p className="finance-help">Current: {identity.currentName}</p></div><span>Settlement remainder · USD</span></header>
      <div role="img" aria-label={`${identity.label}: weekly statement remainder, ${range.start} through ${range.end}; blank weeks are not zero earnings.`}>
        <ResponsiveContainer width="100%" height={230}><ComposedChart data={points} syncId="truck-weeks" margin={{top:14,right:12,bottom:0,left:0}}>
          <CartesianGrid vertical={false} stroke="#e2e8f0"/>
          <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={55} tick={{fontSize:11}}/>
          <YAxis width={66} domain={domain} tickFormatter={v=>v===0?'$0':`${v<0?'-':''}$${Math.abs(v)/1000}k`} tick={{fontSize:11}}/>
          {downtime.map(d=>{const covered=points.filter(p=>p.through>=d.start&&p.date<=d.end);return covered.length?<ReferenceArea key={d.start} x1={covered[0].date} x2={covered[covered.length-1].date} fill="#c4cbd0" fillOpacity={0.38} strokeOpacity={0}/>:null})}
          <ReferenceLine y={0} stroke="#82919c"/>
          <Tooltip wrapperStyle={{maxWidth:200,pointerEvents:'none'}} content={({active,payload})=>{const p=payload?.[0]?.payload as typeof selected;if(!active||!p)return null;return <div className="weekly-tooltip"><strong>{shortDate(p.date)} – {shortDate(p.through)}</strong><p>{p.value===null?p.status:dollars(p.value)}</p>{p.average!==null&&average&&<p>Four-week average: {dollars(p.average)}</p>}<small>{p.records.length} statement{p.records.length===1?'':'s'} in this week</small></div>}}/>
          <Bar name="Statement remainder" dataKey="value" fill={id===1?'#7c3aed':'#2563eb'} maxBarSize={24} isAnimationActive={false} onClick={data=>setSelection({assetId:id,date:data.payload.date})} cursor="pointer"/>
          {average&&<Line name="Four-week average" dataKey="average" stroke="#172f3b" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false}/>}
        </ComposedChart></ResponsiveContainer>
      </div>
      <div className="weekly-status-track" aria-label={`${identity.label} weekly evidence and operating status`}>{points.map(p=><span key={p.date} className={p.offRoad?'is-offroad':p.status==='Review evidence'?'is-review':p.value===null?'is-unknown':'is-recorded'} title={`${p.date}–${p.through}: ${p.status}`} aria-label={`${p.date}: ${p.status}`}/>)}</div>
      <label className="weekly-inspect">Inspect a week<select aria-label={`Inspect week for ${identity.label}`} value={selection?.assetId===id?selection.date:''} onChange={e=>setSelection({assetId:id,date:e.target.value})}><option value="">Choose a week…</option>{points.map(p=><option value={p.date} key={p.date}>{shortDate(p.date)} · {p.value===null?p.status:dollars(p.value)}</option>)}</select></label>
      {downtime.filter(d=>d.end>=range.start&&d.start<=range.end).map(d=><p className="weekly-downtime" key={d.start}><strong>Out of service · {shortDate(d.start)}–{shortDate(d.end)}</strong><span>{d.description}</span></p>)}
    </section>)}
    <p className="weekly-key"><span>Solid gray: owner-reported downtime</span><span>Amber hatch: evidence needs review</span><span>Pale: no statement recorded</span>{average&&<span>Dark line: four verified consecutive weeks</span>}</p>
    {selected&&<section className="weekly-selected" aria-live="polite"><h3>Statements dated {shortDate(selected.date)}–{shortDate(selected.through)}</h3><p>Combined statement remainder: {dollars(selected.value)}. This is before outside expenses.</p>{selected.records.map(r=><Link key={r.id} to={`/settlements/reconciliation?asset=${r.asset_id}&id=${r.id}#review-records`}>{r.date} · {r.provider} · {dollars(r.remainder)} — review statement</Link>)}</section>}
  </div>
}
