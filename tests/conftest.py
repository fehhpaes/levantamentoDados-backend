"""
Test configuration and fixtures.
"""

import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.config import settings
from main import app


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create test engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    TestSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with TestSessionLocal() as session:
        yield session
    
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client."""
    
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_match_data():
    """Sample match data for testing."""
    return {
        "external_id": "test_match_1",
        "home_team_name": "Team A",
        "away_team_name": "Team B",
        "match_date": "2024-06-15T15:00:00",
        "status": "scheduled",
        "venue": "Stadium A"
    }


@pytest.fixture
def sample_prediction_data():
    """Sample prediction data for testing."""
    return {
        "home_win_prob": 0.45,
        "draw_prob": 0.25,
        "away_win_prob": 0.30,
        "confidence": 0.75,
        "over_25_prob": 0.55,
        "btts_prob": 0.60
    }


@pytest.fixture
def sample_odds_data():
    """Sample odds data for testing."""
    return {
        "bookmaker_name": "Test Bookmaker",
        "home_odds": 2.10,
        "draw_odds": 3.50,
        "away_odds": 3.20,
        "over_25": 1.85,
        "under_25": 1.95
    }


@pytest.fixture
def sample_webhook_data():
    """Sample webhook data for testing."""
    return {
        "name": "Test Webhook",
        "url": "https://example.com/webhook",
        "secret": "test-secret-key",
        "events": ["value_bet_found", "prediction_ready"],
        "max_retries": 3,
        "retry_delay": 60
    }


@pytest.fixture
def sample_strategy_data():
    """Sample backtest strategy data for testing."""
    return {
        "name": "Test Strategy",
        "strategy_type": "value_betting",
        "min_edge": 0.05,
        "min_odds": 1.5,
        "max_odds": 5.0,
        "min_confidence": 0.6,
        "base_stake": 100,
        "max_stake": 500,
        "markets": ["1X2"]
    }
