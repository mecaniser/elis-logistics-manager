"""Security state for the single configured ELIS application account."""
from sqlalchemy import BigInteger, Column, Integer, String, Text
from app.database import Base


class AuthAccount(Base):
    __tablename__ = "auth_account"

    id = Column(Integer, primary_key=True)
    password_hash = Column(Text, nullable=True)
    session_version = Column(Integer, nullable=False, default=0)
    reset_token_hash = Column(String(64), nullable=True)
    reset_expires_at = Column(BigInteger, nullable=True)
    reset_requested_at = Column(BigInteger, nullable=True)
    mfa_secret = Column(Text, nullable=True)
    mfa_pending_secret = Column(Text, nullable=True)
    recovery_code_hashes = Column(Text, nullable=True)
    failed_login_count = Column(Integer, nullable=False, default=0)
    login_retry_after = Column(BigInteger, nullable=True)
