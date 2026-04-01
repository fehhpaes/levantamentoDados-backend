from sqlalchemy import Column, String, Integer, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import relationship
from .base import BaseModel


class Sport(BaseModel):
    """Sport model (Football, Basketball, Tennis, etc.)"""
    __tablename__ = "sports"
    
    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    leagues = relationship("League", back_populates="sport", lazy="selectin")


class League(BaseModel):
    """League/Competition model."""
    __tablename__ = "leagues"
    
    sport_id = Column(Integer, ForeignKey("sports.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    slug = Column(String(200), nullable=False, index=True)
    country = Column(String(100), nullable=True)
    country_code = Column(String(10), nullable=True)
    logo_url = Column(String(500), nullable=True)
    season = Column(String(20), nullable=True)  # e.g., "2024/2025"
    is_active = Column(Boolean, default=True)
    external_id = Column(String(100), nullable=True)  # ID from external APIs
    
    # Relationships
    sport = relationship("Sport", back_populates="leagues")
    teams = relationship("Team", back_populates="league", lazy="selectin")
    matches = relationship("Match", back_populates="league", lazy="selectin")


class Team(BaseModel):
    """Team model."""
    __tablename__ = "teams"
    
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    short_name = Column(String(50), nullable=True)
    slug = Column(String(200), nullable=False, index=True)
    logo_url = Column(String(500), nullable=True)
    country = Column(String(100), nullable=True)
    founded_year = Column(Integer, nullable=True)
    venue_name = Column(String(200), nullable=True)
    venue_capacity = Column(Integer, nullable=True)
    external_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Stats cache (updated periodically)
    matches_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    points = Column(Integer, default=0)
    
    # Relationships
    league = relationship("League", back_populates="teams")
    players = relationship("Player", back_populates="team", lazy="selectin")
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")


class Player(BaseModel):
    """Player model."""
    __tablename__ = "players"
    
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    short_name = Column(String(100), nullable=True)
    position = Column(String(50), nullable=True)  # GK, DEF, MID, FWD
    nationality = Column(String(100), nullable=True)
    birth_date = Column(String(20), nullable=True)
    height = Column(Float, nullable=True)  # in cm
    weight = Column(Float, nullable=True)  # in kg
    photo_url = Column(String(500), nullable=True)
    jersey_number = Column(Integer, nullable=True)
    external_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Season stats (updated periodically)
    appearances = Column(Integer, default=0)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    minutes_played = Column(Integer, default=0)
    rating = Column(Float, nullable=True)  # Average rating
    
    # Relationships
    team = relationship("Team", back_populates="players")
