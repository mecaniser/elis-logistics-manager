const nonce = new URL(location.href).searchParams.get('nonce');
const approve = document.querySelector('#approve');
const cancel = document.querySelector('#cancel');
const status = document.querySelector('#status');
const send = action => chrome.runtime.sendMessage({ action, nonce });
let timer;
let finishing = false;
async function finish(action) {
  if (finishing) return;
  finishing = true;
  approve.disabled = true;
  cancel.disabled = true;
  clearInterval(timer);
  status.textContent = action === 'approve' ? 'Checking account histories…' : 'Closing review…';
  try {
    const result = await send(action);
    if (!result?.ok) throw new Error();
  } catch {
    status.textContent = 'Review expired. Close this dialog and select Check completion again.';
  }
}
cancel.addEventListener('click', () => void finish('cancel'));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') { event.preventDefault(); void finish('cancel'); }
});
try {
  const result = await send('read-verification-review');
  if (!result?.ok) throw new Error();
  const { draft, expiresAt } = result;
  const text = (selector, value) => { document.querySelector(selector).textContent = value; };
  text('#profile', draft.bank_session?.profile_name || 'Truliant');
  text('#from', `${draft.bank_session?.source_name || 'Account'} ••${draft.from_last4}`);
  text('#to', `${draft.bank_session?.destination_name || 'Account'} ••${draft.to_last4}`);
  text('#amount', (draft.amount_cents / 100).toLocaleString('en-US', { style:'currency', currency:'USD' }));
  text('#memo', draft.memo);
  const tick = () => {
    const seconds = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
    status.textContent = `Review expires in ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    if (!seconds) { clearInterval(timer); approve.disabled = true; }
  };
  timer = setInterval(tick, 1000);
  tick();
  approve.disabled = false;
  approve.addEventListener('click', () => void finish('approve'));
  approve.focus();
} catch {
  status.textContent = 'Review unavailable. Close this dialog and select Check completion again.';
}
