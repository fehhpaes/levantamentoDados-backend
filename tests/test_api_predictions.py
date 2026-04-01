"""
Tests for Predictions API endpoints.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.prediction import Prediction, PredictionResult
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


@pytest.fixture
async def test_prediction(test_db: AsyncSession, test_match):
    """Create a test prediction."""
    prediction = Prediction(
        match_id=test_match.id,
        model_name="poisson",
        home_win_prob=0.45,
        draw_prob=0.25,
        away_win_prob=0.30,
        confidence_score=0.75,
        over_25_prob=0.55,
        btts_prob=0.60,
        expected_value=8.5,
        recommended_bet="home_win"
    )
    test_db.add(prediction)
    await test_db.commit()
    await test_db.refresh(prediction)
    return prediction


class TestPredictionsByMatch:
    """Tests for getting predictions by match."""

    async def test_get_match_predictions_empty(
        self, client: AsyncClient, test_match
    ):
        """Test getting predictions when none exist."""
        response = await client.get(
            f"/api/v1/predictions/match/{test_match.id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_match_predictions(
        self, client: AsyncClient, test_match, test_prediction
    ):
        """Test getting predictions for a match."""
        response = await client.get(
            f"/api/v1/predictions/match/{test_match.id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["model_name"] == "poisson"
        assert data[0]["home_win_prob"] == 0.45

    async def test_get_match_predictions_filter_by_model(
        self, client: AsyncClient, test_db: AsyncSession, test_match
    ):
        """Test filtering predictions by model name."""
        # Create predictions from different models
        models = ["poisson", "elo", "xgboost"]
        for model in models:
            pred = Prediction(
                match_id=test_match.id,
                model_name=model,
                home_win_prob=0.40,
                draw_prob=0.30,
                away_win_prob=0.30,
                confidence_score=0.7
            )
            test_db.add(pred)
        await test_db.commit()
        
        # Filter by specific model
        response = await client.get(
            f"/api/v1/predictions/match/{test_match.id}",
            params={"model_name": "poisson"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["model_name"] == "poisson"


class TestCreatePrediction:
    """Tests for creating predictions."""

    async def test_create_prediction(
        self, client: AsyncClient, test_match, sample_prediction_data
    ):
        """Test creating a new prediction."""
        prediction_data = {
            "match_id": test_match.id,
            "model_name": "elo",
            **sample_prediction_data
        }
        
        response = await client.post(
            "/api/v1/predictions/",
            json=prediction_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["match_id"] == test_match.id
        assert data["model_name"] == "elo"
        assert data["home_win_prob"] == sample_prediction_data["home_win_prob"]

    async def test_create_prediction_invalid_match(
        self, client: AsyncClient, sample_prediction_data
    ):
        """Test creating prediction for non-existent match."""
        prediction_data = {
            "match_id": 99999,
            "model_name": "elo",
            **sample_prediction_data
        }
        
        response = await client.post(
            "/api/v1/predictions/",
            json=prediction_data
        )
        
        assert response.status_code == 404

    async def test_create_prediction_with_features(
        self, client: AsyncClient, test_match, sample_prediction_data
    ):
        """Test creating prediction with features used."""
        prediction_data = {
            "match_id": test_match.id,
            "model_name": "xgboost",
            "features_used": ["home_form", "away_form", "h2h_stats"],
            "prediction_details": {"feature_importance": {"home_form": 0.3}},
            **sample_prediction_data
        }
        
        response = await client.post(
            "/api/v1/predictions/",
            json=prediction_data
        )
        
        assert response.status_code == 201


class TestPredictionResults:
    """Tests for recording prediction results."""

    async def test_record_result_home_win(
        self, client: AsyncClient, test_prediction
    ):
        """Test recording a prediction result with home win."""
        result_data = {
            "actual_home_score": 2,
            "actual_away_score": 1
        }
        
        response = await client.post(
            f"/api/v1/predictions/{test_prediction.id}/result",
            json=result_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["actual_home_score"] == 2
        assert data["actual_away_score"] == 1
        assert data["actual_result"] == "home"
        assert data["result_correct"] is True  # Home was predicted

    async def test_record_result_away_win(
        self, client: AsyncClient, test_db: AsyncSession, test_match
    ):
        """Test recording a prediction result with away win."""
        # Create prediction favoring away
        prediction = Prediction(
            match_id=test_match.id,
            model_name="test",
            home_win_prob=0.20,
            draw_prob=0.30,
            away_win_prob=0.50,
            confidence_score=0.8
        )
        test_db.add(prediction)
        await test_db.commit()
        await test_db.refresh(prediction)
        
        result_data = {
            "actual_home_score": 0,
            "actual_away_score": 2
        }
        
        response = await client.post(
            f"/api/v1/predictions/{prediction.id}/result",
            json=result_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["actual_result"] == "away"
        assert data["result_correct"] is True

    async def test_record_result_draw(
        self, client: AsyncClient, test_db: AsyncSession, test_match
    ):
        """Test recording a prediction result with draw."""
        # Create prediction favoring draw
        prediction = Prediction(
            match_id=test_match.id,
            model_name="test",
            home_win_prob=0.30,
            draw_prob=0.45,
            away_win_prob=0.25,
            confidence_score=0.7
        )
        test_db.add(prediction)
        await test_db.commit()
        await test_db.refresh(prediction)
        
        result_data = {
            "actual_home_score": 1,
            "actual_away_score": 1
        }
        
        response = await client.post(
            f"/api/v1/predictions/{prediction.id}/result",
            json=result_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["actual_result"] == "draw"
        assert data["result_correct"] is True

    async def test_record_result_with_profit_loss(
        self, client: AsyncClient, test_prediction
    ):
        """Test recording result with profit/loss information."""
        result_data = {
            "actual_home_score": 2,
            "actual_away_score": 1,
            "bet_outcome": "won",
            "profit_loss": 50.0
        }
        
        response = await client.post(
            f"/api/v1/predictions/{test_prediction.id}/result",
            json=result_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["profit_loss"] == 50.0

    async def test_record_result_not_found(self, client: AsyncClient):
        """Test recording result for non-existent prediction."""
        response = await client.post(
            "/api/v1/predictions/99999/result",
            json={"actual_home_score": 1, "actual_away_score": 0}
        )
        
        assert response.status_code == 404


class TestModelPerformance:
    """Tests for model performance endpoints."""

    async def test_get_model_performance_empty(self, client: AsyncClient):
        """Test getting model performance when no results exist."""
        response = await client.get("/api/v1/predictions/models/performance")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_model_performance(
        self, client: AsyncClient, test_db: AsyncSession, test_match
    ):
        """Test getting model performance with results."""
        # Create predictions and results
        for i in range(3):
            prediction = Prediction(
                match_id=test_match.id,
                model_name="test_model",
                home_win_prob=0.50,
                draw_prob=0.25,
                away_win_prob=0.25,
                confidence_score=0.7
            )
            test_db.add(prediction)
            await test_db.commit()
            await test_db.refresh(prediction)
            
            result = PredictionResult(
                prediction_id=prediction.id,
                match_id=test_match.id,
                actual_home_score=2,
                actual_away_score=1,
                actual_result="home",
                result_correct=True,
                profit_loss=10.0
            )
            test_db.add(result)
        await test_db.commit()
        
        response = await client.get("/api/v1/predictions/models/performance")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_get_model_performance_filter_by_model(
        self, client: AsyncClient
    ):
        """Test filtering model performance by model name."""
        response = await client.get(
            "/api/v1/predictions/models/performance",
            params={"model_name": "poisson"}
        )
        
        assert response.status_code == 200


class TestValueBets:
    """Tests for value bets endpoint."""

    async def test_get_value_bets_empty(self, client: AsyncClient):
        """Test getting value bets when none qualify."""
        response = await client.get("/api/v1/predictions/value-bets")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_get_value_bets(
        self, client: AsyncClient, test_db: AsyncSession, test_match
    ):
        """Test getting value bets."""
        # Create a prediction with high EV
        prediction = Prediction(
            match_id=test_match.id,
            model_name="value_model",
            home_win_prob=0.50,
            draw_prob=0.25,
            away_win_prob=0.25,
            confidence_score=0.85,
            expected_value=12.0,
            recommended_bet="home_win @2.50"
        )
        test_db.add(prediction)
        await test_db.commit()
        
        response = await client.get(
            "/api/v1/predictions/value-bets",
            params={"min_confidence": 0.8, "min_edge": 10.0}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_get_value_bets_with_filters(self, client: AsyncClient):
        """Test value bets with confidence and edge filters."""
        response = await client.get(
            "/api/v1/predictions/value-bets",
            params={"min_confidence": 0.7, "min_edge": 3.0}
        )
        
        assert response.status_code == 200


class TestPredictionValidation:
    """Tests for prediction data validation."""

    async def test_prediction_probabilities_sum(
        self, client: AsyncClient, test_match
    ):
        """Test that prediction probabilities can sum to any value (model output)."""
        # Note: The API doesn't enforce sum to 1.0, models output raw probabilities
        prediction_data = {
            "match_id": test_match.id,
            "model_name": "test",
            "home_win_prob": 0.40,
            "draw_prob": 0.30,
            "away_win_prob": 0.30,
            "confidence": 0.8
        }
        
        response = await client.post(
            "/api/v1/predictions/",
            json=prediction_data
        )
        
        assert response.status_code == 201

    async def test_prediction_negative_probability(
        self, client: AsyncClient, test_match
    ):
        """Test that negative probabilities are rejected."""
        prediction_data = {
            "match_id": test_match.id,
            "model_name": "test",
            "home_win_prob": -0.1,
            "draw_prob": 0.50,
            "away_win_prob": 0.60
        }
        
        response = await client.post(
            "/api/v1/predictions/",
            json=prediction_data
        )
        
        # Should be rejected by validation
        assert response.status_code == 422
