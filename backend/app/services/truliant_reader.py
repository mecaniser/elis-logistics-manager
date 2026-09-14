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
                # Pending extraction is deliberately not inferred from summary
                # balances. Pending coverage fails closed until verified end-to-end.
                return BalanceSnapshot(observed_at=datetime.now(timezone.utc), accounts=accounts)
            finally:
                context.close()
    except BankReadError:
        raise
    except Exception:
        # Browser exceptions may contain account data, URLs, or profile paths.
        raise BankReadError('bank_read_failed') from None
