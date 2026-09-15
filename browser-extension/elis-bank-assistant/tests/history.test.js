import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {findPostedEntry} from '../history.js';
const wanted={suffix:'1111',source:false,amount_cents:11820,memo:'Cvr Utility 0914',bank_date:'Sep 14, 2026'};
const section=label=>({getAttribute:()=>label,querySelector:()=>null});
const entry=(amount='$118.20',memo='Deposit Cvr Utility 0914',date='Sep 14, 2026')=>({getAttribute:()=>null,querySelector:s=>s.includes('amount-')?{textContent:amount,id:'opaque-test-transaction'}:s.includes('description-')?{textContent:memo}:s.includes('transactionDate-')?{textContent:date}:null});
function setup(rows,headings=[{textContent:'Test account 00001111'}]){
  globalThis.location={origin:'https://www.truliantfcuonline.org'};
  if(!globalThis.crypto) Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
  globalThis.document={querySelector:()=>({querySelectorAll:()=>rows}),querySelectorAll:()=>headings};
}
test('pending credits never confirm a transfer',async()=>{
  setup([section('pending transactions section'),entry(),section('posted transactions section')]);
  assert((await findPostedEntry(wanted)).error);
});
test('one exact posted deposit returns only hashed evidence',async()=>{
  setup([section('posted transactions section'),entry()]);
  assert.match((await findPostedEntry(wanted)).match,/^[a-f0-9]{64}$/);
});
test('identical responsive account headings do not create false ambiguity',async()=>{
  const heading={textContent:'Test account 00001111'};
  setup([section('posted transactions section'),entry()],[heading,heading]);
  assert.match((await findPostedEntry(wanted)).match,/^[a-f0-9]{64}$/);
});
test('conflicting account headings still fail closed',async()=>{
  setup([section('posted transactions section'),entry()],[{textContent:'Test account 00001111'},{textContent:'Other account 99991111'}]);
  assert.equal((await findPostedEntry(wanted)).error,'Account identity could not be verified.');
});
test('duplicates, wrong date, wrong amount, and wrong memo stay unconfirmed',async()=>{
  for(const rows of [[entry(),entry()],[entry('$118.21')],[entry('$118.20','Deposit Cvr Other')],[entry('$118.20','Deposit Cvr Utility 0914','Sep 13, 2026')]]){
    setup([section('posted transactions section'),...rows]);
    assert((await findPostedEntry(wanted)).error);
  }
});
test('source requires a disbursement with the opposite sign',async()=>{
  setup([section('posted transactions section'),entry()]);
  assert((await findPostedEntry({...wanted,source:true})).error);
  setup([section('posted transactions section'),entry('-$118.20','Principal Disbursement Cvr / Utility 0914')]);
  assert((await findPostedEntry({...wanted,source:true})).match);
});
