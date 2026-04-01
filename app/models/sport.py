from beanie import Document, Indexed, Link
from pydantic import Field
from typing import Optional, List
from datetime import datetime
from .base import BaseDocument


class Sport(BaseDocument):
    """Sport model (Football, Basketball, Tennis, etc.)"""
    name: Indexed(str, unique=True)
    slug: Indexed(str, unique=True)
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool = True
    
    class Settings:
        name = "sports"


class League(BaseDocument):
    """League/Competition model."""
    sport_id: str  # Reference to Sport
    name: Indexed(str)
    slug: Indexed(str)
    country: Optional[str] = None
    country_code: Optional[str] = None
    logo_url: Optional[str] = None
    season: Optional[str] = None  # e.g., "2024/2025"
    is_active: bool = True
    external_id: Optional[str] = None
    
    class Settings:
        name = "leagues"


class Team(BaseDocument):
    """Team model."""
    league_id: Optional[str] = None
    name: Indexed(str)
    short_name: Optional[str] = None
    slug: Indexed(str)
    logo_url: Optional[str] = None
    country: Optional[str] = None
    founded_year: Optional[int] = None
    venue_name: Optional[str] = None
    venue_capacity: Optional[int] = None
    external_id: Optional[str] = None
    is_active: bool = True
    
    # Stats cache
    matches_played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    
    class Settings:
        name = "teams"


class Player(BaseDocument):
    """Player model."""
    team_id: Optional[str] = None
    name: Indexed(str)
    short_name: Optional[str] = None
    position: Optional[str] = None  # GK, DEF, MID, FWD
    nationality: Optional[str] = None
    birth_date: Optional[str] = None
    height: Optional[float] = None  # in cm
    weight: Optional[float] = None  # in kg
    photo_url: Optional[str] = None
    jersey_number: Optional[int] = None
    external_id: Optional[str] = None
    is_active: bool = True
    
    # Season stats
    appearances: int = 0
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    minutes_played: int = 0
    rating: Optional[float] = None
    
    class Settings:
        name = "players"
