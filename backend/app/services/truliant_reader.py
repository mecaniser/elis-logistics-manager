"""Read-only browser adapter. Never opens a transfer form or submits a payment.

Uses a dedicated private profile and optional worker-only credential secrets.
No cookies are copied from a personal browser. MFA requires operator recovery.
"""
import os
import re
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pathlib import Path
from app.services.bank_monitor import AccountBalance, BalanceSnapshot, usd_cents

LOGIN = 'https://www.truliantfcuonline.org/dbank/live/app/login/consumer'
HOME = 'https://www.truliantfcuonline.org/dbank/live/app/home'
MONEY = r'-?\$(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}'


class BankReadError(Exception):
    pass


def parse_card(text):
    """Parse only explicitly labeled amounts; no currency/zero guessing."""
    text = ' '.join(text.split())
    suffix = re.search(r'\*{2,}(\d{4})\b', text)
    if not suffix:
        raise BankReadError('account_format_changed')
    values = {'last4': suffix.group(1)}
    for label, key in [('Current Balance', 'current_cents'),
                       ('Available Balance', 'available_cents'),
                       ('Available Credit', 'available_credit_cents')]:
        match = re.search(re.escape(label) + r'\s*\**\s*(' + MONEY + r')(?![\d.])', text)
        if match:
            values[key] = usd_cents(match.group(1))
    return AccountBalance(**values)


def sign_in(page, profile, tenant_id):
    """One credential submission, then a durable stop until operator recovery.

    The marker is written BEFORE submission: crashes/timeouts must never cause
    repeated password attempts. No secrets or bank response text are persisted.
    """
    marker = profile / '.login-needs-review'
    if marker.exists():
        raise BankReadError('login_review_required')
    username = os.getenv(f'BANK_MONITOR_USERNAME_{tenant_id}', '')
    password = os.getenv(f'BANK_MONITOR_PASSWORD_{tenant_id}', '')
    if not username or not password:
        raise BankReadError('credentials_required')
    page.goto(LOGIN, wait_until='domcontentloaded', timeout=45000)
    page.locator('#username').wait_for(state='visible', timeout=20000)
    # Only the observed first-party login page may receive credentials.
    parsed = urlsplit(page.url)
    if (parsed.scheme, parsed.netloc, parsed.path) != (
            'https', 'www.truliantfcuonline.org', '/dbank/live/app/login/consumer'):
        raise BankReadError('unexpected_login_page')
    try:
        fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise BankReadError('login_review_required') from None
    os.close(fd)
    page.locator('#username').fill(username)
    page.locator('#password').fill(password)
    page.get_by_role('button', name='Login', exact=True).click()
    cards = page.frame_locator('iframe#appContainer').locator('[id^="account-link-"]')
    try:
        cards.first.wait_for(state='visible', timeout=30000)
    except Exception:
        if re.search(r'mfa|verification', page.url, re.I):
            raise BankReadError('mfa_required') from None
        # Deliberately do not infer bad passwords from arbitrary bank content.
        raise BankReadError('login_review_required') from None
    marker.unlink()  # Success is established by the authenticated account view.


def pending_total(rows):
    """Require explicit Pending -> Posted boundaries; never infer missing = zero."""
    state = 'before'
    total = 0
    seen = set()
    for row in rows:
        section = row.get('section')
        if section == 'pending transactions section':
            if state != 'before':
                raise BankReadError('pending_data_unavailable')
            state = 'pending'
        elif section == 'posted transactions section':
            if state != 'pending':
                raise BankReadError('pending_data_unavailable')
            return total
        elif state == 'pending':
            key = row.get('id')
            if not key or key in seen or not row.get('amount'):
                raise BankReadError('pending_data_unavailable')
            seen.add(key)
            try:
                amount = usd_cents(row['amount'])
            except ValueError:
                raise BankReadError('pending_data_unavailable') from None
            total += max(0, -amount)  # Pending deposits cannot offset debits.
    raise BankReadError('pending_data_unavailable')


def read_pending(page, suffix):
    frame = page.frame_locator('iframe#appContainer')
    table = frame.get_by_role('table', name='account transactions', exact=True)
    table.wait_for(state='visible', timeout=20000)
    # The history heading exposes the full account number; compare in memory
    # only, and never persist it or include it in exceptions/logging.
    headings = frame.get_by_role('heading', level=2).all_text_contents()
    if not any(re.search(r'(?<!\d)\d*' + re.escape(suffix) + r'\s*$', h) for h in headings):
        raise BankReadError('account_identity_unverified')
    rows = table.locator('tbody tr').evaluate_all("""rows => rows.map(row => {
        const amount = row.querySelector('[id^="amount-value-cell-"]');
        return {section: row.getAttribute('aria-label'),
                id: amount ? amount.id : null,
                amount: amount ? amount.innerText : null};
    })""")
    return pending_total(rows)


def credit_details(rows):
    values = {}
    labels = {'Balance': 'outstanding_cents', 'Accrued Interest': 'accrued_interest_cents'}
    for row in rows:
        key = labels.get(row.get('label'))
        if key:
            if key in values:
                raise BankReadError('credit_details_unavailable')
            try:
                value = usd_cents(row.get('amount', ''))
            except ValueError:
                raise BankReadError('credit_details_unavailable') from None
            if value < 0:
                raise BankReadError('credit_details_unavailable')
            values[key] = value
    if set(values) != set(labels.values()):
        raise BankReadError('credit_details_unavailable')
    # No payoff inference: accrued interest may have separate posting rules.
    return values


def read_credit_details(page, suffix):
    frame = page.frame_locator('iframe#appContainer')
    frame.get_by_role('button', name='Account Details', exact=True).click()
    heading = frame.get_by_role('heading', level=1).filter(
        has_text=re.compile(r'(?<!\d)\d*' + re.escape(suffix) + r'\s*$'))
    heading.wait_for(state='visible', timeout=20000)
    if heading.count() != 1:
        raise BankReadError('account_identity_unverified')
    rows = frame.locator('li[data-testid^="account-summary__detail-row__"]').evaluate_all(
        """rows => rows.map(row => ({
            label: row.querySelector('p')?.innerText.trim(),
            amount: row.querySelector('h6')?.innerText.trim()
        })).filter(row => ['Balance', 'Accrued Interest'].includes(row.label))""")
    return credit_details(rows)


def read_balances(profile_path, rules, tenant_id=None):
    # Imported lazily: the web application does not need a browser installation.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise BankReadError('browser_dependency_missing') from None
    profile = Path(profile_path).expanduser()
    if not profile.is_absolute() or profile.is_symlink():
        raise BankReadError('profile_permissions_required')
    if not profile.is_dir():
        raise BankReadError('profile_setup_required')
    if profile.stat().st_mode & 0o077:
        raise BankReadError('profile_permissions_required')
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(str(profile), headless=True)
            try:
                observed_at = datetime.now(timezone.utc)
                page = context.new_page()
                page.goto(HOME, wait_until='domcontentloaded', timeout=45000)
                frame = page.frame_locator('iframe#appContainer')
                cards = frame.locator('[id^="account-link-"]')
                try:
                    cards.first.wait_for(state='visible', timeout=20000)
                except Exception:
                    if tenant_id is None:
                        raise BankReadError('sign_in_required') from None
                    sign_in(page, profile, tenant_id)
                needed = {a.last4 for a in rules.checking + rules.sources}
                accounts = []
                for card in cards.all():
                    text = card.inner_text()
                    suffix = re.search(r'\*{2,}(\d{4})\b', text)
                    if suffix and suffix.group(1) in needed:
                        accounts.append(parse_card(text))
                if rules.basis == 'posted_and_pending' or rules.repayment.enabled:
                    for checking in rules.checking:
                        page.goto(HOME, wait_until='domcontentloaded', timeout=45000)
                        cards.first.wait_for(state='visible', timeout=20000)
                        matches = cards.filter(has_text=re.compile(r'\*{2,}' + re.escape(checking.last4) + r'\b'))
                        if matches.count() != 1:
                            raise BankReadError('account_identity_unverified')
                        matches.click()
                        try:
                            pending = read_pending(page, checking.last4)
                        except BankReadError:
                            if rules.basis == 'posted_and_pending':
                                raise
                            continue  # Repayment remains blocked on missing evidence.
                        for account in accounts:
                            if account.last4 == checking.last4:
                                account.pending_debits_cents = pending
                if rules.repayment.enabled:
                    for source in rules.sources:
                        page.goto(HOME, wait_until='domcontentloaded', timeout=45000)
                        cards.first.wait_for(state='visible', timeout=20000)
                        matches = cards.filter(has_text=re.compile(r'\*{2,}' + re.escape(source.last4) + r'\b'))
                        if matches.count() != 1:
                            raise BankReadError('account_identity_unverified')
                        matches.click()
                        details = read_credit_details(page, source.last4)
                        for account in accounts:
                            if account.last4 == source.last4:
                                for key, value in details.items():
                                    setattr(account, key, value)
                return BalanceSnapshot(observed_at=observed_at, accounts=accounts)
            finally:
                context.close()
    except BankReadError:
        raise
    except Exception:
        # Browser exceptions may contain account data, URLs, or profile paths.
        raise BankReadError('bank_read_failed') from None
