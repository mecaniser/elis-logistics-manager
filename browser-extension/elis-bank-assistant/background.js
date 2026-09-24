import {allowedSender, validDraft, boundDraft, parseAccountSummary, TRANSFERS} from './contract.js';
import {fillForm} from './fill-form.js';
import {startScheduledChromeRead} from './scheduled-check.js';
let busy = false;
const stageError = (code, message) => Object.assign(new Error(message), {code});
const scheduledAlarm = 'elis-bank-monitor-daily';
const scheduledCleanup = 'elis-bank-monitor-cleanup';
chrome.alarms?.create(scheduledAlarm, {periodInMinutes: 1});
chrome.alarms?.onAlarm.addListener(async alarm => {
  if (alarm.name === scheduledCleanup) {
    const {scheduledElisTabId} = await chrome.storage.session.get('scheduledElisTabId');
    if (scheduledElisTabId) await chrome.tabs.remove(scheduledElisTabId).catch(() => {});
    await chrome.storage.session.remove('scheduledElisTabId');
    return;
  }
  if (alarm.name !== scheduledAlarm) return;
  await startScheduledChromeRead(chrome);
});
chrome.runtime.onMessageExternal.addListener((message,sender,reply)=>{
  if(sender.id || sender.frameId !== 0 || !sender.tab?.id || !allowedSender(sender.url)) {reply({ok:false,error:'ELIS origin not allowed.'});return;}
  if(message?.type==='ELIS_PING') {reply({ok:true,version:chrome.runtime.getManifest().version});return;}
  if(message?.type==='ELIS_SCHEDULED_DONE') {
    chrome.storage.session.get('scheduledElisTabId').then(async ({scheduledElisTabId})=>{
      if (sender.tab.id === scheduledElisTabId) {
        await chrome.storage.session.remove('scheduledElisTabId');
        await chrome.alarms.clear(scheduledCleanup);
        await chrome.tabs.remove(scheduledElisTabId).catch(()=>{});
      }
      reply({ok:true});
    });
    return true;
  }
  if(message?.type==='ELIS_RELOAD') {
    if(busy) {reply({ok:false,error:'The bank assistant is busy.'});return;}
    reply({ok:true,version:chrome.runtime.getManifest().version});
    setTimeout(()=>chrome.runtime.reload(),100);
    return;
  }
  if(message?.type==='ELIS_DISCOVER_ACCOUNTS') {
    if(busy) {reply({ok:false,error:'The bank assistant is busy.'});return;}
    busy=true;
    (async()=>{
      const open=await chrome.tabs.query({url:'https://www.truliantfcuonline.org/*'});
      const tab=open.find(item=>item.status==='complete' && /\/dbank\/live\/app\/home\/?$/.test(item.url || '')) || await chrome.tabs.create({url:'https://www.truliantfcuonline.org/dbank/live/app/home',active:true});
      for(let attempt=0;attempt<50;attempt++) {
        await new Promise(resolve=>setTimeout(resolve,300));
        const results=await chrome.scripting.executeScript({target:{tabId:tab.id,allFrames:true},func:()=>
          [...document.querySelectorAll('[id^="account-link-"]')].map(element=>(element.textContent||'').replace(/\s+/g,' ').trim())}).catch(()=>[]);
        const accounts=[...new Map(results.flatMap(result=>result.result||[]).map(parseAccountSummary).filter(Boolean)
          .map(account=>[account.last4,{nickname:account.nickname,last4:account.last4,kind:account.kind}])).values()];
        if(accounts.length) {reply({ok:true,accounts});return;}
      }
      reply({ok:false,error:'Open and sign in to Truliant, then try account import again.'});
    })().catch(()=>reply({ok:false,error:'Account import stopped. No bank information was changed.'})).finally(()=>{busy=false;});
    return true;
  }
  if(message?.type==='ELIS_CHECK_BALANCES') {
    const suffixes=message.suffixes;
    const checkingSuffixes=message.checking_suffixes;
    const includePending=message.include_pending === true;
    if(!Array.isArray(suffixes) || suffixes.length<1 || suffixes.length>15 || suffixes.some(value=>!/^\d{4}$/.test(value)) ||
       !Array.isArray(checkingSuffixes) || checkingSuffixes.some(value=>!/^\d{4}$/.test(value) || !suffixes.includes(value))) {reply({ok:false,error:'Configured accounts are invalid.'});return;}
    if(busy) {reply({ok:false,error:'The bank assistant is busy.'});return;}
    busy=true;
    (async()=>{
      const open=await chrome.tabs.query({url:'https://www.truliantfcuonline.org/*'});
      const tab=open.find(item=>item.status==='complete' && /\/dbank\/live\/app\/home\/?$/.test(item.url || '')) || await chrome.tabs.create({url:'https://www.truliantfcuonline.org/dbank/live/app/home',active:true});
      for(let attempt=0;attempt<50;attempt++) {
        await new Promise(resolve=>setTimeout(resolve,300));
        const results=await chrome.scripting.executeScript({target:{tabId:tab.id,allFrames:true},func:()=>
          [...document.querySelectorAll('[id^="account-link-"]')].map(element=>(element.textContent||'').replace(/\s+/g,' ').trim())}).catch(()=>[]);
        const summaries=results.flatMap(result=>result.result||[]).map(parseAccountSummary).filter(Boolean)
          .filter(account=>suffixes.includes(account.last4));
        const accounts=[...new Map(summaries.map(account=>[account.last4,account])).values()];
        if(accounts.length===suffixes.length) {
          const coverage=[];
          const checking=accounts.filter(account=>checkingSuffixes.includes(account.last4));
          for(const account of checking) {
            const inspection=await chrome.tabs.create({url:'https://www.truliantfcuonline.org/dbank/live/app/home',active:false});
            try {
              const navigationEnd=Date.now()+25000;
              while(Date.now()<navigationEnd) {
                const current=await chrome.tabs.get(inspection.id);
                if(current.status==='complete') break;
                await new Promise(resolve=>setTimeout(resolve,200));
              }
              let selected=false;
              for(let i=0;i<60;i++) {
                await new Promise(resolve=>setTimeout(resolve,300));
                const result=await chrome.tabs.sendMessage(inspection.id,{type:'ELIS_OPEN_ACCOUNT',suffix:account.last4}).catch(()=>null);
                if(result?.opened) {selected=true;break;}
              }
              if(!selected) {coverage.push({last4:account.last4,transactions:[],error:`Could not open checking account ••${account.last4}.`});continue;}
              let history=null;
              for(let i=0;i<50;i++) {
                await new Promise(resolve=>setTimeout(resolve,300));
                history=await chrome.tabs.sendMessage(inspection.id,{type:'ELIS_LIST_COVERAGE_DEBITS',suffix:account.last4,include_pending:includePending}).catch(()=>null);
                if(history?.ready) break;
              }
              coverage.push({last4:account.last4,transactions:history?.transactions || [],overdraft_detected:history?.overdraft_detected === true,error:history?.error || (history?.ready ? null : 'Account history did not load.')});
            } finally { await chrome.tabs.remove(inspection.id).catch(()=>{}); }
          }
          reply({ok:true,checked_at:new Date().toISOString(),accounts,coverage});return;
        }
      }
      reply({ok:false,error:'Could not read every configured account. Open the signed-in Truliant home page and try again.'});
    })().catch(()=>reply({ok:false,error:'Balance check stopped. No bank information was changed.'})).finally(()=>{busy=false;});
    return true;
  }
  if(message?.type==='ELIS_STATUS' && /^[a-f0-9-]{36}$/.test(message.id || '')) {
    chrome.storage.session.get('activeDraft').then(({activeDraft})=>{
      const allowed=activeDraft?.id===message.id && activeDraft.origin===new URL(sender.url).origin && activeDraft.elisTabId===sender.tab.id;
      reply({ok:true,progress:allowed ? activeDraft.progress || null : null});
    }); return true;
  }
  if(message?.type==='ELIS_ACK' && /^[a-f0-9-]{36}$/.test(message.id || '')) {
    chrome.storage.session.get('activeDraft').then(async ({activeDraft})=>{
      if(activeDraft?.id===message.id && activeDraft?.status==='matched' && activeDraft.origin===new URL(sender.url).origin && activeDraft.elisTabId===sender.tab.id) await chrome.storage.session.remove('activeDraft');
      reply({ok:true});
    }); return true;
  }
  if(!['ELIS_PREPARE','ELIS_VERIFY','ELIS_REAUTHORIZE_VERIFY'].includes(message?.type)||!validDraft(message.draft)) {reply({ok:false,error:'Invalid reviewed transfer.'});return;}
  if(busy) {reply({ok:false,error:'Another form is being prepared.'});return;}
  busy=true;
  const finishReply = value => { busy=false; reply(value); };
  (async()=>{
    const existing=await chrome.storage.session.get('activeDraft');
    if(message.type==='ELIS_REAUTHORIZE_VERIFY') {
      if(existing.activeDraft) throw new Error('An active transfer review already exists.');
      if(!/^\d{4}-\d{2}-\d{2}$/.test(message.draft.bank_date || '')) throw new Error('Preparation date unavailable.');
      await approvePreparation(message.draft,'verify');
      const bankDate=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',year:'numeric'}).format(new Date(`${message.draft.bank_date}T12:00:00Z`));
      await chrome.storage.session.set({activeDraft:{id:message.draft.id,draft:message.draft,origin:new URL(sender.url).origin,elisTabId:sender.tab.id,status:'prepared',bankDate}});
      finishReply({ok:true}); return;
    }
    if(message.type==='ELIS_VERIFY') {
      if(!existing.activeDraft) {finishReply({ok:false,code:'VERIFICATION_REAUTH_REQUIRED',error:'No active preparation for this draft.'});return;}
      if(!boundDraft(existing.activeDraft,message.draft,sender))
        throw new Error('No active preparation for this draft.');
      const bankDate=existing.activeDraft.bankDate;
      if(!bankDate) throw new Error('Preparation date unavailable.');
      const progress = async (stage, message) => chrome.storage.session.set({activeDraft:{...existing.activeDraft,status:'prepared',progress:{stage,message,at:Date.now()}}});
      async function inspect(suffix,source) {
        await progress(source ? 'opening_source' : 'opening_checking', `Opening ${source ? 'funding source' : 'checking account'} ••${suffix} in Truliant…`);
        const inspection=await chrome.tabs.create({url:'https://www.truliantfcuonline.org/dbank/live/app/home',active:false});
        try {
          const navigationEnd=Date.now()+25000;
          while(Date.now()<navigationEnd) {
            const current=await chrome.tabs.get(inspection.id);
            if(current.status==='complete') break;
            await new Promise(r=>setTimeout(r,200));
          }
          let selected=false;
          for(let i=0;i<60;i++) {
            await new Promise(r=>setTimeout(r,500));
            const result=await chrome.tabs.sendMessage(inspection.id,{type:'ELIS_OPEN_ACCOUNT',suffix}).catch(()=>null);
            if(result?.opened) {selected=true;break;}
          }
          const repayment = message.draft.kind === 'repayment';
          const accountRole = repayment ? (source ? 'checking account' : 'credit account') : (source ? 'funding source' : 'checking account');
          if(!selected) throw stageError(
            source ? 'SOURCE_ACCOUNT_NOT_FOUND' : 'DESTINATION_ACCOUNT_NOT_FOUND',
            `Could not open ${accountRole} ••${suffix}. Sign in to Truliant in this Chrome profile and confirm the account is visible.`
          );
          const entryRole = repayment ? (source ? 'repayment debits' : 'credit payments') : (source ? 'principal disbursements' : 'deposits');
          await progress(source ? 'searching_source' : 'searching_checking', `Searching posted ${entryRole} in account ••${suffix}…`);
          for(let i=0;i<40;i++) {
            await new Promise(r=>setTimeout(r,300));
            const found=await chrome.tabs.sendMessage(inspection.id,{type:'ELIS_FIND_POSTED',wanted:{suffix,source,kind:message.draft.kind,amount_cents:message.draft.amount_cents,memo:message.draft.memo,bank_date:bankDate}}).catch(()=>null);
            if(found?.match) return found.match;
            if(found?.error) throw stageError(source ? 'SOURCE_HISTORY_NO_MATCH' : 'DESTINATION_HISTORY_NO_MATCH', found.error);
          }
          throw stageError(source ? 'SOURCE_HISTORY_NOT_LOADED' : 'DESTINATION_HISTORY_NOT_LOADED',
            `${source ? 'Funding source' : 'Checking account'} history did not load.`);
        } finally {
          await chrome.tabs.remove(inspection.id).catch(()=>{});
        }
      }
      const destination=await inspect(message.draft.to_last4,false);
      await progress('destination_matched', `Destination account ••${message.draft.to_last4} matched. Opening source account ••${message.draft.from_last4}…`);
      const source=await inspect(message.draft.from_last4,true);
      await chrome.storage.session.set({activeDraft:{...existing.activeDraft,status:'matched',progress:{stage:'matched',message:'Both posted bank entries matched. Saving verification in ELIS…',at:Date.now()}}});
      finishReply({ok:true,evidence:{source,destination}});
      return;
    }
    if(existing.activeDraft) throw new Error('A transfer is already awaiting review. Finish checking it before preparing another.');
    try {
    await approvePreparation(message.draft,'prepare');
    } catch (error) {
      // This branch is before activeDraft persistence, bank-tab creation and
      // scripting. Never classify a later error as safe to retry.
      if (error?.code !== 'APPROVAL_NOT_GRANTED') throw error;
      finishReply({ok:false,code:'PREPARATION_NOT_STARTED',error:'Preparation approval expired or was canceled. No bank form was opened. You can prepare this draft again.'});
      return;
    }
    // Persist before opening/filling, including across service-worker restarts.
    await chrome.storage.session.set({activeDraft:{id:message.draft.id,draft:message.draft,origin:new URL(sender.url).origin,elisTabId:sender.tab.id,status:'requested'}});
    const tab=await chrome.tabs.create({url:TRANSFERS,active:true});
    await chrome.storage.session.set({activeDraft:{id:message.draft.id,draft:message.draft,origin:new URL(sender.url).origin,elisTabId:sender.tab.id,tabId:tab.id,status:'requested'}});
    const end=Date.now()+25000;
    while(Date.now()<end) {
      const current=await chrome.tabs.get(tab.id);
      if(current.status==='complete') break;
      await new Promise(r=>setTimeout(r,200));
    }
    const results=await chrome.scripting.executeScript({target:{tabId:tab.id},func:fillForm,args:[message.draft]});
    const result=results[0]?.result || {ok:false,error:'No preparation result. Inspect the bank tab.'};
    if(result.code==='LOGIN_REQUIRED') {
      await chrome.storage.session.remove('activeDraft');
      finishReply({ok:false,code:'PREPARATION_NOT_STARTED',error:result.error});
      return;
    }
    await chrome.storage.session.set({activeDraft:{id:message.draft.id,draft:message.draft,origin:new URL(sender.url).origin,elisTabId:sender.tab.id,tabId:tab.id,status:result.ok?'prepared':'needs_review',bankDate:new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',year:'numeric'}).format(new Date())}});
    finishReply(result);
  })().catch(error=>{
    const safeCodes = new Set([
      'SOURCE_ACCOUNT_NOT_FOUND', 'DESTINATION_ACCOUNT_NOT_FOUND',
      'SOURCE_HISTORY_NO_MATCH', 'DESTINATION_HISTORY_NO_MATCH',
      'SOURCE_HISTORY_NOT_LOADED', 'DESTINATION_HISTORY_NOT_LOADED'
    ]);
    const safeMessages = new Set(['No active preparation for this draft.', 'Preparation date unavailable.']);
    const safe = safeCodes.has(error?.code) || safeMessages.has(error?.message);
    finishReply({ok:false,code:safe ? error?.code : undefined,error:safe ? error.message : 'Preparation stopped. Inspect the bank tab; do not assume completion or retry blindly.'});
  }).finally(()=>{busy=false;});
  return true;
});


// A compromised ELIS page cannot authorize preparation by itself. Approval is
// rendered on an extension-owned page, never in web-page HTML.
async function approvePreparation(draft,mode) {
  const nonce = crypto.randomUUID();
  const expires_at=Date.now()+120000;
  await chrome.storage.session.set({approval:{nonce,draft,mode,expires_at}});
  const popup=await chrome.windows.create({url:chrome.runtime.getURL('approve.html'),type:'popup',focused:true,width:520,height:650});
  const [tab]=popup.tabs?.length ? popup.tabs : await chrome.tabs.query({windowId:popup.id});
  if(!tab?.id) throw new Error('Approval window could not be opened.');
  try {
    await new Promise((resolve,reject)=>{
      const timeout=setTimeout(()=>finish(false),120000);
      function finish(approved) {
        clearTimeout(timeout); chrome.runtime.onMessage.removeListener(listener); chrome.windows.onRemoved.removeListener(closed);
        approved ? resolve() : reject(Object.assign(new Error('Preparation approval declined or expired.'), {code:'APPROVAL_NOT_GRANTED'}));
      }
      function closed(windowId) { if(windowId===popup.id) finish(false); }
      function listener(message,sender,reply) {
        if(sender.id!==chrome.runtime.id || sender.tab?.id!==tab.id || sender.url!==chrome.runtime.getURL('approve.html') || message?.nonce!==nonce) return;
        if(!['approve','cancel'].includes(message.action)) return;
        reply({ok:true}); finish(message.action==='approve');
      }
      chrome.runtime.onMessage.addListener(listener); chrome.windows.onRemoved.addListener(closed);
    });
  } finally { await chrome.storage.session.remove('approval'); await chrome.windows.remove(popup.id).catch(()=>{}); }
}
