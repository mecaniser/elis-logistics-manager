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
  const updatedTabs = [];
  const focusedWindows = [];
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
      update:async(id,options)=>focusedWindows.push({id,...options}),
      onRemoved:{addListener(){},removeListener(){}}
    },
    tabs:{
      create:async options=>{createdTabs.push(options);const tab={id:nextTab++, status:'complete', url:options.url};tabs.set(tab.id,tab);return tab;},
      get:async id=>tabs.get(id),
      update:async(id,options)=>{updatedTabs.push({id,...options});Object.assign(tabs.get(id),options);return tabs.get(id);},
      remove:async id=>{removed.push(id);tabs.delete(id);},
      sendMessage:async (id,message)=>{
        let inspection = inspections.at(-1);
        if(message.type==='ELIS_OPEN_ACCOUNT' && inspection?.suffix!==message.suffix) {inspection={tabId:id};inspections.push(inspection);}
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
    scripting:{executeScript:async options=>{assert.match(String(options.func),/querySelectorAll/); assert.doesNotMatch(String(options.func),/\.click\(|\.value\s*=/); return [{result:{accounts:['Business Checking **3304 $100.00','Preferred Line **2829 $200.00']}}];}}
  };
  return {
    get external(){return external;}, get approval(){return approval;}, get approvalListener(){return approvalListener;},
    session, inspections, removed, removedWindows, createdTabs, updatedTabs, focusedWindows, tabs
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

  harness.tabs.set(42,{id:42,url:'https://www.truliantfcuonline.org/dbank/live/app/home/olb/transfers',windowId:9});
  harness.session.activeDraft={id:draft.id,draft,origin:new URL(sender.url).origin,elisTabId:81,tabId:42};
  const reauthorization=call(harness.external,{type:'ELIS_REAUTHORIZE_VERIFY',draft});
  await waitForApproval(harness);
  approve(harness);
  assert.deepEqual(await reauthorization,{ok:true});
  assert.equal(harness.session.activeDraft.tabId,42,'reauthorization preserves the transfer tab');
  assert.deepEqual(await call(harness.external,{type:'ELIS_STATUS',id:draft.id}),{ok:true,progress:null});

  const verified=await call(harness.external,{type:'ELIS_VERIFY',draft,interactive:true});
  assert.deepEqual(verified,{ok:true,evidence:{source:'a'.repeat(64),destination:'b'.repeat(64)}});
  assert.deepEqual(harness.inspections.map(item=>[item.suffix,item.wanted.source,item.wanted.bank_date]),[
    ['3304',false,'Sep 14, 2026'], ['2829',true,'Sep 14, 2026']
  ]);
  assert.equal(harness.updatedTabs.length,1);
  assert.equal(harness.updatedTabs[0].id,harness.inspections[0].tabId);
  assert.equal(harness.updatedTabs[0].active,undefined,'signed-in checks never request focus');
  assert.equal(harness.tabs.has(42),true,'original form is preserved');
  assert.equal(harness.session.activeDraft.tabId,42);
  assert.equal(harness.session.activeDraft.status,'matched');
  assert.equal(harness.session.activeDraft.progress.stage,'matched');
  assert.equal(harness.inspections.every(item=>item.wanted.amount_cents===11820 && item.wanted.memo===draft.memo),true);

  assert.deepEqual(await call(harness.external,{type:'ELIS_ACK',id:draft.id}),{ok:true});
  assert.equal(harness.session.activeDraft,undefined);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(harness.removed.length,1,'one temporary history tab serves both accounts and is closed');
  assert.equal(harness.createdTabs.length,1);
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

 test('return action requires the exact draft and original ELIS tab binding',async()=>{
  const harness=installChrome();
  await import('../background.js?return-binding');
  harness.session.activeDraft={id:draft.id,draft,origin:'http://127.0.0.1:18081',elisTabId:81,tabId:999};
  for(const changed of [{...draft,amount_cents:1},{...draft,memo:'Cvr Changed'}]) {
    const result=await call(harness.external,{type:'ELIS_RETURN_TO_TRANSFER',draft:changed});
    assert.equal(result.ok,false);assert.match(result.error,/not linked/);
  }
  const result=await new Promise(resolve=>harness.external({type:'ELIS_RETURN_TO_TRANSFER',draft},{...sender,tab:{id:82}},resolve));
  assert.equal(result.ok,false);assert.equal(harness.createdTabs.length,0);
  delete globalThis.chrome;
 });

 test('return action focuses the bound original form without creating or navigating a tab',async()=>{
  const harness=installChrome();
  await import('../background.js?return-success');
  harness.tabs.set(42,{id:42,url:'https://www.truliantfcuonline.org/dbank/live/app/home/olb/transfers',windowId:9});
  harness.session.activeDraft={id:draft.id,draft,origin:new URL(sender.url).origin,elisTabId:81,tabId:42};
  assert.deepEqual(await call(harness.external,{type:'ELIS_RETURN_TO_TRANSFER',draft}),{ok:true});
  assert.deepEqual(harness.updatedTabs,[{id:42,active:true}]);
  assert.deepEqual(harness.focusedWindows,[{id:9,focused:true}]);
  assert.equal(harness.createdTabs.length,0);
  delete globalThis.chrome;
 });
