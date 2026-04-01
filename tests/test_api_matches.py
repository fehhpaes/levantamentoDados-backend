"""
Tests for Matches API endpoints.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.match import Match
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
        match_date=datetime.utcnow() + timedelta(days=1),
        status="scheduled"
    )
    test_db.add(match)
    await test_db.commit()
    await test_db.refresh(match)
    return match


class TestMatchesList:
    """Tests for listing matches."""

    async def test_list_matches_empty(self, client: AsyncClient):
        """Test listing matches when none exist."""
        response = await client.get("/api/v1/matches/")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_list_matches(self, client: AsyncClient, test_match):
        """Test listing matches."""
        response = await client.get("/api/v1/matches/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_list_matches_filter_by_league(
        self, client: AsyncClient, test_match, test_league
    ):
        """Test filtering matches by league."""
        response = await client.get(
            "/api/v1/matches/",
            params={"league_id": test_league.id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_list_matches_filter_by_status(
        self, client: AsyncClient, test_match
    ):
        """Test filtering matches by status."""
        response = await client.get(
            "/api/v1/matches/",
            params={"status": "scheduled"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        response = await client.get(
            "/api/v1/matches/",
            params={"status": "finished"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    async def test_list_matches_filter_by_date_range(
        self, client: AsyncClient, test_match
    ):
        """Test filtering matches by date range."""
        # Tomorrow matches should be found
        date_from = datetime.utcnow()
        date_to = datetime.utcnow() + timedelta(days=2)
        
        response = await client.get(
            "/api/v1/matches/",
            params={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat()
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_list_matches_pagination(
        self, client: AsyncClient, test_db: AsyncSession, test_teams, test_league
    ):
        """Test match list pagination."""
        team_a, team_b = test_teams
        
        # Create multiple matches
        for i in range(5):
            match = Match(
                home_team_id=team_a.id,
                away_team_id=team_b.id,
                league_id=test_league.id,
                match_date=datetime.utcnow() + timedelta(days=i),
                status="scheduled"
            )
            test_db.add(match)
        await test_db.commit()
        
        # Test limit
        response = await client.get("/api/v1/matches/", params={"limit": 2})
        assert len(response.json()) == 2
        
        # Test skip
        response = await client.get("/api/v1/matches/", params={"skip": 3})
        assert len(response.json()) == 2


class TestMatchCreate:
    """Tests for creating matches."""

    async def test_create_match(
        self, client: AsyncClient, test_teams, test_league, sample_match_data
    ):
        """Test creating a match."""
        team_a, team_b = test_teams
        sample_match_data["home_team_id"] = team_a.id
        sample_match_data["away_team_id"] = team_b.id
        sample_match_data["league_id"] = test_league.id
        del sample_match_data["home_team_name"]
        del sample_match_data["away_team_name"]
        
        response = await client.post("/api/v1/matches/", json=sample_match_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "scheduled"
        assert "id" in data


class TestMatchDetails:
    """Tests for match details."""

    async def test_get_match_details(self, client: AsyncClient, test_match):
        """Test getting match details."""
        response = await client.get(f"/api/v1/matches/{test_match.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_match.id
        assert data["status"] == "scheduled"

    async def test_get_match_not_found(self, client: AsyncClient):
        """Test getting non-existent match."""
        response = await client.get("/api/v1/matches/99999")
        
        assert response.status_code == 404


class TestMatchScore:
    """Tests for updating match scores."""

    async def test_update_score(
        self, client: AsyncClient, test_match, test_db: AsyncSession
    ):
        """Test updating match score."""
        update_data = {
            "home_score": 2,
            "away_score": 1,
            "status": "finished"
        }
        
        response = await client.put(
            f"/api/v1/matches/{test_match.id}/score",
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["home_score"] == 2
        assert data["away_score"] == 1
        assert data["status"] == "finished"

    async def test_update_score_halftime(
        self, client: AsyncClient, test_match
    ):
        """Test updating half-time score."""
        update_data = {
            "home_score": 1,
            "away_score": 0,
            "home_score_ht": 1,
            "away_score_ht": 0,
            "status": "halftime"
        }
        
        response = await client.put(
            f"/api/v1/matches/{test_match.id}/score",
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["home_score_ht"] == 1
        assert data["away_score_ht"] == 0

    async def test_update_score_not_found(self, client: AsyncClient):
        """Test updating score for non-existent match."""
        response = await client.put(
            "/api/v1/matches/99999/score",
            json={"home_score": 1, "away_score": 0}
        )
        
        assert response.status_code == 404


class TestMatchStatistics:
    """Tests for match statistics."""

    async def test_add_statistics(self, client: AsyncClient, test_match):
        """Test adding match statistics."""
        stats_data = {
            "match_id": test_match.id,
            "home_possession": 55.0,
            "away_possession": 45.0,
            "home_shots": 12,
            "away_shots": 8,
            "home_shots_on_target": 5,
            "away_shots_on_target": 3,
            "home_corners": 6,
            "away_corners": 4
        }
        
        response = await client.post(
            f"/api/v1/matches/{test_match.id}/statistics",
            json=stats_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["home_possession"] == 55.0
        assert data["home_shots"] == 12

    async def test_update_statistics(self, client: AsyncClient, test_match):
        """Test updating existing statistics."""
        # Add initial statistics
        stats_data = {
            "match_id": test_match.id,
            "home_possession": 50.0,
            "away_possession": 50.0,
        }
        await client.post(
            f"/api/v1/matches/{test_match.id}/statistics",
            json=stats_data
        )
        
        # Update statistics
        updated_data = {
            "match_id": test_match.id,
            "home_possession": 60.0,
            "away_possession": 40.0,
        }
        response = await client.post(
            f"/api/v1/matches/{test_match.id}/statistics",
            json=updated_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["home_possession"] == 60.0


class TestMatchEvents:
    """Tests for match events."""

    async def test_add_event(self, client: AsyncClient, test_match, test_teams):
        """Test adding a match event."""
        team_a, _ = test_teams
        event_data = {
            "match_id": test_match.id,
            "event_type": "goal",
            "minute": 35,
            "team_id": team_a.id,
            "player_name": "John Doe"
        }
        
        response = await client.post(
            f"/api/v1/matches/{test_match.id}/events",
            json=event_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == "goal"
        assert data["minute"] == 35

    async def test_add_card_event(self, client: AsyncClient, test_match, test_teams):
        """Test adding a card event."""
        _, team_b = test_teams
        event_data = {
            "match_id": test_match.id,
            "event_type": "yellow_card",
            "minute": 60,
            "team_id": team_b.id,
            "player_name": "Jane Smith"
        }
        
        response = await client.post(
            f"/api/v1/matches/{test_match.id}/events",
            json=event_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == "yellow_card"


class TestLiveMatches:
    """Tests for live matches endpoint."""

    async def test_get_live_matches_empty(self, client: AsyncClient):
        """Test getting live matches when none are live."""
        response = await client.get("/api/v1/matches/live")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    async def test_get_live_matches(
        self, client: AsyncClient, test_db: AsyncSession, test_teams, test_league
    ):
        """Test getting live matches."""
        team_a, team_b = test_teams
        
        # Create a live match
        match = Match(
            home_team_id=team_a.id,
            away_team_id=team_b.id,
            league_id=test_league.id,
            match_date=datetime.utcnow(),
            status="live"
        )
        test_db.add(match)
        await test_db.commit()
        
        response = await client.get("/api/v1/matches/live")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestTodayMatches:
    """Tests for today's matches endpoint."""

    async def test_get_today_matches(
        self, client: AsyncClient, test_db: AsyncSession, test_teams, test_league
    ):
        """Test getting today's matches."""
        team_a, team_b = test_teams
        
        # Create a match for today
        today = datetime.utcnow().replace(hour=20, minute=0, second=0, microsecond=0)
        match = Match(
            home_team_id=team_a.id,
            away_team_id=team_b.id,
            league_id=test_league.id,
            match_date=today,
            status="scheduled"
        )
        test_db.add(match)
        await test_db.commit()
        
        response = await client.get("/api/v1/matches/today")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1


class TestHeadToHead:
    """Tests for head-to-head history."""

    async def test_get_h2h(
        self, client: AsyncClient, test_db: AsyncSession, test_match, test_teams, test_league
    ):
        """Test getting head-to-head history."""
        team_a, team_b = test_teams
        
        # Create finished matches between the teams
        for i in range(3):
            finished_match = Match(
                home_team_id=team_a.id,
                away_team_id=team_b.id,
                league_id=test_league.id,
                match_date=datetime.utcnow() - timedelta(days=30 * (i + 1)),
                status="finished",
                home_score=2,
                away_score=1
            )
            test_db.add(finished_match)
        await test_db.commit()
        
        response = await client.get(f"/api/v1/matches/{test_match.id}/head-to-head")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_get_h2h_not_found(self, client: AsyncClient):
        """Test H2H for non-existent match."""
        response = await client.get("/api/v1/matches/99999/head-to-head")
        
        assert response.status_code == 404
