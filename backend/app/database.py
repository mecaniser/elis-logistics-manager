"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL - use PostgreSQL on Railway, SQLite locally
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./elisgroup.db"
)

# Handle Railway PostgreSQL URL format
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


@event.listens_for(Session, 'do_orm_execute')
def _active_repairs_by_default(state):
    """All ordinary lists/aggregates/relationships share the active-record rule.

    Explicit reconciliation/restoration reads can request archived originals;
    this is an archive projection, not a replacement for tenant authorization.
    """
    if state.is_select and state.is_orm_statement and not state.is_column_load and not state.execution_options.get('include_archived_repairs'):
        from app.models.repair import Repair
        state.statement = state.statement.options(with_loader_criteria(
            Repair, lambda repair: repair.archived_at.is_(None), include_aliases=True))

def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

