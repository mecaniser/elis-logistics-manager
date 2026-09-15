import test from 'node:test';
import assert from 'node:assert/strict';

const draft = {
  id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', amount_cents:11820,
  from_last4:'2829', to_last4:'3304', memo:'Cvr Union County utilities 0914',
  bank_date:'2026-09-14'
};
const sender = {frameId:0, tab:{id:81}, url:'http://127.0.0.1:18081/bank-monitor'};

function installChrome({findSource=true, findDestination=true, openSource=true, openDestination=true}={}) {
  let external;
  let approvalListener;
  let approval;
  let nextTab = 100;
  const tabs = new Map();
  const removed = [];
  const removedWindows = [];
  const inspections = [];
  const createdTabs = [];
  const session = {};
  globalThis.chrome = {
    runtime:{
      id:'acceptance-extension',
      getURL:path=>`chrome-extension://acceptance-extension/${path}`,
      getManifest:()=>({version:'acceptance'}),
      onMessageExternal:{addListener:listener=>{external=listener;}},
      onMessage:{
        addListener:listener=>{approvalListener=listener;},
        removeListener:listener=>{if(approvalListener===listener) approvalListener=undefined;}
      }
    },
    storage:{session:{
      get:async key=>({[key]:session[key]}),
      set:async values=>{Object.assign(session, values); if(values.approval) approval=values.approval;},
      remove:async key=>{delete session[key];}
    }},
    windows:{
      create:async options=>{const tab={id:nextTab++,status:'complete',url:options.url};tabs.set(tab.id,tab);return {id:500,tabs:[tab]};},
      remove:async id=>{removedWindows.push(id);},
      onRemoved:{addListener(){},removeListener(){}}
    },
    tabs:{
      create:async options=>{createdTabs.push(options);const tab={id:nextTab++, status:'complete', url:options.url};tabs.set(tab.id,tab);return tab;},
      get:async id=>tabs.get(id),
      remove:async id=>{removed.push(id);tabs.delete(id);},
      sendMessage:async (id,message)=>{
        const inspection = inspections.find(item=>item.tabId===id) || {tabId:id};
        if(!inspections.includes(inspection)) inspections.push(inspection);
        if(message.type==='ELIS_OPEN_ACCOUNT') {
          inspection.suffix=message.suffix;
          const opened=message.suffix==='3304' ? openDestination : openSource;
          return {ready:true,opened};
        }
        if(message.type==='ELIS_FIND_POSTED') {
          inspection.wanted=message.wanted;
          const found=message.wanted.source ? findSource : findDestination;
          return found ? {ready:true,match:(message.wanted.source?'a':'b').repeat(64)} :
            {ready:true,error:'No unique posted match found. It may not have posted yet.'};
        }
      }
    },
    scripting:{executeScript:async()=>assert.fail('Read-only verification must never script or submit a transfer form.')}
  };
  return {
    get external(){return external;}, get approval(){return approval;}, get approvalListener(){return approvalListener;},
    session, inspections, removed, removedWindows, createdTabs
  };
}

const call = (listener, message) => new Promise(resolve=>listener(message,sender,resolve));
async function waitForApproval(harness) {
  for(let attempt=0;attempt<20 && !harness.approvalListener;attempt++) await new Promise(resolve=>setImmediate(resolve));
  assert.equal(typeof harness.approvalListener,'function','extension approval listener became ready');
}
const approve = harness => harness.approvalListener(
  {action:'approve',nonce:harness.approval.nonce},
  {id:'acceptance-extension',tab:{id:100},url:'chrome-extension://acceptance-extension/approve.html'},
  ()=>{}
);

test('full reauthorization and two-account verification flow returns separate evidence and clears only after ELIS acknowledgement', async t => {
  t.mock.method(globalThis, 'setTimeout', (callback, delay)=>{if(delay!==120000) queueMicrotask(callback);return 1;});
  const harness=installChrome();
  await import('../background.js?acceptance-success');

  const reauthorization=call(harness.external,{type:'ELIS_REAUTHORIZE_VERIFY',draft});
  await waitForApproval(harness);
  approve(harness);
  assert.deepEqual(await reauthorization,{ok:true});
  assert.deepEqual(await call(harness.external,{type:'ELIS_STATUS',id:draft.id}),{ok:true,progress:null});

  const verified=await call(harness.external,{type:'ELIS_VERIFY',draft});
  assert.deepEqual(verified,{ok:true,evidence:{source:'a'.repeat(64),destination:'b'.repeat(64)}});
  assert.deepEqual(harness.inspections.map(item=>[item.suffix,item.wanted.source,item.wanted.bank_date]),[
    ['3304',false,'Sep 14, 2026'], ['2829',true,'Sep 14, 2026']
  ]);
  assert.equal(harness.session.activeDraft.status,'matched');
  assert.equal(harness.session.activeDraft.progress.stage,'matched');
  assert.equal(harness.inspections.every(item=>item.wanted.amount_cents===11820 && item.wanted.memo===draft.memo),true);

  assert.deepEqual(await call(harness.external,{type:'ELIS_ACK',id:draft.id}),{ok:true});
  assert.equal(harness.session.activeDraft,undefined);
  assert.equal(harness.removed.length,2,'both temporary history tabs are closed');
  assert.equal(harness.createdTabs.every(options=>options.active===false),true,'history verification stays in background tabs');
  assert.deepEqual(harness.removedWindows,[500],'the approval popup is closed');
  delete globalThis.chrome;
});

test('destination account failure stops before source inspection and reports the exact stage', async t => {
  t.mock.method(globalThis, 'setTimeout', (callback, delay)=>{if(delay!==120000) queueMicrotask(callback);return 1;});
  const harness=installChrome({openDestination:false});
  await import('../background.js?acceptance-destination-failure');
  const reauthorization=call(harness.external,{type:'ELIS_REAUTHORIZE_VERIFY',draft});
  await waitForApproval(harness); approve(harness); await reauthorization;
  const result=await call(harness.external,{type:'ELIS_VERIFY',draft});
  assert.equal(result.ok,false);
  assert.equal(result.code,'DESTINATION_ACCOUNT_NOT_FOUND');
  assert.match(result.error,/checking account ••3304/);
  assert.deepEqual(harness.inspections.map(item=>item.suffix),['3304']);
  assert.equal(harness.session.activeDraft.status,'prepared');
  delete globalThis.chrome;
});

test('source posted-entry failure preserves the draft and reports that checking already passed', async t => {
  t.mock.method(globalThis, 'setTimeout', (callback, delay)=>{if(delay!==120000) queueMicrotask(callback);return 1;});
  const harness=installChrome({findSource:false});
  await import('../background.js?acceptance-source-failure');
  const reauthorization=call(harness.external,{type:'ELIS_REAUTHORIZE_VERIFY',draft});
  await waitForApproval(harness); approve(harness); await reauthorization;
  const result=await call(harness.external,{type:'ELIS_VERIFY',draft});
  assert.equal(result.ok,false);
  assert.equal(result.code,'SOURCE_HISTORY_NO_MATCH');
  assert.match(result.error,/not have posted yet/);
  assert.deepEqual(harness.inspections.map(item=>item.suffix),['3304','2829']);
  assert.equal(harness.session.activeDraft.status,'prepared');
  delete globalThis.chrome;
});
