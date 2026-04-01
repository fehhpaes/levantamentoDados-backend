from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Sport Schemas
class SportBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool = True


class SportCreate(SportBase):
    pass


class SportResponse(SportBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# League Schemas
class LeagueBase(BaseModel):
    sport_id: int
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=200)
    country: Optional[str] = None
    country_code: Optional[str] = None
    logo_url: Optional[str] = None
    season: Optional[str] = None
    is_active: bool = True
    external_id: Optional[str] = None


class LeagueCreate(LeagueBase):
    pass


class LeagueResponse(LeagueBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class LeagueWithSportResponse(LeagueResponse):
    sport: Optional[SportResponse] = None


# Team Schemas
class TeamBase(BaseModel):
    league_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=200)
    short_name: Optional[str] = None
    slug: str = Field(..., min_length=1, max_length=200)
    logo_url: Optional[str] = None
    country: Optional[str] = None
    founded_year: Optional[int] = None
    venue_name: Optional[str] = None
    venue_capacity: Optional[int] = None
    external_id: Optional[str] = None
    is_active: bool = True


class TeamCreate(TeamBase):
    pass


class TeamStats(BaseModel):
    matches_played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    
    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against
    
    @property
    def win_rate(self) -> float:
        if self.matches_played == 0:
            return 0.0
        return self.wins / self.matches_played


class TeamResponse(TeamBase):
    id: int
    matches_played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TeamWithLeagueResponse(TeamResponse):
    league: Optional[LeagueResponse] = None


# Player Schemas
class PlayerBase(BaseModel):
    team_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=200)
    short_name: Optional[str] = None
    position: Optional[str] = None
    nationality: Optional[str] = None
    birth_date: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    photo_url: Optional[str] = None
    jersey_number: Optional[int] = None
    external_id: Optional[str] = None
    is_active: bool = True


class PlayerCreate(PlayerBase):
    pass


class PlayerStats(BaseModel):
    appearances: int = 0
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    minutes_played: int = 0
    rating: Optional[float] = None
    
    @property
    def goals_per_game(self) -> float:
        if self.appearances == 0:
            return 0.0
        return self.goals / self.appearances


class PlayerResponse(PlayerBase):
    id: int
    appearances: int = 0
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    minutes_played: int = 0
    rating: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PlayerWithTeamResponse(PlayerResponse):
    team: Optional[TeamResponse] = None
