export const BANK = 'https://www.truliantfcuonline.org';
export const TRANSFERS = `${BANK}/dbank/live/app/home/olb/transfers`;
export function allowedSender(url) {
  try {
    const u = new URL(url);
    const allowedOrigins = new Set([
      'http://127.0.0.1:18081',
      'https://www.elisprotech.com',
    ]);
    return allowedOrigins.has(u.origin) && u.pathname === '/bank-monitor';
  } catch { return false; }
}
export function validDraft(d) {
  const kind = d?.kind || (d?.memo?.startsWith('Cvr ') ? 'coverage' : null);
  return d && /^[a-f0-9-]{36}$/.test(d.id) && Number.isSafeInteger(d.amount_cents) &&
    (!d.bank_session || (/^[a-f0-9-]{36}$/.test(d.bank_session.profile_id) && typeof d.bank_session.profile_name === 'string' && d.bank_session.profile_name.length <= 80 && d.bank_session.institution_id === 'ins_109917')) &&
    d.amount_cents > 0 && d.amount_cents <= 100000000 &&
    /^\d{4}$/.test(d.from_last4) && /^\d{4}$/.test(d.to_last4) && d.from_last4 !== d.to_last4 &&
    ((kind === 'coverage' && /^Cvr [A-Za-z0-9 ._-]{1,30}$/.test(d.memo)) ||
     (kind === 'repayment' && /^Rpy [A-Za-z0-9 ._-]{1,30}$/.test(d.memo)));
}
function sameBankSession(left, right) {
  if (!left || !right) return !left && !right;
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
  return [...keys].every(key => left[key] === right[key]);
}
export function boundDraft(active, draft, sender) {
  return !!active && active.origin === new URL(sender.url).origin && active.elisTabId === sender.tab?.id &&
    ['id','amount_cents','from_last4','to_last4','memo'].every(k => active.draft?.[k] === draft?.[k]) &&
    sameBankSession(active.draft?.bank_session, draft?.bank_session);
}
export function parseAccountSummary(text) {
  const clean=String(text || '').replace(/\s+/g,' ').trim();
  const suffix=clean.match(/\*{2,}(\d{4})(?!\d)/);
  if(!suffix) return null;
  const nickname=clean.slice(0,clean.indexOf(suffix[0])).trim() || `Account ${suffix[1]}`;
  const cents = label => {
    const match=clean.match(new RegExp(`${label}\\s*\\**\\s*(-?\\$[\\d,]+\\.\\d{2})`,'i'));
    if(!match) return null;
    return Math.round(Number(match[1].replace(/[$,]/g,''))*100);
  };
  return {
    nickname,
    last4:suffix[1],
    kind:/Available Credit/i.test(clean) ? 'credit' : /Available Balance/i.test(clean) && /Current Balance/i.test(clean) ? 'checking' : 'other',
    current_cents:cents('Current Balance'),
    available_cents:cents('Available Balance'),
    available_credit_cents:cents('Available Credit')
  };
}

// Only an identifier already embedded in the saved draft memo is authoritative.
export function transferReference(draft) {
  if (!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(draft?.id || '')) return null;
  const memo = String(draft.memo || '').trim().toLowerCase();
  return [draft.id.slice(0, 13), draft.id.slice(0, 8)].map(id => id.toLowerCase())
    .find(id => memo.endsWith(` ${id}`)) || null;
}
