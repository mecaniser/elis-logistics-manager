from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, Date, UniqueConstraint
from app.database import Base


class BankMonitorConfig(Base):
    __tablename__ = 'bank_monitor_configs'
    tenant_id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    rules = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class BankMonitorRun(Base):
    __tablename__ = 'bank_monitor_runs'
    __table_args__ = (UniqueConstraint('tenant_id', 'scheduled_date', name='uq_bank_monitor_daily'),)
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    scheduled_date = Column(Date, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(40), nullable=False)
    result = Column(JSON, nullable=False, default=dict)


class BankRepaymentRun(Base):
    """On-demand repayment evaluations, separate from the daily scheduler slot."""
    __tablename__ = 'bank_repayment_runs'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(40), nullable=False)
    result = Column(JSON, nullable=False, default=dict)


class BankMonitorWorkerHeartbeat(Base):
    __tablename__ = 'bank_monitor_worker_heartbeats'
    tenant_id = Column(Integer, primary_key=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)


class BankMonitorConnectionCheck(Base):
    """Read-only, on-demand verification of the worker's bank access."""
    __tablename__ = 'bank_monitor_connection_checks'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    requested_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(40), nullable=False)
    result = Column(JSON, nullable=False, default=dict)


class BankMonitorBrowserCheck(Base):
    """Authenticated Chrome-assisted read, separate from server-worker checks."""
    __tablename__ = 'bank_monitor_browser_checks'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(40), nullable=False)
    result = Column(JSON, nullable=False, default=dict)


class BankProviderConnection(Base):
    """Tenant-scoped, consented read-only bank connection. Never store bank credentials."""
    __tablename__ = 'bank_provider_connections'
    tenant_id = Column(Integer, primary_key=True)
    provider = Column(String(20), nullable=False)
    item_id = Column(String(150), nullable=False, unique=True)
    institution_id = Column(String(80), nullable=False)
    encrypted_access_token = Column(String(2048), nullable=False)
    account_map = Column(JSON, nullable=False)
    status = Column(String(40), nullable=False)
    linked_at = Column(DateTime(timezone=True), nullable=False)
    last_checked_at = Column(DateTime(timezone=True))
    last_error = Column(String(80))


class BankProviderLinkAttempt(Base):
    """One-use Link session binding a provider consent to an ELIS tenant."""
    __tablename__ = 'bank_provider_link_attempts'
    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))


class BankTransferDraft(Base):
    __tablename__ = 'bank_transfer_drafts'
    __table_args__ = (UniqueConstraint('tenant_id', 'charge_reference', name='uq_bank_charge_reference'),)
    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    source_evidence = Column(String(64), unique=True)
    destination_evidence = Column(String(64), unique=True)
    charge_reference = Column(String(120), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    from_last4 = Column(String(4), nullable=False)
    to_last4 = Column(String(4), nullable=False)
    memo = Column(String(34), nullable=False)
    bank_state = Column(String(12))
    bank_effective_date = Column(Date)
    status = Column(String(40), nullable=False, default='reviewed')
    created_at = Column(DateTime(timezone=True), nullable=False)


class BankProfile(Base):
    """An independent consented login, including multiple logins at one institution."""
    __tablename__ = 'bank_profiles'
    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    name = Column(String(80), nullable=False)
    item_id = Column(String(150), nullable=False, unique=True)
    institution_id = Column(String(80), nullable=False)
    encrypted_access_token = Column(String(2048), nullable=False)
    legacy = Column(Boolean, nullable=False, default=False)
    status = Column(String(40), nullable=False, default='linked')
    last_error = Column(String(80))
    last_checked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False)


class BankAccountIdentity(Base):
    __tablename__ = 'bank_account_identities'
    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    institution_id = Column(String(80), nullable=False)
    name = Column(String(80), nullable=False)
    last4 = Column(String(4), nullable=False)
    kind = Column(String(20), nullable=False)
    reserve_cents = Column(Integer, nullable=False, default=0)


class BankProfileAccount(Base):
    __tablename__ = 'bank_profile_accounts'
    __table_args__ = (UniqueConstraint('profile_id', 'provider_account_id', name='uq_bank_profile_account'),)
    id = Column(String(36), primary_key=True)
    profile_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), index=True)  # Null until an overlapping account is resolved.
    provider_account_id = Column(String(150), nullable=False)
    name = Column(String(80), nullable=False)
    last4 = Column(String(4), nullable=False)
    kind = Column(String(20), nullable=False)
    subtype = Column(String(80))
    active = Column(Boolean, nullable=False, default=True)
    balance = Column(JSON, nullable=False, default=dict)


class BankProfileRoute(Base):
    __tablename__ = 'bank_profile_routes'
    __table_args__ = (UniqueConstraint('profile_id', 'source_id', 'destination_id', name='uq_bank_profile_route'),)
    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    profile_id = Column(String(36), nullable=False)
    source_id = Column(String(36), nullable=False)
    destination_id = Column(String(36), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)


class BankProfileDraft(Base):
    """Immutable account/profile binding alongside the existing transfer audit record."""
    __tablename__ = 'bank_profile_drafts'
    draft_id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    profile_id = Column(String(36), nullable=False)
    route_id = Column(String(36), nullable=False)
    source_id = Column(String(36), nullable=False)
    destination_id = Column(String(36), nullable=False)


class BankProfileLink(Base):
    __tablename__ = 'bank_profile_links'
    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    name = Column(String(80), nullable=False)
    profile_id = Column(String(36))
    token_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))


class BankProfileRun(Base):
    __tablename__ = 'bank_profile_runs'
    __table_args__ = (UniqueConstraint('profile_id', 'scheduled_date', name='uq_bank_profile_daily'),)
    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    profile_id = Column(String(36), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    status = Column(String(40), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
