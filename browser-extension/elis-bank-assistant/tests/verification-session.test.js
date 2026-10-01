import test from 'node:test';
import assert from 'node:assert/strict';
import {BANK_HOME, focusTransferTab, openVerificationSession, closeBackgroundHistoryTab, assertBackgroundHistoryTab} from '../verification-session.js';
const draft={from_last4:'3304',to_last4:'8264',bank_session:{profile_name:'Main Business'}};
const accounts=['Business Checking **3304 $100.00','Business Preferred Line **8264 $200.00'];
function browser(results) {
 const calls=[],updates=[],removed=[],windowUpdates=[]; let nextId=7;
 return {calls,updates,removed,windowUpdates,tabs:{
  create:async options=>{calls.push(options);return {id:nextId++,url:options.url,windowId:3}},
  get:async id=>({id,url:BANK_HOME,windowId:3}),
  update:async(id,options)=>{updates.push({id,...options});return {id,url:BANK_HOME}},
  remove:async id=>removed.push(id)
 },windows:{update:async(id,options)=>windowUpdates.push({id,...options})},scripting:{executeScript:async()=>[{result:results.shift() || {accounts:[]}}]}};
}
const options={attempts:3,pause:async()=>{}};
test('signed-in verification opens only in background, including while the bank page loads',async()=>{
 const chrome=browser([{accounts:[]},{accounts}]);
 const result=await openVerificationSession(chrome,draft,async()=>{},options);
 assert.equal(result.id,7);assert.deepEqual(chrome.calls,[{url:BANK_HOME,active:false}]);
 assert.deepEqual(chrome.updates,[]); assert.deepEqual(chrome.windowUpdates,[]);
});
test('sign-in is foregrounded once only when access is needed',async()=>{
 const chrome=browser([{accounts:[],loginRequired:true},{accounts:[],loginRequired:true},{accounts}]);
 const inspection=await openVerificationSession(chrome,draft,async()=>{},options);
 assert.equal(inspection.id,8,'sign-in tab is separate from disposable reader');
 assert.equal(chrome.calls.length,2);
 assert.deepEqual(chrome.removed,[]);
 assert.deepEqual(chrome.updates,[{id:7,active:true}]);
 assert.deepEqual(chrome.windowUpdates,[{id:3,focused:true}]);
});
test('automatic verification never changes focus when signed out',async()=>{
 const chrome=browser([{loginRequired:true}]);
 await assert.rejects(openVerificationSession(chrome,draft,async()=>{},{...options,interactive:false}),/Sign in/);
 assert.deepEqual(chrome.updates,[]);assert.deepEqual(chrome.removed,[7]);
});
test('wrong profile retains one sign-in tab and a retry reuses it',async()=>{
 const chrome=browser([{accounts:['Business Checking **3304 $100.00','Preferred Line **2829 $200.00']}]);
 await assert.rejects(openVerificationSession(chrome,draft,async()=>{},{...options,attempts:1}),/Sign-in or account access/);
 assert.deepEqual(chrome.removed,[]);
 chrome.scripting.executeScript=async()=>[{result:{accounts}}];
 await openVerificationSession(chrome,draft,async()=>{},{...options,tabId:7});
 assert.equal(chrome.calls.length,1);
});
test('slow page never steals focus and is cleaned up',async()=>{
 const chrome=browser([]);
 await assert.rejects(openVerificationSession(chrome,draft,async()=>{},options),/did not load/);
 assert.deepEqual(chrome.updates,[]);assert.deepEqual(chrome.removed,[7]);
});
test('closed history tab gives actionable error',async()=>{
 const chrome=browser([]);chrome.tabs.get=async()=>{throw new Error('gone')};
 await assert.rejects(openVerificationSession(chrome,draft,async()=>{},options),/tab was closed/);
});
test('return focuses original tab and its window without navigating or filling it',async()=>{
 const chrome=browser([]);
 await focusTransferTab(chrome,{tabId:42});
 assert.deepEqual(chrome.updates,[{id:42,active:true}]);assert.deepEqual(chrome.windowUpdates,[{id:3,focused:true}]);
 assert.equal(chrome.calls.length,0);
});
test('missing or repurposed original tab never creates a replacement transfer',async()=>{
 const chrome=browser([]);
 await assert.rejects(focusTransferTab(chrome,{}),/unavailable/);
 chrome.tabs.get=async()=>({id:42,url:'https://example.com/'});
 await assert.rejects(focusTransferTab(chrome,{tabId:42}),/unavailable/);
 assert.deepEqual(chrome.calls,[]);assert.deepEqual(chrome.updates,[]);
});

test('cleanup and navigation never affect a foreground bank tab or a transfer form',async()=>{
 const chrome=browser([]);
 for (const tab of [
   {id:7,url:BANK_HOME,active:true},
   {id:7,url:BANK_HOME+'/olb/transfers',active:false},
   {id:7,url:'https://example.com/',active:false}
 ]) {
   chrome.tabs.get=async()=>tab;
   await closeBackgroundHistoryTab(chrome,7);
   await assert.rejects(assertBackgroundHistoryTab(chrome,7),/left open/);
 }
 assert.deepEqual(chrome.removed,[]);
 chrome.tabs.get=async()=>({id:8,url:BANK_HOME+'/olb/history?accountId=D1',active:false});
 await assertBackgroundHistoryTab(chrome,8);
 await closeBackgroundHistoryTab(chrome,8);
 assert.deepEqual(chrome.removed,[8]);
});
