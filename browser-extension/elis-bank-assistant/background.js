import {allowedSender, validDraft, boundDraft, TRANSFERS} from './contract.js';
import {fillForm} from './fill-form.js';
let busy = false;
chrome.runtime.onMessageExternal.addListener((message,sender,reply)=>{
  if(sender.id || sender.frameId !== 0 || !sender.tab?.id || !allowedSender(sender.url)) {reply({ok:false,error:'ELIS origin not allowed.'});return;}
  if(message?.type==='ELIS_PING') {reply({ok:true,version:chrome.runtime.getManifest().version});return;}
  if(message?.type==='ELIS_ACK' && /^[a-f0-9-]{36}$/.test(message.id || '')) {
    chrome.storage.session.get('activeDraft').then(async ({activeDraft})=>{
      if(activeDraft?.id===message.id && activeDraft?.status==='matched' && activeDraft.origin===new URL(sender.url).origin && activeDraft.elisTabId===sender.tab.id) await chrome.storage.session.remove('activeDraft');
      reply({ok:true});
    }); return true;
  }
  if(!['ELIS_PREPARE','ELIS_VERIFY','ELIS_REAUTHORIZE_VERIFY'].includes(message?.type)||!validDraft(message.draft)) {reply({ok:false,error:'Invalid reviewed transfer.'});return;}
  if(busy) {reply({ok:false,error:'Another form is being prepared.'});return;}
  busy=true;
  (async()=>{
    const existing=await chrome.storage.session.get('activeDraft');
    if(message.type==='ELIS_REAUTHORIZE_VERIFY') {
      if(existing.activeDraft) throw new Error('An active transfer review already exists.');
      if(!/^\d{4}-\d{2}-\d{2}$/.test(message.draft.bank_date || '')) throw new Error('Preparation date unavailable.');
      await approvePreparation(message.draft,'verify');
      const bankDate=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',year:'numeric'}).format(new Date(`${message.draft.bank_date}T12:00:00Z`));
      await chrome.storage.session.set({activeDraft:{id:message.draft.id,draft:message.draft,origin:new URL(sender.url).origin,elisTabId:sender.tab.id,status:'prepared',bankDate}});
      reply({ok:true}); return;
    }
    if(message.type==='ELIS_VERIFY') {
      if(!existing.activeDraft) {reply({ok:false,code:'VERIFICATION_REAUTH_REQUIRED',error:'No active preparation for this draft.'});return;}
      if(!boundDraft(existing.activeDraft,message.draft,sender))
        throw new Error('No active preparation for this draft.');
      const bankDate=existing.activeDraft.bankDate;
      if(!bankDate) throw new Error('Preparation date unavailable.');
      async function inspect(suffix,source) {
        const inspection=await chrome.tabs.create({url:'https://www.truliantfcuonline.org/dbank/live/app/home',active:true});
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
          if(!selected) throw new Error(`Open account ••${suffix} failed. Sign in to Truliant in this Chrome profile.`);
          for(let i=0;i<40;i++) {
            await new Promise(r=>setTimeout(r,300));
            const found=await chrome.tabs.sendMessage(inspection.id,{type:'ELIS_FIND_POSTED',wanted:{suffix,source,amount_cents:message.draft.amount_cents,memo:message.draft.memo,bank_date:bankDate}}).catch(()=>null);
            if(found?.match) return found.match;
            if(found?.error) throw new Error(found.error);
          }
          throw new Error('Bank history did not load.');
        } finally {
          await chrome.tabs.remove(inspection.id).catch(()=>{});
        }
      }
      const destination=await inspect(message.draft.to_last4,false);
      const source=await inspect(message.draft.from_last4,true);
      await chrome.storage.session.set({activeDraft:{...existing.activeDraft,status:'matched'}});
      reply({ok:true,evidence:{source,destination}});
      return;
    }
    if(existing.activeDraft) throw new Error('A transfer is already awaiting review. Finish checking it before preparing another.');
    try {
    await approvePreparation(message.draft,'prepare');
    } catch (error) {
      // This branch is before activeDraft persistence, bank-tab creation and
      // scripting. Never classify a later error as safe to retry.
      if (error?.code !== 'APPROVAL_NOT_GRANTED') throw error;
      reply({ok:false,code:'PREPARATION_NOT_STARTED',error:'Preparation approval expired or was canceled. No bank form was opened. You can prepare this draft again.'});
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
    await chrome.storage.session.set({activeDraft:{id:message.draft.id,draft:message.draft,origin:new URL(sender.url).origin,elisTabId:sender.tab.id,tabId:tab.id,status:result.ok?'prepared':'needs_review',bankDate:new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',year:'numeric'}).format(new Date())}});
    reply(result);
  })().catch(error=>{
    const safe = new Set([
      'No active preparation for this draft.',
      'Preparation date unavailable.',
      'Open account ••3304 failed. Sign in to Truliant in this Chrome profile.',
      'Open account ••2829 failed. Sign in to Truliant in this Chrome profile.',
      'Account identity could not be verified.',
      'No unique posted match found. It may not have posted yet.',
      'Multiple matching entries require review.',
      'Bank history did not load.'
    ]);
    reply({ok:false,error:safe.has(error?.message) ? error.message : 'Preparation stopped. Inspect the bank tab; do not assume completion or retry blindly.'});
  }).finally(()=>{busy=false;});
  return true;
});


// A compromised ELIS page cannot authorize preparation by itself. Approval is
// rendered on an extension-owned page, never in web-page HTML.
async function approvePreparation(draft,mode) {
  const nonce = crypto.randomUUID();
  await chrome.storage.session.set({approval:{nonce,draft,mode}});
  const tab = await chrome.tabs.create({url:chrome.runtime.getURL('approve.html'),active:true});
  try {
    await new Promise((resolve,reject)=>{
      const timeout=setTimeout(()=>finish(false),120000);
      function finish(approved) {
        clearTimeout(timeout); chrome.runtime.onMessage.removeListener(listener);
        approved ? resolve() : reject(Object.assign(new Error('Preparation approval declined or expired.'), {code:'APPROVAL_NOT_GRANTED'}));
      }
      function listener(message,sender,reply) {
        if(sender.id!==chrome.runtime.id || sender.tab?.id!==tab.id || sender.url!==chrome.runtime.getURL('approve.html') || message?.nonce!==nonce) return;
        if(!['approve','cancel'].includes(message.action)) return;
        reply({ok:true}); finish(message.action==='approve');
      }
      chrome.runtime.onMessage.addListener(listener);
    });
  } finally { await chrome.storage.session.remove('approval'); await chrome.tabs.remove(tab.id).catch(()=>{}); }
}
