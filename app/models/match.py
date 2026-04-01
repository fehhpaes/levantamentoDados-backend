from sqlalchemy import Column, String, Integer, ForeignKey, Text, Float, DateTime, Enum
from sqlalchemy.orm import relationship
from .base import BaseModel
import enum


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    HALFTIME = "halftime"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class Match(BaseModel):
    """Match/Game model."""
    __tablename__ = "matches"
    
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    
    # Match Info
    match_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(50), default=MatchStatus.SCHEDULED.value, index=True)
    round = Column(String(50), nullable=True)  # e.g., "Round 10", "Quarter-final"
    venue = Column(String(200), nullable=True)
    referee = Column(String(200), nullable=True)
    
    # Score
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    home_score_ht = Column(Integer, nullable=True)  # Half-time
    away_score_ht = Column(Integer, nullable=True)
    
    # External IDs
    external_id = Column(String(100), nullable=True, unique=True)
    flashscore_id = Column(String(100), nullable=True)
    sofascore_id = Column(String(100), nullable=True)
    
    # Relationships
    league = relationship("League", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    statistics = relationship("MatchStatistics", back_populates="match", uselist=False)
    events = relationship("MatchEvent", back_populates="match", lazy="selectin")
    odds = relationship("Odds", back_populates="match", lazy="selectin")
    predictions = relationship("Prediction", back_populates="match", lazy="selectin")


class MatchStatistics(BaseModel):
    """Detailed match statistics."""
    __tablename__ = "match_statistics"
    
    match_id = Column(Integer, ForeignKey("matches.id"), unique=True, nullable=False, index=True)
    
    # Possession
    home_possession = Column(Float, nullable=True)
    away_possession = Column(Float, nullable=True)
    
    # Shots
    home_shots = Column(Integer, nullable=True)
    away_shots = Column(Integer, nullable=True)
    home_shots_on_target = Column(Integer, nullable=True)
    away_shots_on_target = Column(Integer, nullable=True)
    
    # Corners
    home_corners = Column(Integer, nullable=True)
    away_corners = Column(Integer, nullable=True)
    
    # Fouls
    home_fouls = Column(Integer, nullable=True)
    away_fouls = Column(Integer, nullable=True)
    
    # Cards
    home_yellow_cards = Column(Integer, nullable=True)
    away_yellow_cards = Column(Integer, nullable=True)
    home_red_cards = Column(Integer, nullable=True)
    away_red_cards = Column(Integer, nullable=True)
    
    # Offsides
    home_offsides = Column(Integer, nullable=True)
    away_offsides = Column(Integer, nullable=True)
    
    # Passes
    home_passes = Column(Integer, nullable=True)
    away_passes = Column(Integer, nullable=True)
    home_pass_accuracy = Column(Float, nullable=True)
    away_pass_accuracy = Column(Float, nullable=True)
    
    # Expected Goals (xG)
    home_xg = Column(Float, nullable=True)
    away_xg = Column(Float, nullable=True)
    
    # Raw JSON for additional stats
    raw_data = Column(Text, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="statistics")


class EventType(str, enum.Enum):
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


class MatchEvent(BaseModel):
    """Match events (goals, cards, etc.)."""
    __tablename__ = "match_events"
    
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    
    event_type = Column(String(50), nullable=False, index=True)
    minute = Column(Integer, nullable=True)
    extra_minute = Column(Integer, nullable=True)  # Added time
    team_side = Column(String(10), nullable=True)  # "home" or "away"
    description = Column(Text, nullable=True)
    
    # For substitutions
    player_in_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="events")
