// Runs in Chrome's isolated content-script world. No submit control is activated.
export async function fillForm(draft) {
  if (location.origin !== 'https://www.truliantfcuonline.org' ||
      location.pathname !== '/dbank/live/app/home/olb/transfers') return {ok:false, code:'LOGIN_REQUIRED', error:`Sign in to ${draft.bank_session?.profile_name || 'Truliant'}, then return to ELIS and resume this draft.`};
  const visible = e => e && e.getClientRects().length > 0;
  async function until(fn) {
    const end = Date.now() + 12000;
    while (Date.now() < end) { const value = fn(); if (value) return value; await new Promise(r=>setTimeout(r,100)); }
    throw new Error('Bank form changed or did not load. Nothing was submitted.');
  }
  const money = text => {
    const match = text.trim().match(/^\$(\d{1,3}(?:,\d{3})*|\d+)\.(\d{2})$/);
    if (!match) throw new Error('Available credit cannot be verified.');
    return Number(match[1].replaceAll(',',''))*100 + Number(match[2]);
  };
  try {
    await until(()=>document.querySelector('#amountInputField'));
    const amount = document.querySelector('#amountInputField');
    const memo = document.querySelector('#memoInputField');
    if (!memo || (amount.value && amount.value !== '0.00') || memo.value) throw new Error('An existing form needs review. It was not overwritten.');
    const repeat = document.querySelector('#frequency');
    if (!repeat || repeat.checked) throw new Error('Only one-time transfers are supported.');
    // Date must be today's Eastern date. We never change it or schedule a payment.
    const parts = new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    const date = [...document.querySelectorAll('#transferContainer input')].find(e=>/^\d{2}\/\d{2}\/\d{4}$/.test(e.value));
    if (!date || date.value !== parts) throw new Error('Bank date is not today. Review the date manually.');
    async function select(label, suffix, side) {
      const labels = [...document.querySelectorAll('#transferContainer label')].filter(e=>e.textContent.trim()===label);
      if(labels.length!==1) throw new Error('Account selector cannot be identified.');
      const buttons = [...labels[0].parentElement.querySelectorAll('button')].filter(visible);
      if(buttons.length!==1) throw new Error('Account selector is ambiguous.');
      buttons[0].click();
      let options;
      try { options = await until(()=>{
        const found=[...document.querySelectorAll('li[role="menuitem"]')].filter(visible).filter(e=>{
          const title=e.querySelector(`[id^="listAccountDescription"][id$="${side}"]`);
          return title && new RegExp(`(?:^|\\s)${suffix}$`).test(title.textContent.trim());
        }); return found.length ? found : null;
      }); } catch (error) {
        if (draft.bank_session) { const e = new Error(`Use the ${draft.bank_session.profile_name} login. Account ••${suffix} is not available in this session. No amount or memo was filled.`); e.code='PROFILE_SESSION_REQUIRED'; throw e; }
        throw error;
      }
      if(options.length!==1) throw new Error('Account suffix is ambiguous.');
      if(draft.bank_session) {
        const expected = side === 'From' ? draft.bank_session.source_name : draft.bank_session.destination_name;
        const title = options[0].querySelector(`[id^="listAccountDescription"][id$="${side}"]`)?.textContent || '';
        const normalize = value => String(value).toLowerCase().replace(/[^a-z0-9]/g, '');
        if(!expected || normalize(title.replace(new RegExp(`${suffix}$`), '')) !== normalize(expected)) {
          const e = new Error(`The ${side.toLowerCase()} account name does not match ${draft.bank_session.profile_name}. Check the selected bank login. No amount or memo was filled.`);
          e.code='PROFILE_SESSION_REQUIRED'; throw e;
        }
      }
      if(side==='From') {
        const label=options[0].querySelector('[id^="accountBalanceLabel"]');
        const balance=[...options[0].querySelectorAll('[id^="accountBalance"]')].find(e=>!e.id.startsWith('accountBalanceLabel'));
        if(label?.textContent.trim()!=='Available' || !balance || money(balance.textContent)<draft.amount_cents)
          throw new Error('This source cannot cover the whole charge. Review funding in ELIS.');
      }
      options[0].click();
      await until(()=>[...document.querySelectorAll(`[id^="accountDescription"][id$="${side}"]`)].some(e=>visible(e)&&new RegExp(`${suffix}$`).test(e.textContent.trim())));
    }
    await select('From',draft.from_last4,'From');
    await select('To',draft.to_last4,'To');
    const set = (el,value) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,value); el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); };
    set(amount,(draft.amount_cents/100).toFixed(2));
    set(memo,draft.memo);
    await new Promise(r=>setTimeout(r,150));
    if (!/^\$?(?:\d{1,3}(?:,\d{3})*|\d+)\.\d{2}$/.test(amount.value.trim()) || money('$'+amount.value.trim().replace(/^\$/, '')) !== draft.amount_cents) throw new Error('Bank amount differs from the reviewed amount. Inspect the bank form; if you already submitted, check posting in ELIS.');
    if (memo.value !== draft.memo) throw new Error('Bank memo differs from the ELIS reference. If you submitted with an edited memo, check posting in ELIS and confirm the matching bank entries.');
    memo.focus();
    return {ok:true,status:'prepared_awaiting_submission'};
  } catch(e) { return {ok:false,code:e.code,error:e.message}; }
}
