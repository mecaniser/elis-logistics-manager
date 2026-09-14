export const BANK = 'https://www.truliantfcuonline.org';
export const TRANSFERS = `${BANK}/dbank/live/app/home/olb/transfers`;
export function allowedSender(url) {
  try {
    const u = new URL(url);
    return ['https://www.elisprotech.com', 'http://127.0.0.1:18081'].includes(u.origin) && u.pathname === '/bank-monitor';
  } catch { return false; }
}
export function validDraft(d) {
  return d && /^[a-f0-9-]{36}$/.test(d.id) && Number.isSafeInteger(d.amount_cents) &&
    d.amount_cents > 0 && d.amount_cents <= 100000000 &&
    /^\d{4}$/.test(d.from_last4) && /^\d{4}$/.test(d.to_last4) && d.from_last4 !== d.to_last4 &&
    /^Cvr [A-Za-z0-9 ._-]{1,30}$/.test(d.memo);
}
