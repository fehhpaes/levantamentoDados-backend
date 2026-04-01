"""
Integration tests for end-to-end workflows.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.match import Match
from app.models.prediction import Prediction
from app.models.odds import Bookmaker, Odds
from app.models.webhook import Webhook, WebhookStatus
from app.models.sport import Team, League, Sport

pytestmark = pytest.mark.asyncio


class TestMatchPredictionWorkflow:
    """
    Integration tests for the complete match prediction workflow:
    1. Create teams, league, and match
    2. Add odds from bookmakers
    3. Generate prediction
    4. Record result
    5. Evaluate prediction accuracy
    """

    @pytest.fixture
    async def setup_workflow(self, test_db: AsyncSession):
        """Set up full workflow data."""
        # Create sport
        sport = Sport(name="Football", slug="football")
        test_db.add(sport)
        await test_db.commit()
        await test_db.refresh(sport)
        
        # Create league
        league = League(
            name="Premier League",
            country="England",
            sport_id=sport.id
        )
        test_db.add(league)
        await test_db.commit()
        await test_db.refresh(league)
        
        # Create teams
        home_team = Team(name="Manchester United", sport_id=sport.id)
        away_team = Team(name="Liverpool", sport_id=sport.id)
        test_db.add_all([home_team, away_team])
        await test_db.commit()
        await test_db.refresh(home_team)
        await test_db.refresh(away_team)
        
        # Create bookmaker
        bookmaker = Bookmaker(
            name="Bet365",
            slug="bet365",
            is_active=True
        )
        test_db.add(bookmaker)
        await test_db.commit()
        await test_db.refresh(bookmaker)
        
        return {
            "sport": sport,
            "league": league,
            "home_team": home_team,
            "away_team": away_team,
            "bookmaker": bookmaker
        }

    async def test_complete_prediction_workflow(
        self, client: AsyncClient, setup_workflow, test_db: AsyncSession
    ):
        """Test complete workflow from match creation to result evaluation."""
        data = setup_workflow
        
        # Step 1: Create a match
        match_data = {
            "home_team_id": data["home_team"].id,
            "away_team_id": data["away_team"].id,
            "league_id": data["league"].id,
            "match_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "status": "scheduled"
        }
        
        response = await client.post("/api/v1/matches/", json=match_data)
        assert response.status_code == 201
        match = response.json()
        match_id = match["id"]
        
        # Step 2: Add odds
        odds_data = {
            "match_id": match_id,
            "bookmaker_id": data["bookmaker"].id,
            "market_type": "1X2",
            "home_odds": 2.10,
            "draw_odds": 3.50,
            "away_odds": 3.20
        }
        
        response = await client.post("/api/v1/odds/", json=odds_data)
        assert response.status_code == 201
        
        # Step 3: Create prediction
        prediction_data = {
            "match_id": match_id,
            "model_name": "poisson",
            "home_win_prob": 0.45,
            "draw_prob": 0.25,
            "away_win_prob": 0.30,
            "confidence_score": 0.75,
            "expected_value": 8.5,
            "recommended_bet": "home_win"
        }
        
        response = await client.post("/api/v1/predictions/", json=prediction_data)
        assert response.status_code == 201
        prediction = response.json()
        prediction_id = prediction["id"]
        
        # Step 4: Match finishes, update score
        score_update = {
            "home_score": 2,
            "away_score": 1,
            "status": "finished"
        }
        
        response = await client.put(
            f"/api/v1/matches/{match_id}/score",
            json=score_update
        )
        assert response.status_code == 200
        
        # Step 5: Record prediction result
        result_data = {
            "actual_home_score": 2,
            "actual_away_score": 1,
            "bet_outcome": "won",
            "profit_loss": 110.0  # Won at 2.10 odds
        }
        
        response = await client.post(
            f"/api/v1/predictions/{prediction_id}/result",
            json=result_data
        )
        assert response.status_code == 201
        result = response.json()
        
        # Verify prediction was correct (home win predicted, home won)
        assert result["actual_result"] == "home"
        assert result["result_correct"] is True
        assert result["profit_loss"] == 110.0


class TestValueBetWorkflow:
    """
    Integration tests for value bet detection workflow:
    1. Set up match with odds
    2. Generate prediction with high confidence
    3. Detect value bet
    4. Verify webhook notification
    """

    @pytest.fixture
    async def setup_value_bet(self, test_db: AsyncSession):
        """Set up data for value bet testing."""
        sport = Sport(name="Football", slug="football")
        test_db.add(sport)
        await test_db.commit()
        await test_db.refresh(sport)
        
        league = League(name="Test League", country="Test", sport_id=sport.id)
        test_db.add(league)
        
        team_a = Team(name="Team A", sport_id=sport.id)
        team_b = Team(name="Team B", sport_id=sport.id)
        test_db.add_all([team_a, team_b])
        
        bookmaker = Bookmaker(name="Test Book", slug="test-book", is_active=True)
        test_db.add(bookmaker)
        
        # Create webhook for value bet notifications
        webhook = Webhook(
            name="Value Bet Notifier",
            url="https://example.com/webhook",
            events=["value_bet_found"],
            is_active=True
        )
        test_db.add(webhook)
        
        await test_db.commit()
        
        for obj in [league, team_a, team_b, bookmaker, webhook]:
            await test_db.refresh(obj)
        
        return {
            "sport": sport,
            "league": league,
            "team_a": team_a,
            "team_b": team_b,
            "bookmaker": bookmaker,
            "webhook": webhook
        }

    async def test_value_bet_detection(
        self, client: AsyncClient, setup_value_bet, test_db: AsyncSession
    ):
        """Test value bet detection and notification."""
        data = setup_value_bet
        
        # Create match
        match = Match(
            home_team_id=data["team_a"].id,
            away_team_id=data["team_b"].id,
            league_id=data["league"].id,
            match_date=datetime.utcnow() + timedelta(hours=2),
            status="scheduled"
        )
        test_db.add(match)
        await test_db.commit()
        await test_db.refresh(match)
        
        # Add odds with value opportunity
        # Bookmaker gives 2.50 for home, but our model predicts 50% (should be 2.00)
        odds = Odds(
            match_id=match.id,
            bookmaker_id=data["bookmaker"].id,
            market_type="1X2",
            home_odds=2.50,  # Higher than fair odds
            draw_odds=3.00,
            away_odds=2.80,
            is_value_bet=True,
            value_percentage=10.0  # 10% edge
        )
        test_db.add(odds)
        await test_db.commit()
        
        # Query value bets
        response = await client.get(
            "/api/v1/odds/value-bets",
            params={"min_edge": 5.0}
        )
        
        assert response.status_code == 200
        value_bets = response.json()
        assert len(value_bets) >= 1
        assert value_bets[0]["edge_percentage"] == 10.0


class TestOddsComparisonWorkflow:
    """
    Integration tests for odds comparison workflow:
    1. Add odds from multiple bookmakers
    2. Compare and find best odds
    3. Track odds movements
    """

    @pytest.fixture
    async def setup_odds_comparison(self, test_db: AsyncSession):
        """Set up multiple bookmakers and a match."""
        sport = Sport(name="Football", slug="football")
        test_db.add(sport)
        await test_db.commit()
        await test_db.refresh(sport)
        
        league = League(name="Test League", country="Test", sport_id=sport.id)
        team_a = Team(name="Team A", sport_id=sport.id)
        team_b = Team(name="Team B", sport_id=sport.id)
        test_db.add_all([league, team_a, team_b])
        
        # Create multiple bookmakers
        bookmakers = []
        for name in ["Bet365", "Betfair", "William Hill"]:
            b = Bookmaker(name=name, slug=name.lower().replace(" ", "-"), is_active=True)
            test_db.add(b)
            bookmakers.append(b)
        
        await test_db.commit()
        
        for b in bookmakers:
            await test_db.refresh(b)
        await test_db.refresh(league)
        await test_db.refresh(team_a)
        await test_db.refresh(team_b)
        
        # Create match
        match = Match(
            home_team_id=team_a.id,
            away_team_id=team_b.id,
            league_id=league.id,
            match_date=datetime.utcnow() + timedelta(days=1),
            status="scheduled"
        )
        test_db.add(match)
        await test_db.commit()
        await test_db.refresh(match)
        
        return {
            "match": match,
            "bookmakers": bookmakers
        }

    async def test_odds_comparison_workflow(
        self, client: AsyncClient, setup_odds_comparison
    ):
        """Test comparing odds across bookmakers."""
        data = setup_odds_comparison
        match = data["match"]
        bookmakers = data["bookmakers"]
        
        # Add odds from each bookmaker (different odds)
        odds_values = [
            (2.10, 3.50, 3.20),  # Bet365
            (2.15, 3.40, 3.25),  # Betfair - best home
            (2.05, 3.60, 3.15),  # William Hill - best draw
        ]
        
        for bookmaker, (home, draw, away) in zip(bookmakers, odds_values):
            odds_data = {
                "match_id": match.id,
                "bookmaker_id": bookmaker.id,
                "market_type": "1X2",
                "home_odds": home,
                "draw_odds": draw,
                "away_odds": away
            }
            response = await client.post("/api/v1/odds/", json=odds_data)
            assert response.status_code == 201
        
        # Compare odds
        response = await client.get(
            f"/api/v1/odds/match/{match.id}/comparison",
            params={"market_type": "1X2"}
        )
        
        assert response.status_code == 200
        comparison = response.json()
        
        # Verify best odds are identified
        assert comparison["best_home_odds"]["odds"] == 2.15
        assert comparison["best_home_odds"]["bookmaker"] == "Betfair"
        assert comparison["best_draw_odds"]["odds"] == 3.60
        assert comparison["best_draw_odds"]["bookmaker"] == "William Hill"


class TestWebhookNotificationWorkflow:
    """
    Integration tests for webhook notification workflow.
    """

    async def test_webhook_creation_and_test(
        self, client: AsyncClient, sample_webhook_data
    ):
        """Test creating a webhook and testing it."""
        # Create webhook
        response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        assert response.status_code == 201
        webhook = response.json()
        webhook_id = webhook["id"]
        
        # Test the webhook (mocked)
        with patch("app.services.webhook.WebhookService.test_webhook") as mock_test:
            mock_test.return_value = {
                "success": True,
                "status_code": 200,
                "response_time_ms": 150.0,
                "error": None
            }
            
            response = await client.post(f"/api/v1/webhooks/{webhook_id}/test")
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True


class TestLiveMatchWorkflow:
    """
    Integration tests for live match updates.
    """

    @pytest.fixture
    async def setup_live_match(self, test_db: AsyncSession):
        """Set up a live match."""
        sport = Sport(name="Football", slug="football")
        test_db.add(sport)
        await test_db.commit()
        await test_db.refresh(sport)
        
        league = League(name="Test League", country="Test", sport_id=sport.id)
        team_a = Team(name="Home FC", sport_id=sport.id)
        team_b = Team(name="Away FC", sport_id=sport.id)
        test_db.add_all([league, team_a, team_b])
        await test_db.commit()
        
        for obj in [league, team_a, team_b]:
            await test_db.refresh(obj)
        
        # Create live match
        match = Match(
            home_team_id=team_a.id,
            away_team_id=team_b.id,
            league_id=league.id,
            match_date=datetime.utcnow() - timedelta(minutes=30),
            status="live",
            home_score=1,
            away_score=0
        )
        test_db.add(match)
        await test_db.commit()
        await test_db.refresh(match)
        
        return match

    async def test_live_match_score_updates(
        self, client: AsyncClient, setup_live_match
    ):
        """Test live match score update workflow."""
        match = setup_live_match
        
        # Get live matches
        response = await client.get("/api/v1/matches/live")
        assert response.status_code == 200
        live_matches = response.json()
        assert len(live_matches) >= 1
        
        # Update score - goal scored
        score_update = {
            "home_score": 2,
            "away_score": 0
        }
        
        response = await client.put(
            f"/api/v1/matches/{match.id}/score",
            json=score_update
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["home_score"] == 2
        
        # Add match event
        event_data = {
            "match_id": match.id,
            "event_type": "goal",
            "minute": 45,
            "team_id": match.home_team_id,
            "player_name": "Goal Scorer"
        }
        
        response = await client.post(
            f"/api/v1/matches/{match.id}/events",
            json=event_data
        )
        assert response.status_code == 201
        
        # Update to halftime
        halftime_update = {
            "home_score": 2,
            "away_score": 0,
            "home_score_ht": 2,
            "away_score_ht": 0,
            "status": "halftime"
        }
        
        response = await client.put(
            f"/api/v1/matches/{match.id}/score",
            json=halftime_update
        )
        assert response.status_code == 200
        
        # Get match details
        response = await client.get(f"/api/v1/matches/{match.id}")
        assert response.status_code == 200
        details = response.json()
        assert details["home_score_ht"] == 2


class TestBacktestingWorkflow:
    """
    Integration tests for backtesting workflow.
    """

    async def test_historical_prediction_analysis(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        """Test analyzing historical prediction performance."""
        # This would test the full backtest workflow
        # Including strategy creation, historical match analysis,
        # and performance reporting
        
        # Get model performance (even if empty)
        response = await client.get("/api/v1/predictions/models/performance")
        assert response.status_code == 200


class TestDataExportWorkflow:
    """
    Integration tests for data export functionality.
    """

    async def test_export_workflow(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        """Test exporting match and prediction data."""
        # Set up some data first
        sport = Sport(name="Football", slug="football")
        test_db.add(sport)
        await test_db.commit()
        await test_db.refresh(sport)
        
        league = League(name="Test League", country="Test", sport_id=sport.id)
        team_a = Team(name="Team A", sport_id=sport.id)
        team_b = Team(name="Team B", sport_id=sport.id)
        test_db.add_all([league, team_a, team_b])
        await test_db.commit()
        
        for obj in [league, team_a, team_b]:
            await test_db.refresh(obj)
        
        # Create finished matches
        for i in range(3):
            match = Match(
                home_team_id=team_a.id,
                away_team_id=team_b.id,
                league_id=league.id,
                match_date=datetime.utcnow() - timedelta(days=i * 7),
                status="finished",
                home_score=2,
                away_score=1
            )
            test_db.add(match)
        await test_db.commit()
        
        # Query matches (would be part of export)
        response = await client.get(
            "/api/v1/matches/",
            params={"status": "finished", "limit": 100}
        )
        assert response.status_code == 200
        matches = response.json()
        assert len(matches) == 3
