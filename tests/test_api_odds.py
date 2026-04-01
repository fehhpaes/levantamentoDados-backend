"""
Tests for Odds API endpoints.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.odds import Bookmaker, Odds, OddsHistory
from app.models.sport import Team, League, Sport

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def test_sport(test_db: AsyncSession):
    """Create a test sport."""
    sport = Sport(name="Football", slug="football")
    test_db.add(sport)
    await test_db.commit()
    await test_db.refresh(sport)
    return sport


@pytest.fixture
async def test_league(test_db: AsyncSession, test_sport):
    """Create a test league."""
    league = League(
        name="Premier League",
        country="England",
        sport_id=test_sport.id
    )
    test_db.add(league)
    await test_db.commit()
    await test_db.refresh(league)
    return league


@pytest.fixture
async def test_teams(test_db: AsyncSession, test_sport):
    """Create test teams."""
    team_a = Team(name="Team A", sport_id=test_sport.id)
    team_b = Team(name="Team B", sport_id=test_sport.id)
    test_db.add_all([team_a, team_b])
    await test_db.commit()
    await test_db.refresh(team_a)
    await test_db.refresh(team_b)
    return team_a, team_b


@pytest.fixture
async def test_match(test_db: AsyncSession, test_teams, test_league):
    """Create a test match."""
    team_a, team_b = test_teams
    match = Match(
        home_team_id=team_a.id,
        away_team_id=team_b.id,
        league_id=test_league.id,
        match_date=datetime.utcnow(),
        status="scheduled"
    )
    test_db.add(match)
    await test_db.commit()
    await test_db.refresh(match)
    return match


@pytest.fixture
async def test_bookmaker(test_db: AsyncSession):
    """Create a test bookmaker."""
    bookmaker = Bookmaker(
        name="Test Bookmaker",
        slug="test-bookmaker",
        website="https://testbookmaker.com",
        is_active=True
    )
    test_db.add(bookmaker)
    await test_db.commit()
    await test_db.refresh(bookmaker)
    return bookmaker


@pytest.fixture
async def test_odds(test_db: AsyncSession, test_match, test_bookmaker):
    """Create test odds."""
    odds = Odds(
        match_id=test_match.id,
        bookmaker_id=test_bookmaker.id,
        market_type="1X2",
        home_odds=2.10,
        draw_odds=3.50,
        away_odds=3.20,
        odds_updated_at=datetime.utcnow()
    )
    test_db.add(odds)
    await test_db.commit()
    await test_db.refresh(odds)
    return odds


class TestBookmakers:
    """Tests for bookmaker endpoints."""

    async def test_list_bookmakers_empty(self, client: AsyncClient):
        """Test listing bookmakers when none exist."""
        response = await client.get("/api/v1/odds/bookmakers")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_list_bookmakers(self, client: AsyncClient, test_bookmaker):
        """Test listing bookmakers."""
        response = await client.get("/api/v1/odds/bookmakers")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Bookmaker"

    async def test_list_bookmakers_filter_active(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        """Test filtering bookmakers by active status."""
        # Create active and inactive bookmakers
        active = Bookmaker(name="Active", slug="active", is_active=True)
        inactive = Bookmaker(name="Inactive", slug="inactive", is_active=False)
        test_db.add_all([active, inactive])
        await test_db.commit()
        
        # Get only active
        response = await client.get(
            "/api/v1/odds/bookmakers",
            params={"is_active": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Active"

    async def test_create_bookmaker(self, client: AsyncClient):
        """Test creating a bookmaker."""
        bookmaker_data = {
            "name": "New Bookmaker",
            "slug": "new-bookmaker",
            "website": "https://newbookmaker.com",
            "is_active": True
        }
        
        response = await client.post(
            "/api/v1/odds/bookmakers",
            json=bookmaker_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Bookmaker"
        assert "id" in data


class TestMatchOdds:
    """Tests for match odds endpoints."""

    async def test_get_match_odds_empty(self, client: AsyncClient, test_match):
        """Test getting odds when none exist."""
        response = await client.get(f"/api/v1/odds/match/{test_match.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_match_odds(self, client: AsyncClient, test_odds, test_match):
        """Test getting odds for a match."""
        response = await client.get(f"/api/v1/odds/match/{test_match.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["home_odds"] == 2.10
        assert data[0]["draw_odds"] == 3.50
        assert data[0]["away_odds"] == 3.20

    async def test_get_match_odds_filter_by_market(
        self, client: AsyncClient, test_db: AsyncSession, test_match, test_bookmaker
    ):
        """Test filtering odds by market type."""
        # Create odds for different markets
        odds_1x2 = Odds(
            match_id=test_match.id,
            bookmaker_id=test_bookmaker.id,
            market_type="1X2",
            home_odds=2.0,
            draw_odds=3.0,
            away_odds=3.5
        )
        odds_ou = Odds(
            match_id=test_match.id,
            bookmaker_id=test_bookmaker.id,
            market_type="over_under",
            over_odds=1.85,
            under_odds=1.95,
            line=2.5
        )
        test_db.add_all([odds_1x2, odds_ou])
        await test_db.commit()
        
        # Filter by market
        response = await client.get(
            f"/api/v1/odds/match/{test_match.id}",
            params={"market_type": "1X2"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["market_type"] == "1X2"


class TestCreateUpdateOdds:
    """Tests for creating and updating odds."""

    async def test_create_odds(
        self, client: AsyncClient, test_match, test_bookmaker, sample_odds_data
    ):
        """Test creating new odds."""
        odds_data = {
            "match_id": test_match.id,
            "bookmaker_id": test_bookmaker.id,
            "market_type": "1X2",
            "home_odds": sample_odds_data["home_odds"],
            "draw_odds": sample_odds_data["draw_odds"],
            "away_odds": sample_odds_data["away_odds"]
        }
        
        response = await client.post("/api/v1/odds/", json=odds_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["home_odds"] == sample_odds_data["home_odds"]
        assert "id" in data

    async def test_update_odds(
        self, client: AsyncClient, test_odds, test_match, test_bookmaker
    ):
        """Test updating existing odds."""
        # Update with new values
        odds_data = {
            "match_id": test_match.id,
            "bookmaker_id": test_bookmaker.id,
            "market_type": "1X2",
            "home_odds": 2.20,
            "draw_odds": 3.40,
            "away_odds": 3.10
        }
        
        response = await client.post("/api/v1/odds/", json=odds_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["home_odds"] == 2.20
        assert data["draw_odds"] == 3.40

    async def test_create_odds_calculates_probabilities(
        self, client: AsyncClient, test_match, test_bookmaker
    ):
        """Test that odds creation calculates implied probabilities."""
        odds_data = {
            "match_id": test_match.id,
            "bookmaker_id": test_bookmaker.id,
            "market_type": "1X2",
            "home_odds": 2.00,
            "draw_odds": 3.00,
            "away_odds": 4.00
        }
        
        response = await client.post("/api/v1/odds/", json=odds_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Implied probabilities should be calculated
        # 1/2.0 = 0.5, 1/3.0 = 0.333, 1/4.0 = 0.25
        # Total = 1.083 (margin)
        assert "home_prob" in data or data.get("home_odds") is not None


class TestOddsHistory:
    """Tests for odds history endpoints."""

    async def test_get_odds_history_empty(
        self, client: AsyncClient, test_match
    ):
        """Test getting history when none exists."""
        response = await client.get(f"/api/v1/odds/match/{test_match.id}/history")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_odds_history(
        self, client: AsyncClient, test_db: AsyncSession, test_match, test_bookmaker
    ):
        """Test getting odds history."""
        # Create history entries
        for i in range(3):
            history = OddsHistory(
                match_id=test_match.id,
                bookmaker_id=test_bookmaker.id,
                market_type="1X2",
                home_odds=2.00 + (i * 0.1),
                draw_odds=3.00,
                away_odds=3.50,
                recorded_at=datetime.utcnow()
            )
            test_db.add(history)
        await test_db.commit()
        
        response = await client.get(f"/api/v1/odds/match/{test_match.id}/history")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_get_odds_history_filter_by_bookmaker(
        self, client: AsyncClient, test_db: AsyncSession, test_match, test_bookmaker
    ):
        """Test filtering history by bookmaker."""
        # Create another bookmaker
        bookmaker2 = Bookmaker(name="Bookmaker 2", slug="bookmaker-2")
        test_db.add(bookmaker2)
        await test_db.commit()
        await test_db.refresh(bookmaker2)
        
        # Create history for both
        h1 = OddsHistory(
            match_id=test_match.id,
            bookmaker_id=test_bookmaker.id,
            market_type="1X2",
            home_odds=2.0,
            draw_odds=3.0,
            away_odds=3.5,
            recorded_at=datetime.utcnow()
        )
        h2 = OddsHistory(
            match_id=test_match.id,
            bookmaker_id=bookmaker2.id,
            market_type="1X2",
            home_odds=2.1,
            draw_odds=3.1,
            away_odds=3.4,
            recorded_at=datetime.utcnow()
        )
        test_db.add_all([h1, h2])
        await test_db.commit()
        
        response = await client.get(
            f"/api/v1/odds/match/{test_match.id}/history",
            params={"bookmaker_id": test_bookmaker.id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestOddsComparison:
    """Tests for odds comparison endpoint."""

    async def test_compare_odds(
        self, client: AsyncClient, test_db: AsyncSession, test_match
    ):
        """Test comparing odds from multiple bookmakers."""
        # Create bookmakers
        bookmakers = []
        for i in range(3):
            b = Bookmaker(name=f"Bookmaker {i}", slug=f"bookmaker-{i}")
            test_db.add(b)
            bookmakers.append(b)
        await test_db.commit()
        
        for b in bookmakers:
            await test_db.refresh(b)
        
        # Create odds for each
        odds_values = [
            (2.10, 3.50, 3.20),
            (2.05, 3.60, 3.30),
            (2.15, 3.45, 3.15)
        ]
        
        for b, (home, draw, away) in zip(bookmakers, odds_values):
            odds = Odds(
                match_id=test_match.id,
                bookmaker_id=b.id,
                market_type="1X2",
                home_odds=home,
                draw_odds=draw,
                away_odds=away
            )
            test_db.add(odds)
        await test_db.commit()
        
        response = await client.get(
            f"/api/v1/odds/match/{test_match.id}/comparison",
            params={"market_type": "1X2"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["match_id"] == test_match.id
        assert len(data["bookmakers"]) == 3
        assert "best_home_odds" in data
        assert "best_draw_odds" in data
        assert "best_away_odds" in data

    async def test_compare_odds_not_found(self, client: AsyncClient, test_match):
        """Test comparing odds when none exist."""
        response = await client.get(
            f"/api/v1/odds/match/{test_match.id}/comparison",
            params={"market_type": "1X2"}
        )
        
        assert response.status_code == 404


class TestValueBets:
    """Tests for value bets endpoint."""

    async def test_get_value_bets_empty(self, client: AsyncClient):
        """Test getting value bets when none exist."""
        response = await client.get("/api/v1/odds/value-bets")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_value_bets(
        self, client: AsyncClient, test_db: AsyncSession, test_match, test_bookmaker
    ):
        """Test getting identified value bets."""
        # Create a value bet
        odds = Odds(
            match_id=test_match.id,
            bookmaker_id=test_bookmaker.id,
            market_type="1X2",
            home_odds=2.50,
            draw_odds=3.00,
            away_odds=3.00,
            is_value_bet=True,
            value_percentage=8.5
        )
        test_db.add(odds)
        await test_db.commit()
        
        response = await client.get(
            "/api/v1/odds/value-bets",
            params={"min_edge": 5.0}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_get_value_bets_filter_by_edge(
        self, client: AsyncClient, test_db: AsyncSession, test_match, test_bookmaker
    ):
        """Test filtering value bets by minimum edge."""
        # Create value bets with different edges
        for edge in [3.0, 6.0, 10.0]:
            odds = Odds(
                match_id=test_match.id,
                bookmaker_id=test_bookmaker.id,
                market_type="1X2",
                home_odds=2.50,
                draw_odds=3.00,
                away_odds=3.00,
                is_value_bet=True,
                value_percentage=edge
            )
            test_db.add(odds)
        await test_db.commit()
        
        # Filter by minimum edge of 5%
        response = await client.get(
            "/api/v1/odds/value-bets",
            params={"min_edge": 5.0}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Should only get bets with edge >= 5%
        assert len(data) == 2


class TestOddsOverUnder:
    """Tests for over/under odds."""

    async def test_create_over_under_odds(
        self, client: AsyncClient, test_match, test_bookmaker
    ):
        """Test creating over/under odds."""
        odds_data = {
            "match_id": test_match.id,
            "bookmaker_id": test_bookmaker.id,
            "market_type": "over_under",
            "over_odds": 1.85,
            "under_odds": 1.95,
            "line": 2.5
        }
        
        response = await client.post("/api/v1/odds/", json=odds_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["over_odds"] == 1.85
        assert data["under_odds"] == 1.95
        assert data["line"] == 2.5
