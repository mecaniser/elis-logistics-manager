import test from 'node:test'
import assert from 'node:assert/strict'
import {weeklyTruckPoints,truckDowntime} from '../src/components/finance/weeklyTruckModel.ts'
const row=(date,remainder='100',status='arithmetic_matched')=>({asset_id:1,date,remainder,status,vin:'4V4WC9EG2LN250024',provider:'277 Logistics'})
test('calendar weeks sum distinct statements without converting missing or incomplete evidence to zero',()=>{
 const points=weeklyTruckPoints([row('2026-03-02','100.10'),row('2026-03-07','200.20'),row('2026-03-16','80','missing_source'),row('2026-03-23','-50')],1,{start:'2026-03-02',end:'2026-03-29'},[])
 assert.deepEqual(points.map(p=>p.value),[300.3,null,null,-50])
 assert.equal(points[3].average,null)
})
test('average requires four complete verified consecutive calendar weeks',()=>{
 const rows=['2026-03-02','2026-03-09','2026-03-16','2026-03-23'].map((d,i)=>row(d,String(100*(i+1))))
 assert.equal(weeklyTruckPoints(rows,1,{start:'2026-03-02',end:'2026-03-29'},[])[3].average,250)
 assert.equal(weeklyTruckPoints(rows,1,{start:'2026-03-02',end:'2026-03-25'},[])[3].average,null)
})
test('confirmed vehicle transition is bracketed by carrier statements and does not fabricate earnings',()=>{
 const rows=[row('2026-03-07'),{...row('2026-04-06'),provider:'77 Cargo LLC'}]
 const downtime=truckDowntime(rows,1,1)
 assert.equal(downtime[0].start,'2026-03-08');assert.equal(downtime[0].end,'2026-04-05')
 assert.deepEqual(truckDowntime(rows,2,1),[])
 const points=weeklyTruckPoints(rows,1,{start:'2026-03-09',end:'2026-04-05'},downtime)
 assert.ok(points.every(p=>p.offRoad&&p.value===null))
})
