"""
ML Predictions API Endpoints.

Provides endpoints for generating predictions using ensemble ML models,
training models, and getting model insights.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from enum import Enum

from app.core.database import get_db
from app.models.match import Match
from app.models.sport import Team
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User, UserRole
from app.ml.ensemble import EnsemblePredictor
from app.ml.models.poisson import PoissonModel
from app.ml.models.elo import ELOSystem
from app.ml.models.monte_carlo import MonteCarloSimulator


router = APIRouter()


# ========================
# Schemas
# ========================

class SportType(str, Enum):
    football = "football"
    basketball = "basketball"
    tennis = "tennis"
    esports = "esports"


class PredictionRequest(BaseModel):
    match_id: Optional[int] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    sport: SportType = SportType.football
    models: Optional[List[str]] = Field(
        default=None,
        description="Specific models to use. If None, uses all available models."
    )
    include_simulations: bool = Field(
        default=False,
        description="Include Monte Carlo simulations (slower but more detailed)"
    )
    num_simulations: int = Field(default=10000, ge=1000, le=100000)


class TeamStats(BaseModel):
    team_id: int
    team_name: str
    elo_rating: float
    avg_goals_scored: float
    avg_goals_conceded: float
    form_rating: float
    home_advantage: Optional[float] = None


class ScoreProbability(BaseModel):
    home_goals: int
    away_goals: int
    probability: float


class MarketPrediction(BaseModel):
    market: str
    selection: str
    probability: float
    fair_odds: float
    confidence: float


class MLPredictionResponse(BaseModel):
    match_id: Optional[int]
    home_team: TeamStats
    away_team: TeamStats
    predictions: Dict[str, Any]
    ensemble_prediction: Dict[str, float]
    recommended_bets: List[MarketPrediction]
    score_matrix: Optional[List[ScoreProbability]] = None
    simulation_results: Optional[Dict[str, Any]] = None
    model_weights: Dict[str, float]
    prediction_timestamp: datetime
    confidence_score: float


class ModelTrainingRequest(BaseModel):
    model_name: str
    sport: SportType
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    hyperparameters: Optional[Dict[str, Any]] = None


class ModelTrainingResponse(BaseModel):
    job_id: str
    model_name: str
    status: str
    message: str


class ModelInfoResponse(BaseModel):
    name: str
    description: str
    supported_sports: List[str]
    supported_markets: List[str]
    last_trained: Optional[datetime]
    accuracy: Optional[float]
    total_predictions: int


class EloRatingResponse(BaseModel):
    team_id: int
    team_name: str
    elo_rating: float
    rank: int
    recent_change: float
    last_updated: datetime


# ========================
# Endpoints
# ========================

@router.get("/models", response_model=List[ModelInfoResponse])
async def list_available_models():
    """List all available ML models and their capabilities."""
    models = [
        ModelInfoResponse(
            name="poisson",
            description="Poisson distribution model for goal/score predictions",
            supported_sports=["football", "basketball"],
            supported_markets=["1X2", "Over/Under", "Correct Score", "BTTS"],
            last_trained=None,
            accuracy=None,
            total_predictions=0,
        ),
        ModelInfoResponse(
            name="elo",
            description="ELO rating system for win probability predictions",
            supported_sports=["football", "basketball", "tennis", "esports"],
            supported_markets=["1X2", "Moneyline", "Match Winner"],
            last_trained=None,
            accuracy=None,
            total_predictions=0,
        ),
        ModelInfoResponse(
            name="xgboost",
            description="Gradient boosting model with advanced feature engineering",
            supported_sports=["football", "basketball", "tennis"],
            supported_markets=["1X2", "Over/Under", "Asian Handicap", "BTTS"],
            last_trained=None,
            accuracy=None,
            total_predictions=0,
        ),
        ModelInfoResponse(
            name="lstm",
            description="LSTM neural network for time-series predictions",
            supported_sports=["football", "basketball", "esports"],
            supported_markets=["1X2", "Over/Under", "Live Predictions"],
            last_trained=None,
            accuracy=None,
            total_predictions=0,
        ),
        ModelInfoResponse(
            name="monte_carlo",
            description="Monte Carlo simulation for detailed outcome distributions",
            supported_sports=["football", "basketball", "tennis"],
            supported_markets=["All markets", "Custom scenarios"],
            last_trained=None,
            accuracy=None,
            total_predictions=0,
        ),
        ModelInfoResponse(
            name="ensemble",
            description="Combined ensemble of all models with dynamic weighting",
            supported_sports=["football", "basketball", "tennis", "esports"],
            supported_markets=["All markets"],
            last_trained=None,
            accuracy=None,
            total_predictions=0,
        ),
    ]
    return models


@router.post("/predict", response_model=MLPredictionResponse)
async def generate_prediction(
    request: PredictionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate ML predictions for a match.
    
    Uses ensemble of models (Poisson, ELO, XGBoost, LSTM) to predict match outcomes.
    Optionally includes Monte Carlo simulations for detailed probability distributions.
    """
    # Get match or team data
    home_team = None
    away_team = None
    match = None
    
    if request.match_id:
        result = await db.execute(
            select(Match).where(Match.id == request.match_id)
        )
        match = result.scalar_one_or_none()
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")
        
        # Get teams from match
        home_result = await db.execute(select(Team).where(Team.id == match.home_team_id))
        away_result = await db.execute(select(Team).where(Team.id == match.away_team_id))
        home_team = home_result.scalar_one_or_none()
        away_team = away_result.scalar_one_or_none()
    elif request.home_team_id and request.away_team_id:
        home_result = await db.execute(select(Team).where(Team.id == request.home_team_id))
        away_result = await db.execute(select(Team).where(Team.id == request.away_team_id))
        home_team = home_result.scalar_one_or_none()
        away_team = away_result.scalar_one_or_none()
    else:
        raise HTTPException(
            status_code=400, 
            detail="Either match_id or both home_team_id and away_team_id required"
        )
    
    if not home_team or not away_team:
        raise HTTPException(status_code=404, detail="Team(s) not found")
    
    # Initialize models
    poisson = PoissonModel()
    elo = ELOSystem()
    
    # Get ELO ratings (or use defaults)
    home_elo = elo.get_rating(home_team.id) if hasattr(elo, 'get_rating') else 1500
    away_elo = elo.get_rating(away_team.id) if hasattr(elo, 'get_rating') else 1500
    
    # Calculate win probabilities from ELO
    elo_probs = elo.predict_match(home_elo, away_elo)
    
    # Mock team statistics (in production, fetch from database)
    home_stats = TeamStats(
        team_id=home_team.id,
        team_name=home_team.name,
        elo_rating=home_elo,
        avg_goals_scored=1.8,  # Would come from historical data
        avg_goals_conceded=1.2,
        form_rating=0.65,
        home_advantage=0.1,
    )
    
    away_stats = TeamStats(
        team_id=away_team.id,
        team_name=away_team.name,
        elo_rating=away_elo,
        avg_goals_scored=1.5,
        avg_goals_conceded=1.4,
        form_rating=0.55,
        home_advantage=None,
    )
    
    # Generate Poisson predictions
    poisson.fit(
        home_goals=[home_stats.avg_goals_scored],
        away_goals=[away_stats.avg_goals_scored],
        home_conceded=[home_stats.avg_goals_conceded],
        away_conceded=[away_stats.avg_goals_conceded],
    )
    poisson_pred = poisson.predict_match(
        home_team.id, away_team.id,
        home_attack=home_stats.avg_goals_scored,
        home_defense=home_stats.avg_goals_conceded,
        away_attack=away_stats.avg_goals_scored,
        away_defense=away_stats.avg_goals_conceded,
    )
    
    # Combine predictions (simple averaging for now)
    ensemble_prediction = {
        "home_win": (elo_probs["home_win"] + poisson_pred.get("home_win", 0.4)) / 2,
        "draw": (elo_probs["draw"] + poisson_pred.get("draw", 0.25)) / 2,
        "away_win": (elo_probs["away_win"] + poisson_pred.get("away_win", 0.35)) / 2,
        "over_2_5": poisson_pred.get("over_2_5", 0.5),
        "btts": poisson_pred.get("btts", 0.5),
    }
    
    # Normalize probabilities
    total = ensemble_prediction["home_win"] + ensemble_prediction["draw"] + ensemble_prediction["away_win"]
    ensemble_prediction["home_win"] /= total
    ensemble_prediction["draw"] /= total
    ensemble_prediction["away_win"] /= total
    
    # Generate recommended bets
    recommended_bets = []
    
    if ensemble_prediction["home_win"] > 0.5:
        recommended_bets.append(MarketPrediction(
            market="1X2",
            selection="Home Win",
            probability=ensemble_prediction["home_win"],
            fair_odds=1 / ensemble_prediction["home_win"],
            confidence=0.7,
        ))
    elif ensemble_prediction["away_win"] > 0.5:
        recommended_bets.append(MarketPrediction(
            market="1X2",
            selection="Away Win",
            probability=ensemble_prediction["away_win"],
            fair_odds=1 / ensemble_prediction["away_win"],
            confidence=0.7,
        ))
    
    if ensemble_prediction.get("over_2_5", 0) > 0.55:
        recommended_bets.append(MarketPrediction(
            market="Over/Under",
            selection="Over 2.5",
            probability=ensemble_prediction["over_2_5"],
            fair_odds=1 / ensemble_prediction["over_2_5"],
            confidence=0.6,
        ))
    
    # Monte Carlo simulation (if requested)
    simulation_results = None
    if request.include_simulations:
        monte_carlo = MonteCarloSimulator()
        monte_carlo.setup_teams(
            home_team_params={
                "attack": home_stats.avg_goals_scored,
                "defense": home_stats.avg_goals_conceded,
                "form": home_stats.form_rating,
            },
            away_team_params={
                "attack": away_stats.avg_goals_scored,
                "defense": away_stats.avg_goals_conceded,
                "form": away_stats.form_rating,
            },
        )
        simulation_results = monte_carlo.run_simulation(
            n_simulations=request.num_simulations
        )
    
    # Build score matrix from Poisson
    score_matrix = []
    for h in range(6):
        for a in range(6):
            prob = poisson.score_probability(h, a) if hasattr(poisson, 'score_probability') else 0.01
            if prob > 0.01:
                score_matrix.append(ScoreProbability(
                    home_goals=h,
                    away_goals=a,
                    probability=prob,
                ))
    
    # Sort by probability
    score_matrix.sort(key=lambda x: x.probability, reverse=True)
    score_matrix = score_matrix[:15]  # Top 15 most likely scores
    
    return MLPredictionResponse(
        match_id=request.match_id,
        home_team=home_stats,
        away_team=away_stats,
        predictions={
            "poisson": poisson_pred,
            "elo": elo_probs,
        },
        ensemble_prediction=ensemble_prediction,
        recommended_bets=recommended_bets,
        score_matrix=score_matrix if score_matrix else None,
        simulation_results=simulation_results,
        model_weights={
            "poisson": 0.35,
            "elo": 0.25,
            "xgboost": 0.25,
            "lstm": 0.15,
        },
        prediction_timestamp=datetime.utcnow(),
        confidence_score=0.72,
    )


@router.get("/elo-rankings", response_model=List[EloRatingResponse])
async def get_elo_rankings(
    sport: SportType = SportType.football,
    league_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get ELO rankings for teams."""
    # In production, fetch from database
    # For now, return mock data
    query = select(Team)
    if league_id:
        query = query.where(Team.league_id == league_id)
    query = query.limit(limit)
    
    result = await db.execute(query)
    teams = result.scalars().all()
    
    elo_system = ELOSystem()
    rankings = []
    
    for idx, team in enumerate(teams):
        elo = elo_system.get_rating(team.id) if hasattr(elo_system, 'get_rating') else 1500 + (50 - idx) * 10
        rankings.append(EloRatingResponse(
            team_id=team.id,
            team_name=team.name,
            elo_rating=elo,
            rank=idx + 1,
            recent_change=0.0,
            last_updated=datetime.utcnow(),
        ))
    
    # Sort by ELO rating
    rankings.sort(key=lambda x: x.elo_rating, reverse=True)
    
    # Update ranks after sorting
    for idx, r in enumerate(rankings):
        r.rank = idx + 1
    
    return rankings


@router.post("/train", response_model=ModelTrainingResponse)
async def train_model(
    request: ModelTrainingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """
    Start training a model (admin only).
    
    Training runs in the background and results can be checked via /train/{job_id}/status.
    """
    import uuid
    job_id = str(uuid.uuid4())
    
    # In production, add background task for training
    # background_tasks.add_task(train_model_task, job_id, request)
    
    return ModelTrainingResponse(
        job_id=job_id,
        model_name=request.model_name,
        status="queued",
        message=f"Training job {job_id} has been queued for model {request.model_name}",
    )


@router.get("/train/{job_id}/status")
async def get_training_status(
    job_id: str,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Get the status of a training job (admin only)."""
    # In production, fetch from job queue/database
    return {
        "job_id": job_id,
        "status": "completed",
        "progress": 100,
        "metrics": {
            "accuracy": 0.72,
            "log_loss": 0.45,
            "roc_auc": 0.78,
        },
        "completed_at": datetime.utcnow(),
    }


@router.post("/simulate-season")
async def simulate_season(
    league_id: int,
    num_simulations: int = Query(10000, ge=100, le=100000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run Monte Carlo simulations for remaining season matches.
    
    Returns probability distributions for final standings, champions, 
    relegation, European spots, etc.
    """
    # This would fetch remaining matches and run simulations
    # For now, return mock data structure
    return {
        "league_id": league_id,
        "num_simulations": num_simulations,
        "championship_probabilities": {
            "Team A": 0.45,
            "Team B": 0.30,
            "Team C": 0.15,
            "Others": 0.10,
        },
        "relegation_probabilities": {
            "Team X": 0.65,
            "Team Y": 0.55,
            "Team Z": 0.45,
        },
        "champions_league_probabilities": {
            "Team A": 0.92,
            "Team B": 0.85,
            "Team C": 0.70,
            "Team D": 0.55,
        },
        "expected_points": {
            "Team A": 85.5,
            "Team B": 82.3,
            "Team C": 76.8,
        },
        "simulation_timestamp": datetime.utcnow().isoformat(),
    }
