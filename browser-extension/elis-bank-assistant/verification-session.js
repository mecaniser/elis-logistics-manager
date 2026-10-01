import {BANK, parseAccountSummary} from './contract.js';

export const BANK_HOME = `${BANK}/dbank/live/app/home`;

// Keep the transfer form untouched. Only a confirmed sign-in/account-access
// problem may bring this separate, read-only tab into the foreground.
export async function openVerificationSession(chrome, draft, progress, {
  attempts=360, pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),
  interactive=true, tabId, onTab=async()=>{}
}={}) {
  let tab = tabId ? await chrome.tabs.get(tabId).catch(()=>null) : null;
  if (tab && !String(tab.url || '').startsWith(`${BANK}/`)) tab = null;
  if (!tab) tab=await chrome.tabs.create({url:BANK_HOME,active:false});
  await onTab(tab.id);
  const profile=draft.bank_session?.profile_name || 'the required bank profile';
  let prompted=false;
  await progress('checking_session', 'Checking the bank session in the background…');
  for(let i=0;i<attempts;i++) {
    await pause(500);
    try { tab=await chrome.tabs.get(tab.id); if (!tab) throw new Error(); }
    catch { throw Object.assign(new Error('The Truliant history tab was closed. Select Check completion to start again.'), {code:'BANK_SIGN_IN_REQUIRED'}); }
    if (!tab.url && tab.status === 'loading') continue;
    if (!String(tab.url || '').startsWith(`${BANK}/`)) throw Object.assign(new Error('The bank history tab left Truliant. Select Check completion to start again.'), {code:'BANK_SIGN_IN_REQUIRED'});
    const results=await chrome.scripting.executeScript({target:{tabId:tab.id,allFrames:true},func:()=>({
      accounts:[...document.querySelectorAll('[id^="account-link-"]')].map(element=>(element.textContent||'').replace(/\s+/g,' ').trim()),
      loginRequired:[...document.querySelectorAll('input[type="password"]')].some(element=>element.getClientRects().length>0)
    })}).catch(()=>[]);
    const suffixes=results.flatMap(result=>result.result?.accounts || []).map(parseAccountSummary).filter(Boolean).map(account=>account.last4);
    if(suffixes.includes(draft.from_last4) && suffixes.includes(draft.to_last4)) return tab;
    const needsAccess=results.some(result=>result.result?.loginRequired) || suffixes.length>0 || /\/(login|logout)(\/|\?|$)/i.test(tab.url);
    if (needsAccess && !prompted) {
      if (!interactive) {
        await chrome.tabs.remove(tab.id).catch(()=>{});
        await onTab(null);
        throw Object.assign(new Error(`Sign in to ${profile}, then select Check completion.`), {code:'BANK_SIGN_IN_REQUIRED'});
      }
      await chrome.tabs.update(tab.id,{active:true});
      if (tab.windowId != null) await chrome.windows.update(tab.windowId,{focused:true});
      prompted=true;
      await progress('awaiting_sign_in', `Sign in to ${profile}. Waiting for accounts ••${draft.from_last4} and ••${draft.to_last4}…`);
    }
  }
  // Retain only a tab that was explicitly shown for sign-in; a slow or broken
  // page must not steal focus or accumulate invisible tabs.
  if (!prompted) { await chrome.tabs.remove(tab.id).catch(()=>{}); await onTab(null); }
  throw Object.assign(new Error(prompted
    ? `Sign-in or account access is still needed for ${profile}. Finish signing in, then select Check completion again.`
    : 'Bank account information did not load. Select Check completion to retry.'), {code:'BANK_SIGN_IN_REQUIRED'});
}

export async function focusTransferTab(chrome, active) {
  const tab=active?.tabId ? await chrome.tabs.get(active.tabId).catch(()=>null) : null;
  if (!tab || !String(tab.url || '').startsWith(`${BANK}/`)) {
    throw new Error('The original transfer tab is unavailable. Check your existing Truliant tabs before preparing another transfer.');
  }
  // No navigation: preserve edits and any bank confirmation screen.
  await chrome.tabs.update(tab.id,{active:true});
  if (tab.windowId != null) await chrome.windows.update(tab.windowId,{focused:true});
}
