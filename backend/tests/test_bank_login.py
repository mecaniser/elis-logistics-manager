"""Synthetic bank authentication outcomes; no network or real credentials."""
import pytest
from app.services.truliant_reader import sign_in, BankReadError


class Page:
    def __init__(self, outcome='success', redirect=None):
        self.url = ''
        self.outcome = outcome
        self.redirect = redirect
        self.submissions = 0
        self.filled = []
    def goto(self, url, **kwargs):
        self.url = self.redirect or url
    def locator(self, selector):
        page = self
        class Field:
            @property
            def first(self):
                return self
            def wait_for(self, **kwargs):
                if page.outcome == 'challenge' or ('account-link' in selector and page.outcome != 'success'):
                    raise RuntimeError('private provider error')
            def count(self):
                return 1 if page.outcome == 'challenge' and 'challenge-platform' in selector else 0
            def fill(self, value):
                page.filled.append(selector)
        return Field()
    def frame_locator(self, selector):
        return self
    def title(self):
        return 'Just a moment...' if self.outcome == 'challenge' else 'Truliant'
    def get_by_role(self, *args, **kwargs):
        page = self
        class Submit:
            def click(self):
                page.submissions += 1
                if page.outcome == 'mfa':
                    page.url = 'https://www.truliantfcuonline.org/nxg-olb/live/mfaVerification'
        return Submit()


@pytest.fixture
def secrets(monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_USERNAME_1', 'synthetic-user')
    monkeypatch.setenv('BANK_MONITOR_PASSWORD_1', 'synthetic-password')


@pytest.mark.parametrize('outcome,status', [('mfa', 'mfa_required'), ('failure', 'login_review_required')])
def test_uncertain_login_stops_across_restarts(tmp_path, secrets, outcome, status):
    page = Page(outcome)
    with pytest.raises(BankReadError, match=f'^{status}$'):
        sign_in(page, tmp_path, 1)
    with pytest.raises(BankReadError, match='^login_review_required$'):
        sign_in(page, tmp_path, 1)
    assert page.submissions == 1
    marker = tmp_path / '.login-needs-review'
    assert marker.read_bytes() == b''
    assert marker.stat().st_mode & 0o777 == 0o600


def test_exact_origin_required(tmp_path, secrets):
    page = Page(redirect='https://example.com/dbank/live/app/login/consumer')
    with pytest.raises(BankReadError, match='^unexpected_login_page$'):
        sign_in(page, tmp_path, 1)
    assert not page.filled and not page.submissions


def test_missing_secret_does_not_submit(tmp_path, monkeypatch):
    monkeypatch.delenv('BANK_MONITOR_USERNAME_1', raising=False)
    monkeypatch.delenv('BANK_MONITOR_PASSWORD_1', raising=False)
    page = Page()
    with pytest.raises(BankReadError, match='^credentials_required$'):
        sign_in(page, tmp_path, 1)
    assert not page.submissions


def test_success_clears_guard(tmp_path, secrets):
    page = Page()
    sign_in(page, tmp_path, 1)
    assert page.submissions == 1
    assert not (tmp_path / '.login-needs-review').exists()


def test_security_challenge_stops_before_credentials(tmp_path, secrets):
    page = Page(outcome='challenge')
    with pytest.raises(BankReadError, match='^bank_security_challenge$'):
        sign_in(page, tmp_path, 1)
    assert page.submissions == 0
    assert page.filled == []
    assert not (tmp_path / '.login-needs-review').exists()
