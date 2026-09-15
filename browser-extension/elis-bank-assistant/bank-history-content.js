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
    if (message?.type === 'ELIS_LIST_COVERAGE_DEBITS' && /^\d{4}$/.test(message.suffix || '')) {
      if (!document.querySelector('table[aria-label="account transactions"]')) return;
      listCoverageDebits(message.suffix, message.include_pending === true).then(reply);
      return true;
    }
  });

  const parseMoney = value => {
    const text = String(value || '').replace(/\s/g, '').trim();
    const match = text.match(/^(?:-\$([\d,]+\.\d{2})|\$-([\d,]+\.\d{2})|\(([\d,]+\.\d{2})\)|\$([\d,]+\.\d{2}))$/);
    if (!match) return null;
    const digits = match[1] || match[2] || match[3] || match[4];
    const cents = Math.round(Number(digits.replace(/,/g, '')) * 100);
    return match[1] || match[2] || match[3] ? -cents : cents;
  };

  async function listCoverageDebits(suffix, includePending) {
    const table = document.querySelector('table[aria-label="account transactions"]');
    const headings = [...document.querySelectorAll('h2')].map(element => element.textContent.trim())
      .filter(text => new RegExp(`\\d*${suffix}$`).test(text));
    if (!table || headings.length === 0) return {ready: true, error: 'Account identity could not be verified.'};
    let section = '';
    const rows = [];
    for (const row of table.querySelectorAll('tbody tr')) {
      if (row.getAttribute('aria-label') === 'pending transactions section') { section = 'pending'; continue; }
      if (row.getAttribute('aria-label') === 'posted transactions section') { section = 'posted'; continue; }
      if (!section || rows.length >= 100) continue;
      const amountNode = row.querySelector('[id^="amount-value-cell-"]');
      const descriptionNode = row.querySelector('[id^="description-value-cell-"]');
      const dateNode = row.querySelector('[id^="transactionDate-value-cell-"]');
      const balanceNode = row.querySelector('[id^="ledgerBalance-value-cell-"], [id^="balance-value-cell-"]');
      if (!amountNode || !descriptionNode || !dateNode) continue;
      const amountCents = parseMoney(amountNode.textContent);
      if (amountCents == null) continue;
      const description = normalized(descriptionNode.textContent);
      rows.push({section, amountNode, date:dateNode.textContent.trim(), description, amount_cents:amountCents,
        balance_cents:balanceNode ? parseMoney(balanceNode.textContent) : null});
    }
    const postedRows = rows.filter(row => row.section === 'posted');
    const overdraftIndex = postedRows.findIndex(row => row.amount_cents > 0 && /^Overdraft Service Deposit\b/i.test(row.description) && row.balance_cents === 0);
    const overdraftDetected = overdraftIndex === 0;
    let incident = postedRows;
    if (overdraftDetected) {
      incident = postedRows.slice(1);
      const boundary = incident.findIndex(row => row.balance_cents != null && row.balance_cents >= 0);
      if (boundary >= 0) incident = incident.slice(0, boundary);
    }
    let candidates = incident.filter(row => row.amount_cents < 0 && (overdraftDetected || row.balance_cents == null || row.balance_cents < 0));
    if (overdraftDetected) {
      const coverageDeposits = incident.filter(row => row.amount_cents > 0 && /^Deposit Cvr\b/i.test(row.description));
      for (const deposit of coverageDeposits) {
        const match = candidates.findIndex(row => Math.abs(row.amount_cents) === deposit.amount_cents);
        if (match >= 0) candidates.splice(match, 1);
      }
    }
    if (includePending) candidates.unshift(...rows.filter(row => row.section === 'pending' && row.amount_cents < 0));
    const transactions = [];
    for (const row of candidates) {
      if (/^(deposit|principal disbursement)\b/i.test(row.description) || /\b(overdraft|nsf|insufficient funds)\b|\bfee\b/i.test(row.description)) continue;
      const {amountNode, date, description, amount_cents, balance_cents, section} = row;
      const identity = `${suffix}|${amountNode.id}|${date}|${description}|${amount_cents}`;
      const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(identity));
      transactions.push({
        reference: [...new Uint8Array(bytes)].map(value => value.toString(16).padStart(2, '0')).join(''),
        date,
        description,
        amount_cents: Math.abs(amount_cents),
        balance_cents,
        pending: section === 'pending'
      });
    }
    return {ready: true, transactions, overdraft_detected:overdraftDetected};
  }

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
