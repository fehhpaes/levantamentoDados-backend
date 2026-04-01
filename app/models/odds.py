from sqlalchemy import Column, String, Integer, ForeignKey, Float, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from .base import BaseModel


class Bookmaker(BaseModel):
    """Bookmaker/Betting site model."""
    __tablename__ = "bookmakers"
    
    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    logo_url = Column(String(500), nullable=True)
    website_url = Column(String(500), nullable=True)
    country = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    odds = relationship("Odds", back_populates="bookmaker", lazy="selectin")


class Odds(BaseModel):
    """Current odds for a match."""
    __tablename__ = "odds"
    
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False, index=True)
    
    # Market type: 1X2, Over/Under, Both Teams Score, etc.
    market_type = Column(String(50), nullable=False, index=True)
    market_name = Column(String(100), nullable=True)  # e.g., "Over 2.5", "Home Win"
    
    # Odds values
    home_odds = Column(Float, nullable=True)     # For 1X2: Home Win
    draw_odds = Column(Float, nullable=True)     # For 1X2: Draw
    away_odds = Column(Float, nullable=True)     # For 1X2: Away Win
    
    over_odds = Column(Float, nullable=True)     # For O/U markets
    under_odds = Column(Float, nullable=True)
    
    yes_odds = Column(Float, nullable=True)      # For BTTS, etc.
    no_odds = Column(Float, nullable=True)
    
    line = Column(Float, nullable=True)          # For handicaps, totals (e.g., 2.5)
    
    # Probabilities (calculated)
    home_prob = Column(Float, nullable=True)
    draw_prob = Column(Float, nullable=True)
    away_prob = Column(Float, nullable=True)
    
    # Value bet indicator
    is_value_bet = Column(Boolean, default=False)
    value_percentage = Column(Float, nullable=True)
    
    # Timestamps for odds
    odds_updated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="odds")
    bookmaker = relationship("Bookmaker", back_populates="odds")


class OddsHistory(BaseModel):
    """Historical odds movements."""
    __tablename__ = "odds_history"
    
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False, index=True)
    
    market_type = Column(String(50), nullable=False, index=True)
    
    home_odds = Column(Float, nullable=True)
    draw_odds = Column(Float, nullable=True)
    away_odds = Column(Float, nullable=True)
    over_odds = Column(Float, nullable=True)
    under_odds = Column(Float, nullable=True)
    line = Column(Float, nullable=True)
    
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
