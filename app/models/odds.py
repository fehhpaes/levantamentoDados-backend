from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, Dict, Any
from datetime import datetime
from .base import BaseDocument


class Bookmaker(BaseDocument):
    """Bookmaker/Betting site model."""
    name: Indexed(str, unique=True)
    slug: Indexed(str, unique=True)
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    country: Optional[str] = None
    is_active: bool = True
    
    class Settings:
        name = "bookmakers"


class Odds(BaseDocument):
    """Current odds for a match."""
    match_id: Indexed(str)
    bookmaker_id: Indexed(str)
    
    # Market type: 1X2, Over/Under, Both Teams Score, etc.
    market_type: Indexed(str)
    market_name: Optional[str] = None
    
    # Odds values
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
    
    over_odds: Optional[float] = None
    under_odds: Optional[float] = None
    
    yes_odds: Optional[float] = None
    no_odds: Optional[float] = None
    
    line: Optional[float] = None
    
    # Probabilities (calculated)
    home_prob: Optional[float] = None
    draw_prob: Optional[float] = None
    away_prob: Optional[float] = None
    
    # Value bet indicator
    is_value_bet: bool = False
    value_percentage: Optional[float] = None
    
    # Timestamps for odds
    odds_updated_at: Optional[datetime] = None
    
    # Embedded bookmaker info
    bookmaker: Optional[Dict[str, Any]] = None
    
    class Settings:
        name = "odds"


class OddsHistory(BaseDocument):
    """Historical odds movements."""
    match_id: Indexed(str)
    bookmaker_id: Indexed(str)
    
    market_type: Indexed(str)
    
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
    over_odds: Optional[float] = None
    under_odds: Optional[float] = None
    line: Optional[float] = None
    
    recorded_at: Indexed(datetime)
    
    class Settings:
        name = "odds_history"
