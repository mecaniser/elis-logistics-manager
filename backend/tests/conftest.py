"""
Pytest configuration and fixtures
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.auth_utils import SESSION_COOKIE_NAME, create_session_token
from app.main import app
from app.main import APP_AUTH_USERNAME
from app.models.tenant import Tenant

# Test database (in-memory SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(Tenant(id=1, name="Test Tenant", business_type="logistics"))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        if APP_AUTH_USERNAME:
            session_token = create_session_token(APP_AUTH_USERNAME)
            if session_token:
                test_client.cookies.set(SESSION_COOKIE_NAME, session_token)
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def tenant_headers():
    """Default tenant header for API requests."""
    return {"X-Tenant-ID": "1"}
