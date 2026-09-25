import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { HistoryReport } from './historyTypes'
import { dollars } from '../../services/finance'
const pairColors = ['#2563eb', '#7c3aed', '#0f766e', '#b45309']
export default function HistoryTrend({history}: {history: HistoryReport}) {
  const [metric, setMetric] = useState('remainder')
  const eligible = history.rows.filter(r => r.status === 'arithmetic_matched')
  const assets = [...new Map(eligible.map(r => [r.asset_id, r.name])).entries()].sort((a,b) => a[1].localeCompare(b[1]))
  const byDate: Record<string, Record<string, string | number | null>> = {}
  const assetIds = new Set(assets.map(([id]) => id))
  for (const r of history.rows.filter(row => assetIds.has(row.asset_id))) {
    const day = byDate[r.date] ||= {date: r.date, dateValue: Date.parse(r.date)}
    const value = r.status !== 'arithmetic_matched' ? null : metric === 'fuel' ? r.rolling_fuel_per_mile : metric === 'driver' ? r.driver_percent : r.remainder
    day[String(r.asset_id)] = value === null ? null : Number(value)
  }
  const points = Object.values(byDate).sort((a,b) => String(a.date).localeCompare(String(b.date)))
  const format = (v: unknown) => v === null || v === undefined ? 'Not established' : metric === 'driver' ? `${Number(v).toFixed(1)}%` : dollars(v)
  return <><div className="finance-section-heading"><h2>Performance over time</h2><label className="finance-inline-label">Measure<select value={metric} onChange={e => setMetric(e.target.value)}><option value="remainder">Settlement remainder</option><option value="fuel">28-day fuel cost / mile</option><option value="driver">Driver share of freight</option></select></label></div>
    <p className="finance-help">Arithmetic-matched statement history. Carrier changes and different service dates affect comparisons. {metric === 'fuel' ? 'Rolling 28-day fuel purchases ÷ reported miles. This measures spending, not consumption.' : 'Only arithmetic-matched originals are plotted. Gaps are not zero earnings.'}</p>
    {points.length > 1 ? <div className="owner-trend" role="img" aria-label={`${metric === 'remainder' ? 'Settlement remainder' : metric === 'fuel' ? 'Rolling fuel cost per mile' : 'Driver share'} by statement date; exact values in the table below`}><ResponsiveContainer width="100%" height={270}><LineChart data={points} margin={{top:20,right:12,left:0,bottom:0}}><CartesianGrid vertical={false} stroke="#e2e8f0" /><XAxis dataKey="dateValue" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={v => new Date(Number(v)).toISOString().slice(5,10)} minTickGap={40} /><YAxis width={65} tickFormatter={v => metric==='driver' ? `${v}%` : `$${v}`} /><Tooltip labelFormatter={v => new Date(Number(v)).toISOString().slice(0,10)} formatter={v => format(v)} />{assets.map(([id, name],i) => <Line key={id} name={name} dataKey={String(id)} stroke={pairColors[i%pairColors.length]} strokeWidth={2} dot={{r:2}} connectNulls={false} isAnimationActive={false} />)}</LineChart></ResponsiveContainer></div> : <p className="finance-empty">At least two source-checked dates are needed for a trend.</p>}
    <div className="owner-legend">{assets.map(([id,name],i)=><span key={id}><i style={{background:pairColors[i%pairColors.length]}} />{name}</span>)}</div>
    <details className="owner-details"><summary>View exact trend values</summary><div className="finance-table-scroll"><table><caption className="sr-only">Source-checked historical trend values</caption><thead><tr><th>Date</th>{assets.map(([id,name])=><th key={id}>{name}</th>)}</tr></thead><tbody>{points.map(p=><tr key={String(p.date)}><td>{p.date}</td>{assets.map(([id])=><td key={id}>{format(p[String(id)])}</td>)}</tr>)}</tbody></table></div></details>
  </>
}
