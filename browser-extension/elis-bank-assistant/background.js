import {allowedSender, validDraft, TRANSFERS} from './contract.js';
import {openAccount, findPostedEntry} from './history.js';
import {fillForm} from './fill-form.js';
let busy = false;
chrome.runtime.onMessageExternal.addListener((message,sender,reply)=>{
  if(!allowedSender(sender.url)) {reply({ok:false,error:'ELIS origin not allowed.'});return;}
  if(message?.type==='ELIS_PING') {reply({ok:true,version:'0.1.0'});return;}
  if(message?.type==='ELIS_ACK' && /^[a-f0-9-]{36}$/.test(message.id || '')) {
    chrome.storage.session.get('activeDraft').then(async ({activeDraft})=>{
      if(activeDraft?.id===message.id && activeDraft?.status==='matched') await chrome.storage.session.remove('activeDraft');
      reply({ok:true});
    }); return true;
  }
  if(!['ELIS_PREPARE','ELIS_VERIFY'].includes(message?.type)||!validDraft(message.draft)) {reply({ok:false,error:'Invalid reviewed transfer.'});return;}
  if(busy) {reply({ok:false,error:'Another form is being prepared.'});return;}
  busy=true;
  (async()=>{
    const existing=await chrome.storage.session.get('activeDraft');
    if(message.type==='ELIS_VERIFY') {
      if(!existing.activeDraft || existing.activeDraft.id!==message.draft.id || !existing.activeDraft.tabId)
        throw new Error('No active preparation for this draft.');
      const tabId=existing.activeDraft.tabId;
      const bankDate=existing.activeDraft.bankDate;
      if(!bankDate) throw new Error('Preparation date unavailable.');
      async function inspect(suffix,source) {
        await chrome.tabs.update(tabId,{url:'https://www.truliantfcuonline.org/dbank/live/app/home',active:true});
        let selected=false;
        for(let i=0;i<40;i++) {
          await new Promise(r=>setTimeout(r,300));
          const results=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:openAccount,args:[suffix]}).catch(()=>[]);
          if(results.some(r=>r.result===true)) {selected=true;break;}
        }
        if(!selected) throw new Error('Sign in or open the bank account to verify.');
        for(let i=0;i<40;i++) {
          await new Promise(r=>setTimeout(r,300));
          const results=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:findPostedEntry,args:[{suffix,source,amount_cents:message.draft.amount_cents,memo:message.draft.memo,bank_date:bankDate}]}).catch(()=>[]);
          const found=results.map(r=>r.result).find(Boolean);
          if(found?.match) return found.match;
          if(found?.error) throw new Error(found.error);
        }
        throw new Error('Bank history did not load.');
      }
      const destination=await inspect(message.draft.to_last4,false);
      const source=await inspect(message.draft.from_last4,true);
      await chrome.storage.session.set({activeDraft:{...existing.activeDraft,status:'matched'}});
      reply({ok:true,evidence:{source,destination}});
      return;
    }
    if(existing.activeDraft) throw new Error('A transfer is already awaiting review. Finish checking it before preparing another.');
    // Persist before opening/filling, including across service-worker restarts.
    await chrome.storage.session.set({activeDraft:{id:message.draft.id,status:'requested'}});
    const tab=await chrome.tabs.create({url:TRANSFERS,active:true});
    await chrome.storage.session.set({activeDraft:{id:message.draft.id,tabId:tab.id,status:'requested'}});
    const end=Date.now()+25000;
    while(Date.now()<end) {
      const current=await chrome.tabs.get(tab.id);
      if(current.status==='complete') break;
      await new Promise(r=>setTimeout(r,200));
    }
    const results=await chrome.scripting.executeScript({target:{tabId:tab.id},func:fillForm,args:[message.draft]});
    const result=results[0]?.result || {ok:false,error:'No preparation result. Inspect the bank tab.'};
    await chrome.storage.session.set({activeDraft:{id:message.draft.id,tabId:tab.id,status:result.ok?'prepared':'needs_review',bankDate:new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',year:'numeric'}).format(new Date())}});
    reply(result);
  })().catch(()=>reply({ok:false,error:'Preparation stopped. Inspect the bank tab; do not assume completion or retry blindly.'})).finally(()=>{busy=false;});
  return true;
});
