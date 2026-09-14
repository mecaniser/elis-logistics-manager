"""Read-only browser adapter. Never opens a transfer form or submits a payment.

Uses a dedicated, operator-authenticated profile on the worker host. No cookies
are copied from a personal browser. MFA and session expiry require user action.
"""
import re
from datetime import datetime, timezone
from pathlib import Path
from app.services.bank_monitor import AccountBalance, BalanceSnapshot, usd_cents

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


def read_balances(profile_path, rules):
    # Imported lazily: the web application does not need a browser installation.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise BankReadError('browser_dependency_missing') from None
    profile = Path(profile_path).expanduser()
    if not profile.is_dir():
        raise BankReadError('sign_in_required')
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
                    if re.search(r'login|mfa|verification|sign', page.url, re.I):
                        raise BankReadError('sign_in_required') from None
                    raise BankReadError('account_view_unavailable') from None
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
