from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from .base import BaseDocument


class Prediction(BaseDocument):
    """Match predictions from ML models or analysis."""
    match_id: Indexed(str)
    
    # Prediction source/model
    model_name: str  # e.g., "xgboost_v1", "poisson", "elo"
    model_version: Optional[str] = None
    
    # Predicted probabilities
    home_win_prob: Optional[float] = None
    draw_prob: Optional[float] = None
    away_win_prob: Optional[float] = None
    
    # Predicted scores
    predicted_home_score: Optional[float] = None
    predicted_away_score: Optional[float] = None
    
    # Over/Under predictions
    over_2_5_prob: Optional[float] = None
    under_2_5_prob: Optional[float] = None
    
    # BTTS
    btts_yes_prob: Optional[float] = None
    btts_no_prob: Optional[float] = None
    
    # Confidence and accuracy
    confidence_score: Optional[float] = None  # 0-1
    
    # Value bets identified
    recommended_bet: Optional[str] = None
    expected_value: Optional[float] = None
    
    # Prediction details
    features_used: Optional[Dict[str, Any]] = None
    prediction_details: Optional[Dict[str, Any]] = None
    
    class Settings:
        name = "predictions"


class PredictionResult(BaseDocument):
    """Track prediction accuracy after match completion."""
    prediction_id: Indexed(str)
    match_id: Indexed(str)
    
    # Actual results
    actual_home_score: Optional[int] = None
    actual_away_score: Optional[int] = None
    actual_result: Optional[str] = None  # "home", "draw", "away"
    
    # Prediction accuracy
    result_correct: Optional[bool] = None
    score_correct: Optional[bool] = None
    over_under_correct: Optional[bool] = None
    btts_correct: Optional[bool] = None
    
    # Betting outcome
    bet_outcome: Optional[str] = None  # "won", "lost", "void"
    profit_loss: Optional[float] = None
    
    class Settings:
        name = "prediction_results"
