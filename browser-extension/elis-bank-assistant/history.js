export function openAccount(suffix) {
  if(location.origin!=='https://www.truliantfcuonline.org') return false;
  const matches=[...document.querySelectorAll('[id^="account-link-"]')].filter(e=>new RegExp(`\\*{2,}${suffix}(?!\\d)`).test(e.textContent));
  if(matches.length!==1) return false;
  matches[0].click(); return true;
}
export async function findPostedEntry(wanted) {
  if(location.origin!=='https://www.truliantfcuonline.org') return null;
  const table=document.querySelector('table[aria-label="account transactions"]');
  if(!table) return null;
  const headings=[...document.querySelectorAll('h2')].map(e=>e.textContent.trim()).filter(text=>new RegExp(`\\d*${wanted.suffix}$`).test(text));
  // Truliant can render masked and full-number desktop/mobile headings for the
  // same account. Each accepted heading is already bound to the requested last4.
  if(headings.length===0) return {error:'Account identity could not be verified.'};
  let posted=false; const matches=[];
  const normalized=s=>s.replace(/\s*\/\s*/g,' ').replace(/\s+/g,' ').trim();
  for(const row of table.querySelectorAll('tbody tr')) {
    if(row.getAttribute('aria-label')==='posted transactions section') {posted=true;continue;}
    if(!posted) continue;
    const amount=row.querySelector('[id^="amount-value-cell-"]');
    const description=row.querySelector('[id^="description-value-cell-"]');
    const date=row.querySelector('[id^="transactionDate-value-cell-"]');
    if(!amount||!description||!date) continue;
    const expected=`${wanted.source?'-':''}$${(wanted.amount_cents/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
    const text=normalized(description.textContent);
    if(amount.textContent.trim()===expected && text.endsWith(wanted.memo) &&
       date.textContent.trim()===wanted.bank_date &&
       (wanted.source ? text.startsWith('Principal Disbursement ') : text.startsWith('Deposit '))) {
      const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(amount.id));
      matches.push([...new Uint8Array(bytes)].map(n=>n.toString(16).padStart(2,'0')).join(''));
    }
  }
  return matches.length===1 ? {match:matches[0]} : {error:matches.length?'Multiple matching entries require review.':'No unique posted match found. It may not have posted yet.'};
}
