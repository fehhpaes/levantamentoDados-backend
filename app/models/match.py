from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from .base import BaseDocument


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


class MatchStatistics(BaseDocument):
    """Detailed match statistics."""
    match_id: Indexed(str)
    
    # Possession
    home_possession: Optional[float] = None
    away_possession: Optional[float] = None
    
    # Shots
    home_shots: Optional[int] = None
    away_shots: Optional[int] = None
    home_shots_on_target: Optional[int] = None
    away_shots_on_target: Optional[int] = None
    
    # Corners
    home_corners: Optional[int] = None
    away_corners: Optional[int] = None
    
    # Fouls
    home_fouls: Optional[int] = None
    away_fouls: Optional[int] = None
    
    # Cards
    home_yellow_cards: Optional[int] = None
    away_yellow_cards: Optional[int] = None
    home_red_cards: Optional[int] = None
    away_red_cards: Optional[int] = None
    
    # Offsides
    home_offsides: Optional[int] = None
    away_offsides: Optional[int] = None
    
    # Passes
    home_passes: Optional[int] = None
    away_passes: Optional[int] = None
    home_pass_accuracy: Optional[float] = None
    away_pass_accuracy: Optional[float] = None
    
    # Expected Goals (xG)
    home_xg: Optional[float] = None
    away_xg: Optional[float] = None
    
    # Raw data
    raw_data: Optional[Dict[str, Any]] = None
    
    class Settings:
        name = "match_statistics"


class MatchEvent(BaseDocument):
    """Match events (goals, cards, etc.)."""
    match_id: Indexed(str)
    player_id: Optional[str] = None
    
    event_type: str
    minute: Optional[int] = None
    extra_minute: Optional[int] = None
    team_side: Optional[str] = None  # "home" or "away"
    description: Optional[str] = None
    
    # For substitutions
    player_in_id: Optional[str] = None
    
    class Settings:
        name = "match_events"


class TeamInfo(Document):
    """Embedded team info for match."""
    id: str
    name: str
    logo_url: Optional[str] = None


class Match(BaseDocument):
    """Match/Game model."""
    league_id: Indexed(str)
    home_team_id: Indexed(str)
    away_team_id: Indexed(str)
    
    # Match Info
    match_date: Indexed(datetime)
    status: str = MatchStatus.SCHEDULED.value
    round: Optional[str] = None
    venue: Optional[str] = None
    referee: Optional[str] = None
    
    # Score
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_score_ht: Optional[int] = None
    away_score_ht: Optional[int] = None
    
    # External IDs
    external_id: Optional[str] = None
    flashscore_id: Optional[str] = None
    sofascore_id: Optional[str] = None
    
    # Embedded team info (denormalized for quick access)
    home_team: Optional[Dict[str, Any]] = None
    away_team: Optional[Dict[str, Any]] = None
    league: Optional[Dict[str, Any]] = None
    
    class Settings:
        name = "matches"
