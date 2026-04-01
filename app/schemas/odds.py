from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Bookmaker Schemas
class BookmakerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    country: Optional[str] = None
    is_active: bool = True


class BookmakerCreate(BookmakerBase):
    pass


class BookmakerResponse(BookmakerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Odds Schemas
class OddsBase(BaseModel):
    match_id: int
    bookmaker_id: int
    market_type: str  # "1X2", "over_under", "btts", "handicap"
    market_name: Optional[str] = None
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
    over_odds: Optional[float] = None
    under_odds: Optional[float] = None
    yes_odds: Optional[float] = None
    no_odds: Optional[float] = None
    line: Optional[float] = None


class OddsCreate(OddsBase):
    pass


class OddsResponse(OddsBase):
    id: int
    home_prob: Optional[float] = None
    draw_prob: Optional[float] = None
    away_prob: Optional[float] = None
    is_value_bet: bool = False
    value_percentage: Optional[float] = None
    odds_updated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OddsWithBookmakerResponse(OddsResponse):
    bookmaker: Optional[BookmakerResponse] = None


# Odds History Schemas
class OddsHistoryBase(BaseModel):
    match_id: int
    bookmaker_id: int
    market_type: str
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
    over_odds: Optional[float] = None
    under_odds: Optional[float] = None
    line: Optional[float] = None
    recorded_at: datetime


class OddsHistoryCreate(OddsHistoryBase):
    pass


class OddsHistoryResponse(OddsHistoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Odds Movement Analysis
class OddsMovement(BaseModel):
    market_type: str
    opening_odds: Optional[float] = None
    current_odds: Optional[float] = None
    lowest_odds: Optional[float] = None
    highest_odds: Optional[float] = None
    movement_percentage: Optional[float] = None
    direction: str = "stable"  # "up", "down", "stable"


class OddsComparison(BaseModel):
    match_id: int
    market_type: str
    bookmakers: List[dict]
    best_home_odds: Optional[dict] = None
    best_draw_odds: Optional[dict] = None
    best_away_odds: Optional[dict] = None
    best_over_odds: Optional[dict] = None
    best_under_odds: Optional[dict] = None
