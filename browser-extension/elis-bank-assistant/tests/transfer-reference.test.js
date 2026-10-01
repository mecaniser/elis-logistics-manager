import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {transferReference} from '../contract.js';
import {findPostedEntry} from '../history.js';
const id='a1b2c3d4-1234-4567-89ab-0123456789ab';
const memo='Cvr LifeCafe 10-01 a1b2c3d4';
test('reference is extracted from saved memo only when bound to the draft ID',()=>{
 assert.equal(transferReference({id,memo}),'a1b2c3d4');
 assert.equal(transferReference({id,memo:'Cvr ELIS a1b2c3d4-1234'}),'a1b2c3d4-1234');
 for(const d of [{id,memo:'Cvr Other deadbeef'},{id,memo:'Cvr Utility 1001'},{id:'invalid',memo}]) assert.equal(transferReference(d),null);
});
const source=readFileSync(new URL('../bank-history-content.js',import.meta.url),'utf8');
function fixture(text,{amount='$339.00',date='Oct 1, 2026',suffix='3304',pending=false,duplicate=false}={}) {
 const row={getAttribute:()=>null,querySelector:s=>s.includes('amount-')?{textContent:amount,id:'opaque-row'}:s.includes('description-')?{textContent:text}:{textContent:date}};
 const rows=[{getAttribute:()=>pending?'pending transactions section':'posted transactions section'},row,...(duplicate?[row]:[])];
 return {querySelector:()=>({querySelectorAll:()=>rows}),querySelectorAll:()=>[{textContent:`Account ${suffix}`} ]};
}
const wanted={suffix:'3304',source:false,kind:'coverage',amount_cents:33900,bank_date:'Oct 1, 2026',memo,reference:transferReference({id,memo})};
async function check(document,content) {
 if(!content){globalThis.document=document;globalThis.location={origin:'https://www.truliantfcuonline.org'};return findPostedEntry(wanted);}
 let listener;const context={window:{},location:{origin:'https://www.truliantfcuonline.org'},document,crypto:webcrypto,TextEncoder,setTimeout,chrome:{runtime:{onMessage:{addListener:fn=>listener=fn}}}};
 context.window.top={};vm.runInNewContext(source,context);
 return new Promise(resolve=>listener({type:'ELIS_FIND_POSTED',wanted},{},resolve));
}
for(const content of [false,true]) {
 test(`${content?'content script':'history reader'} accepts changed label with intact ID`,async()=>{
  assert.match((await check(fixture('Deposit Cvr Membership 10-01 / A1B2C3D4'),content)).match,/^[a-f0-9]{64}$/);
 });
 test(`${content?'content script':'history reader'} rejects altered IDs and unrelated bank entries`,async()=>{
  for(const text of ['Deposit Cvr Membership deadbeef','Deposit Cvr Membership a1b2c3d40','Deposit Cvr Membership xa1b2c3d4','Deposit Cvr Membership a1b2c3d4-1234','Deposit Cvr Membership']) assert.ok((await check(fixture(text),content)).error,text);
  for(const options of [{amount:'$338.00'},{date:'Oct 2, 2026'},{suffix:'9551'},{pending:true},{duplicate:true}]) assert.ok((await check(fixture('Deposit Cvr Membership a1b2c3d4',options),content)).error,JSON.stringify(options));
 });
}
