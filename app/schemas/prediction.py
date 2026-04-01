from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# Prediction Schemas
class PredictionBase(BaseModel):
    match_id: int
    model_name: str = Field(..., min_length=1, max_length=100)
    model_version: Optional[str] = None
    home_win_prob: Optional[float] = Field(None, ge=0, le=1)
    draw_prob: Optional[float] = Field(None, ge=0, le=1)
    away_win_prob: Optional[float] = Field(None, ge=0, le=1)
    predicted_home_score: Optional[float] = None
    predicted_away_score: Optional[float] = None
    over_2_5_prob: Optional[float] = Field(None, ge=0, le=1)
    under_2_5_prob: Optional[float] = Field(None, ge=0, le=1)
    btts_yes_prob: Optional[float] = Field(None, ge=0, le=1)
    btts_no_prob: Optional[float] = Field(None, ge=0, le=1)
    confidence_score: Optional[float] = Field(None, ge=0, le=1)
    recommended_bet: Optional[str] = None
    expected_value: Optional[float] = None


class PredictionCreate(PredictionBase):
    features_used: Optional[Dict[str, Any]] = None
    prediction_details: Optional[Dict[str, Any]] = None


class PredictionResponse(PredictionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PredictionWithMatchResponse(PredictionResponse):
    match: Optional[dict] = None


# Prediction Result Schemas
class PredictionResultBase(BaseModel):
    prediction_id: int
    match_id: int
    actual_home_score: Optional[int] = None
    actual_away_score: Optional[int] = None
    actual_result: Optional[str] = None
    result_correct: Optional[bool] = None
    score_correct: Optional[bool] = None
    over_under_correct: Optional[bool] = None
    btts_correct: Optional[bool] = None
    bet_outcome: Optional[str] = None
    profit_loss: Optional[float] = None


class PredictionResultCreate(PredictionResultBase):
    pass


class PredictionResultResponse(PredictionResultBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Model Performance
class ModelPerformance(BaseModel):
    model_name: str
    total_predictions: int
    correct_results: int
    correct_scores: int
    accuracy_result: float
    accuracy_score: float
    total_profit_loss: float
    roi_percentage: float
    
    @property
    def success_rate(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return self.correct_results / self.total_predictions


# Value Bet
class ValueBet(BaseModel):
    match_id: int
    match_info: dict
    market: str
    selection: str
    predicted_prob: float
    bookmaker_odds: float
    bookmaker_name: str
    implied_prob: float
    edge_percentage: float
    expected_value: float
    confidence: float
    recommended_stake: Optional[float] = None
