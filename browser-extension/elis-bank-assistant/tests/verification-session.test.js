import test from 'node:test';
import assert from 'node:assert/strict';
import {openVerificationSession} from '../verification-session.js';
const draft={from_last4:'3304',to_last4:'8264',bank_session:{profile_name:'Main Business'}};
function browser(results) {
 const calls=[];
 return {calls,tabs:{create:async options=>{calls.push(options);return {id:7}},get:async()=>({id:7})},scripting:{executeScript:async()=>[{result:results.shift() || []}]}};
}
test('manual check opens visible bank tab and waits for both required accounts',async()=>{
 const chrome=browser([[],['Business Checking **3304 $100.00'],['Business Checking **3304 $100.00','Business Preferred Line **8264 $200.00']]);
 const result=await openVerificationSession(chrome,draft,async()=>{}, {attempts:3,pause:async()=>{}});
 assert.equal(result.id,7);assert.equal(chrome.calls[0].active,true);
 assert.equal(chrome.calls[0].url,'https://www.truliantfcuonline.org/dbank/live/app/home');
});
test('wrong login never proceeds and leaves sign-in tab available',async()=>{
 const chrome=browser([['Business Checking **3304 $100.00','Preferred Line **2829 $200.00']]);
 await assert.rejects(openVerificationSession(chrome,draft,async()=>{}, {attempts:1,pause:async()=>{}}),/Sign-in or account access/);
});
test('closed login window gives an actionable result',async()=>{
 const chrome=browser([]);chrome.tabs.get=async()=>{throw new Error('gone')};
 await assert.rejects(openVerificationSession(chrome,draft,async()=>{}, {attempts:1,pause:async()=>{}}),/tab was closed/);
});
