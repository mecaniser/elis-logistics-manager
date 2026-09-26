import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { HistoryReport } from './historyTypes'
import { dateNumber, inRange, metricValue, monthBuckets, trendSegments, type TrendMetric, type TrendRange } from './historyTrendModel'
import { vehicleIdentities } from './vehicleIdentity'
import { dollars } from '../../services/finance'

const pairColors = ['#7c3aed', '#2563eb', '#0f766e', '#b45309']
const assetColor = (id: number) => pairColors[(Math.max(1, id)-1)%pairColors.length]
const labels: Record<TrendMetric, string> = {remainder:'Settlement remainder',fuel:'28-day fuel cost / mile',driver:'Driver share of freight'}
const monthLabel = (month: string) => new Date(`${month}-01T00:00:00Z`).toLocaleDateString('en-US',{month:'short',year:'2-digit',timeZone:'UTC'})

export default function HistoryTrend({history}: {history: HistoryReport}) {
  const latestYear = Number(history.period.end?.slice(0, 4) || new Date().getFullYear())
  const firstYear = Number(history.period.start?.slice(0, 4) || latestYear)
  const [metric, setMetric] = useState<TrendMetric>('remainder')
  const [period, setPeriod] = useState(String(latestYear))
  const [customStart, setCustomStart] = useState(`${latestYear}-01-01`)
  const [customEnd, setCustomEnd] = useState(history.period.end || `${latestYear}-12-31`)
  const years = Array.from({length:latestYear-firstYear+1},(_,index)=>latestYear-index)
  const range: TrendRange = period === 'all' ? {start:history.period.start || customStart,end:history.period.end || customEnd}
    : period === 'custom' ? {start:customStart,end:customEnd} : {start:`${period}-01-01`,end:Number(period)===latestYear ? history.period.end || `${period}-12-31` : `${period}-12-31`}
  const validRange = range.start <= range.end
  const filtered = validRange ? history.rows.filter(row => inRange(row.date,range)) : []
  const identities = vehicleIdentities(history.rows)
  const verifiedIds = new Set(history.rows.filter(row=>row.status==='arithmetic_matched').map(row=>row.asset_id))
  const assets = [...identities].filter(([id])=>verifiedIds.has(id)).map(([id,identity])=>[id,identity.label] as const)
  const assetIds = new Set(assets.map(([id])=>id))
  const segments = validRange ? trendSegments(history.rows.filter(row=>assetIds.has(row.asset_id)),range,metric) : []
  const byDate: Record<string, Record<string, string | number | null>> = {}
  for (const row of filtered.filter(item=>assetIds.has(item.asset_id))) {
    const value = metricValue(row,metric)
    if (value === null) continue
    const point = byDate[row.date] ||= {date:row.date,dateValue:dateNumber(row.date)}
    const segment = segments.find(item=>item.assetId===row.asset_id && item.dates.includes(row.date))
    if (segment) point[segment.key] = value
  }
  const points = Object.values(byDate).sort((a,b)=>Number(a.dateValue)-Number(b.dateValue))
  const format = (value: unknown) => value == null ? '—' : metric==='driver' ? `${Number(value).toFixed(1)}%` : dollars(value)
  const statusCount = (status: string) => filtered.filter(row => assetIds.has(row.asset_id) && row.status===status).length
  const displayEnd = range.end > (history.period.end || range.end) ? history.period.end || range.end : range.end
  const months = validRange && history.period.start && history.period.end
    ? monthBuckets(history.rows,{start:range.start < history.period.start ? history.period.start : range.start,end:displayEnd},assets[0]?.[0] || 0).map(item=>item.month) : []
  const dates = months.filter((_,index)=> index===0 || index===months.length-1 || index % Math.max(1,Math.ceil(months.length/6))===0).map(month=>dateNumber(`${month}-01`))
  const ownerOffRoad = history.tenant_id===1 && range.start<='2026-06-22' && range.end>='2026-05-10' && assets.some(([id])=>id===2)
  return <>
    <div className="finance-section-heading"><h2>Performance over time</h2></div>
    <div className="history-trend-controls">
      <label>Timeline<select aria-label="Timeline" value={period} onChange={event=>setPeriod(event.target.value)}>
        {years.map(year=><option key={year} value={year}>{year}</option>)}<option value="all">All recorded dates</option><option value="custom">Custom dates</option>
      </select></label>
      {period==='custom'&&<><label>From<input aria-label="Timeline from" type="date" value={customStart} onChange={event=>setCustomStart(event.target.value)} /></label><label>Through<input aria-label="Timeline through" type="date" value={customEnd} onChange={event=>setCustomEnd(event.target.value)} /></label></>}
      <label>Measure<select aria-label="Measure" value={metric} onChange={event=>setMetric(event.target.value as TrendMetric)}><option value="remainder">Settlement remainder</option><option value="fuel">28-day fuel cost / mile</option><option value="driver">Driver share of freight</option></select></label>
    </div>
    {!validRange?<p role="alert" className="finance-error">The start date must be on or before the end date.</p>:<>
      <p className="finance-help">Trucks are identified by VIN; current names are shown for reference. Each point is one source-checked statement, dated when the carrier issued it. A line stops after more than two settlement cycles without a verified point. {metric==='fuel'?'Fuel purchases per reported mile measure spending, not consumption.':'Gaps do not mean zero earnings.'}</p>
      <div className="history-trend-summary" aria-live="polite"><span><strong>{statusCount('arithmetic_matched')}</strong> verified statements</span><span><strong>{statusCount('missing_source')}</strong> saved records without originals</span><span><strong>{statusCount('needs_review')}</strong> originals needing review</span></div>
      {points.length ? <div className="owner-trend" role="img" aria-label={`${labels[metric]} from ${range.start} through ${range.end}. Verified statements are connected only within each truck's own series; exact dates and values follow below.`}>
        <ResponsiveContainer width="100%" height={290}><LineChart data={points} margin={{top:20,right:18,left:0,bottom:8}}>
          <CartesianGrid vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="dateValue" type="number" scale="time" domain={[dateNumber(range.start),dateNumber(range.end)]} allowDataOverflow ticks={dates} tickFormatter={value=>monthLabel(new Date(Number(value)).toISOString().slice(0,7))} minTickGap={35} tick={{fontSize:11}} />
          <YAxis width={65} tickFormatter={value=>metric==='driver'?`${value}%`:`$${value}`} />
          {ownerOffRoad&&<ReferenceArea x1={dateNumber('2026-05-10')} x2={dateNumber('2026-06-22')} fill="#eef1f5" strokeOpacity={0} ifOverflow="hidden" />}
          <Tooltip labelFormatter={value=>new Date(Number(value)).toISOString().slice(0,10)} formatter={(value,name)=>[format(value),String(name)]} />
          {segments.map(segment=><Line key={segment.key} name={assets.find(([id])=>id===segment.assetId)?.[1] || `Truck ${segment.assetId}`} dataKey={segment.key} stroke={assetColor(segment.assetId)} strokeWidth={2} dot={{r:3}} activeDot={{r:5}} connectNulls isAnimationActive={false} legendType="none" />)}
        </LineChart></ResponsiveContainer>
      </div>:<p className="finance-empty">No source-checked values for this measure in the selected period. Saved records still appear in the coverage below.</p>}
      <div className="owner-legend">{assets.map(([id,name])=><span key={id}><i style={{background:assetColor(id)}} /><span title={identities.get(id)?.vin}><strong>{name}</strong><small className="history-identity-secondary">Current: {identities.get(id)?.currentName}</small></span></span>)}</div>
      {ownerOffRoad&&<p className="history-trend-annotation"><strong>{identities.get(2)?.label} off road · May 10–June 22, 2026.</strong> Owner-reported: a driver had not yet been hired. The shaded interval marks this truck’s known gap; it does not assert zero revenue or apply to the other truck.</p>}
      <div className="history-coverage-heading"><h3>Record coverage by month</h3><Link to="/settlements/reconciliation?status=missing_source#review-records">Review all records without originals</Link></div>
      <p className="finance-help">A saved record is visible here even when its original PDF is unavailable. Only source-checked amounts appear on the line chart.</p>
      <div className="finance-table-scroll history-coverage-scroll"><table className="history-coverage-table"><caption className="sr-only">Monthly settlement evidence coverage for the selected timeline</caption><thead><tr><th>Truck</th>{months.map(month=><th key={month}>{monthLabel(month)}</th>)}</tr></thead><tbody>{assets.map(([id,name])=><tr key={id}><th scope="row" title={identities.get(id)?.vin}>{name}<small className="history-identity-secondary">Current: {identities.get(id)?.currentName}</small></th>{months.map(month=>{const item=monthBuckets(history.rows,{start:range.start,end:displayEnd},id).find(bucket=>bucket.month===month);return <td key={month}>{item&&(item.matched||item.missingOriginal||item.needsReview)?<span className="history-coverage-cell" aria-label={`${monthLabel(month)}: ${item.matched} verified, ${item.missingOriginal} saved without original, ${item.needsReview} original needing review`} title={`${item.matched} verified · ${item.missingOriginal} missing original · ${item.needsReview} needs review`}>{item.matched>0&&<b className="is-verified">{item.matched} verified</b>}{item.missingOriginal>0&&<b className="is-missing">{item.missingOriginal} without PDF</b>}{item.needsReview>0&&<b className="is-review">{item.needsReview} review</b>}</span>:<span className="finance-muted">No record</span>}</td>})}</tr>)}</tbody></table></div>
      <details className="owner-details"><summary>View exact verified values</summary><div className="finance-table-scroll"><table><caption className="sr-only">Source-checked historical trend values</caption><thead><tr><th>Date</th>{assets.map(([id,name])=><th key={id}>{name}</th>)}</tr></thead><tbody>{points.map(point=><tr key={String(point.date)}><td>{String(point.date)}</td>{assets.map(([id])=>{const segment=segments.find(item=>item.assetId===id&&item.dates.includes(String(point.date)));return <td key={id}>{format(segment ? point[segment.key] : null)}</td>})}</tr>)}</tbody></table></div></details>
    </>}
  </>
}
