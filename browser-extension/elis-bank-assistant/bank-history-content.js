(() => {
  if (window === window.top || location.origin !== 'https://www.truliantfcuonline.org') return;
  const normalized = value => value.replace(/\s*\/\s*/g, ' ').replace(/\s+/g, ' ').trim();

  chrome.runtime.onMessage.addListener((message, _sender, reply) => {
    if (message?.type === 'ELIS_OPEN_ACCOUNT' && /^\d{4}$/.test(message.suffix || '')) {
      const links = [...document.querySelectorAll('[id^="account-link-"]')];
      // Other Truliant child frames must remain silent so they cannot win the
      // one-response tabs.sendMessage race before the account frame replies.
      if (links.length === 0) return;
      const matches = links.filter(element => new RegExp(`\\*{2,}${message.suffix}(?!\\d)`).test(element.textContent));
      // A different account-card frame must also stay silent. Only the frame
      // containing the requested account may answer the tab-wide message.
      if (matches.length === 0) return;
      reply({ready: true, opened: matches.length === 1});
      // Deliver the response before navigation destroys this child frame.
      if (matches.length === 1) setTimeout(() => matches[0].click(), 0);
      return;
    }
    if (message?.type === 'ELIS_FIND_POSTED') {
      if (!document.querySelector('table[aria-label="account transactions"]')) return;
      findPosted(message.wanted).then(reply);
      return true;
    }
  });

  async function findPosted(wanted) {
    const table = document.querySelector('table[aria-label="account transactions"]');
    if (!table) return {ready: false};
    const headings = [...document.querySelectorAll('h2')].map(element => element.textContent.trim())
      .filter(text => new RegExp(`\\d*${wanted.suffix}$`).test(text));
    // Truliant renders masked and full-number variants of the same account
    // heading. The configured identity boundary is the requested last four.
    if (headings.length === 0) return {ready: true, error: 'Account identity could not be verified.'};
    let posted = false;
    const matches = [];
    for (const row of table.querySelectorAll('tbody tr')) {
      if (row.getAttribute('aria-label') === 'posted transactions section') { posted = true; continue; }
      if (!posted) continue;
      const amount = row.querySelector('[id^="amount-value-cell-"]');
      const description = row.querySelector('[id^="description-value-cell-"]');
      const date = row.querySelector('[id^="transactionDate-value-cell-"]');
      if (!amount || !description || !date) continue;
      const expected = `${wanted.source ? '-' : ''}$${(wanted.amount_cents / 100).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
      const text = normalized(description.textContent);
      if (amount.textContent.trim() === expected && text.endsWith(wanted.memo) && date.textContent.trim() === wanted.bank_date &&
          (wanted.source ? text.startsWith('Principal Disbursement ') : text.startsWith('Deposit '))) {
        const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(amount.id));
        matches.push([...new Uint8Array(bytes)].map(value => value.toString(16).padStart(2, '0')).join(''));
      }
    }
    return matches.length === 1 ? {ready: true, match: matches[0]} :
      {ready: true, error: matches.length ? 'Multiple matching entries require review.' : 'No unique posted match found. It may not have posted yet.'};
  }
})();
