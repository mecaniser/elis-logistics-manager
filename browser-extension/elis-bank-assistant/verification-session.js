import {parseAccountSummary} from './contract.js';

// Manual verification starts visibly and waits for the user to authenticate.
// This only inspects account links; it never opens or fills a transfer form.
export async function openVerificationSession(chrome, draft, progress, {attempts=360, pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))}={}) {
  const tab=await chrome.tabs.create({url:'https://www.truliantfcuonline.org/dbank/live/app/home',active:true});
  const profile=draft.bank_session?.profile_name || 'the required bank profile';
  await progress('awaiting_sign_in', `Sign in to ${profile} in the new Truliant tab. Waiting for accounts ••${draft.from_last4} and ••${draft.to_last4}…`);
  for(let i=0;i<attempts;i++) {
    await pause(500);
    try { await chrome.tabs.get(tab.id); }
    catch { throw new Error('The Truliant sign-in tab was closed. Select Check completion to start again.'); }
    const results=await chrome.scripting.executeScript({target:{tabId:tab.id,allFrames:true},func:()=>
      [...document.querySelectorAll('[id^="account-link-"]')].map(element=>(element.textContent||'').replace(/\s+/g,' ').trim())}).catch(()=>[]);
    const suffixes=results.flatMap(result=>result.result || []).map(parseAccountSummary).filter(Boolean).map(account=>account.last4);
    if(suffixes.includes(draft.from_last4) && suffixes.includes(draft.to_last4)) return tab;
  }
  throw new Error(`Sign-in or account access is still needed for ${profile}. Keep the Truliant tab open, sign in, then select Check completion again. Nothing was submitted.`);
}
