import test from 'node:test';
import assert from 'node:assert/strict';

const sender = {frameId:0,tab:{id:81},url:'http://127.0.0.1:18081/bank-monitor'};

test('balance check returns every account and posted debits for negative checking only', async t => {
  t.mock.method(globalThis,'setTimeout',(callback)=>{queueMicrotask(callback);return 1;});
  let external;
  const removed=[];
  globalThis.chrome={
    runtime:{
      id:'balance-extension',getManifest:()=>({version:'0.1.16'}),getURL:path=>`chrome-extension://balance-extension/${path}`,
      onMessageExternal:{addListener:listener=>{external=listener;}},
      onMessage:{addListener:()=>{},removeListener:()=>{}}
    },
    storage:{session:{get:async()=>({}),set:async()=>{},remove:async()=>{}}},
    tabs:{
      query:async()=>[{id:50,status:'complete'}],
      create:async()=>({id:100,status:'complete'}),
      get:async()=>({id:100,status:'complete'}),
      remove:async id=>{removed.push(id);},
      sendMessage:async(_id,message)=>message.type==='ELIS_OPEN_ACCOUNT' ? {opened:true} :
        message.type==='ELIS_LIST_POSTED_DEBITS' ? {ready:true,transactions:[{reference:'a'.repeat(64),date:'Sep 14, 2026',description:'Utility',amount_cents:11820,balance_cents:-96810}]} : null
    },
    scripting:{executeScript:async()=>[{result:[
      'Main Business Checking **3304 Current Balance -$968.10 Available Balance -$968.10',
      'Second Business Checking **1111 Current Balance $50.00 Available Balance $50.00',
      'Home Equity Line **3062 Current Balance $4,973.71 Available Credit $26.29',
      'Preferred Line of Credit **2829 Current Balance $311.25 Available Credit $4,688.75'
    ]}]}
  };
  await import('../background.js?balance-coverage');
  const response=await new Promise(resolve=>external({type:'ELIS_CHECK_BALANCES',suffixes:['3304','1111','3062','2829'],checking_suffixes:['3304','1111']},sender,resolve));
  assert.equal(response.ok,true);
  assert.deepEqual(response.accounts.map(account=>account.last4),['3304','1111','3062','2829']);
  assert.equal(response.accounts.find(account=>account.last4==='3062').available_credit_cents,2629);
  assert.deepEqual(response.coverage.map(item=>item.last4),['3304']);
  assert.equal(response.coverage[0].transactions[0].description,'Utility');
  assert.deepEqual(removed,[100]);
  delete globalThis.chrome;
});
