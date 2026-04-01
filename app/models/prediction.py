from sqlalchemy import Column, String, Integer, ForeignKey, Float, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel


class Prediction(BaseModel):
    """Match predictions from ML models or analysis."""
    __tablename__ = "predictions"
    
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    
    # Prediction source/model
    model_name = Column(String(100), nullable=False)  # e.g., "xgboost_v1", "poisson", "elo"
    model_version = Column(String(50), nullable=True)
    
    # Predicted probabilities
    home_win_prob = Column(Float, nullable=True)
    draw_prob = Column(Float, nullable=True)
    away_win_prob = Column(Float, nullable=True)
    
    # Predicted scores
    predicted_home_score = Column(Float, nullable=True)
    predicted_away_score = Column(Float, nullable=True)
    
    # Over/Under predictions
    over_2_5_prob = Column(Float, nullable=True)
    under_2_5_prob = Column(Float, nullable=True)
    
    # BTTS
    btts_yes_prob = Column(Float, nullable=True)
    btts_no_prob = Column(Float, nullable=True)
    
    # Confidence and accuracy
    confidence_score = Column(Float, nullable=True)  # 0-1
    
    # Value bets identified
    recommended_bet = Column(String(100), nullable=True)  # e.g., "Over 2.5", "Home Win"
    expected_value = Column(Float, nullable=True)  # EV percentage
    
    # Prediction details (JSON)
    features_used = Column(Text, nullable=True)  # JSON with feature values
    prediction_details = Column(Text, nullable=True)  # Additional details
    
    # Relationships
    match = relationship("Match", back_populates="predictions")


class PredictionResult(BaseModel):
    """Track prediction accuracy after match completion."""
    __tablename__ = "prediction_results"
    
    prediction_id = Column(Integer, ForeignKey("predictions.id"), unique=True, nullable=False, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    
    # Actual results
    actual_home_score = Column(Integer, nullable=True)
    actual_away_score = Column(Integer, nullable=True)
    actual_result = Column(String(10), nullable=True)  # "home", "draw", "away"
    
    # Prediction accuracy
    result_correct = Column(Boolean, nullable=True)
    score_correct = Column(Boolean, nullable=True)
    over_under_correct = Column(Boolean, nullable=True)
    btts_correct = Column(Boolean, nullable=True)
    
    # Betting outcome if bet was placed
    bet_outcome = Column(String(20), nullable=True)  # "won", "lost", "void"
    profit_loss = Column(Float, nullable=True)  # In units
