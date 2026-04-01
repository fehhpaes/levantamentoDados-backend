from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    HALFTIME = "halftime"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class EventType(str, Enum):
    GOAL = "goal"
    OWN_GOAL = "own_goal"
    PENALTY = "penalty"
    PENALTY_MISSED = "penalty_missed"
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    SECOND_YELLOW = "second_yellow"
    SUBSTITUTION = "substitution"
    VAR = "var"
    INJURY = "injury"


# Match Schemas
class MatchBase(BaseModel):
    league_id: int
    home_team_id: int
    away_team_id: int
    match_date: datetime
    status: MatchStatus = MatchStatus.SCHEDULED
    round: Optional[str] = None
    venue: Optional[str] = None
    referee: Optional[str] = None


class MatchCreate(MatchBase):
    external_id: Optional[str] = None


class MatchScoreUpdate(BaseModel):
    home_score: int
    away_score: int
    home_score_ht: Optional[int] = None
    away_score_ht: Optional[int] = None
    status: Optional[MatchStatus] = None


class MatchResponse(MatchBase):
    id: int
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_score_ht: Optional[int] = None
    away_score_ht: Optional[int] = None
    external_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MatchWithTeamsResponse(MatchResponse):
    home_team: Optional[dict] = None
    away_team: Optional[dict] = None
    league: Optional[dict] = None


# Match Statistics Schemas
class MatchStatisticsBase(BaseModel):
    match_id: int
    home_possession: Optional[float] = None
    away_possession: Optional[float] = None
    home_shots: Optional[int] = None
    away_shots: Optional[int] = None
    home_shots_on_target: Optional[int] = None
    away_shots_on_target: Optional[int] = None
    home_corners: Optional[int] = None
    away_corners: Optional[int] = None
    home_fouls: Optional[int] = None
    away_fouls: Optional[int] = None
    home_yellow_cards: Optional[int] = None
    away_yellow_cards: Optional[int] = None
    home_red_cards: Optional[int] = None
    away_red_cards: Optional[int] = None
    home_offsides: Optional[int] = None
    away_offsides: Optional[int] = None
    home_passes: Optional[int] = None
    away_passes: Optional[int] = None
    home_pass_accuracy: Optional[float] = None
    away_pass_accuracy: Optional[float] = None
    home_xg: Optional[float] = None
    away_xg: Optional[float] = None


class MatchStatisticsCreate(MatchStatisticsBase):
    pass


class MatchStatisticsResponse(MatchStatisticsBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Match Event Schemas
class MatchEventBase(BaseModel):
    match_id: int
    player_id: Optional[int] = None
    event_type: EventType
    minute: Optional[int] = None
    extra_minute: Optional[int] = None
    team_side: Optional[str] = None
    description: Optional[str] = None
    player_in_id: Optional[int] = None


class MatchEventCreate(MatchEventBase):
    pass


class MatchEventResponse(MatchEventBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Match Details (combined response)
class MatchDetailsResponse(MatchWithTeamsResponse):
    statistics: Optional[MatchStatisticsResponse] = None
    events: List[MatchEventResponse] = []
    odds: List[dict] = []
    predictions: List[dict] = []
