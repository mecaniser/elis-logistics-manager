import { fuelMileageReport } from './fuelMileageModel'
import type { FuelSource } from './freightFlowModel'
import type { HistoryReport } from './historyTypes'
const number=(value:number|null)=>value===null?'Unavailable':value.toLocaleString('en-US',{maximumFractionDigits:1})
export default function FuelMileageReport({sources,history}:{sources:FuelSource[];history?:HistoryReport|null}){
 const report=fuelMileageReport(sources,history)
 return <section className="freight-fuel-detail" aria-label="Miles versus fuel report"><h3>Miles vs fuel purchased</h3>
 <p className="finance-help">Your reference: 6–7 MPG. Purchases are not consumption; tank levels, idling and purchase timing affect comparisons.</p>
 <div className="fuel-mileage-grid">{report.selected.map(row=><article key={row.id}><div className="finance-section-heading"><strong>{row.name} · {row.date}</strong><span>{row.status}</span></div>
 <dl className="finance-waterfall"><div><dt>Reported miles</dt><dd>{number(row.miles)} mi</dd></div><div><dt>Gallons purchased · all products</dt><dd>{number(row.purchased)} gal</dd></div><div><dt>Expected diesel at 6–7 MPG</dt><dd>{row.expected?`${number(row.expected[0])}–${number(row.expected[1])} gal`:'Unavailable'}</dd></div><div><dt>Miles / diesel gallon purchased</dt><dd>{row.mpg===null?'Not established':row.mpg.toFixed(2)}</dd></div></dl>
 {row.issues.length>0&&<p className="finance-help">{row.issues.join(' ')}</p>}</article>)}</div>
 <h4>28-day comparison · {report.start}–{report.end}</h4>
 {report.rolling.map(row=><div className="fuel-window-row" key={row.assetId}><strong>{row.name}</strong><span>{row.count} statements</span><span>{row.mpg===null?'Not established':`${row.mpg.toFixed(2)} mi/gal purchased · ${row.status}`}</span></div>)}
 <p className="finance-help">Statement-date window; missing statements and overlapping service dates can limit coverage. Weekly results are early signals, not proof of fuel loss.</p>
 </section>
}
