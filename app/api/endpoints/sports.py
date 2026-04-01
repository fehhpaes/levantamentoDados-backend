from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional

from app.core.database import get_db
from app.models.sport import Sport, League, Team, Player
from app.schemas.sport import (
    SportCreate, SportResponse,
    LeagueCreate, LeagueResponse, LeagueWithSportResponse,
    TeamCreate, TeamResponse, TeamWithLeagueResponse,
    PlayerCreate, PlayerResponse, PlayerWithTeamResponse,
)
from app.schemas.common import PaginatedResponse, MessageResponse

router = APIRouter()


# ===================== SPORTS =====================

@router.get("/", response_model=List[SportResponse])
async def list_sports(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all sports."""
    query = select(Sport)
    if is_active is not None:
        query = query.where(Sport.is_active == is_active)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=SportResponse, status_code=201)
async def create_sport(
    sport: SportCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new sport."""
    db_sport = Sport(**sport.model_dump())
    db.add(db_sport)
    await db.commit()
    await db.refresh(db_sport)
    return db_sport


@router.get("/{sport_id}", response_model=SportResponse)
async def get_sport(sport_id: int, db: AsyncSession = Depends(get_db)):
    """Get a sport by ID."""
    result = await db.execute(select(Sport).where(Sport.id == sport_id))
    sport = result.scalar_one_or_none()
    if not sport:
        raise HTTPException(status_code=404, detail="Sport not found")
    return sport


# ===================== LEAGUES =====================

@router.get("/leagues/", response_model=List[LeagueResponse])
async def list_leagues(
    sport_id: Optional[int] = None,
    country: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all leagues with optional filters."""
    query = select(League)
    
    if sport_id:
        query = query.where(League.sport_id == sport_id)
    if country:
        query = query.where(League.country.ilike(f"%{country}%"))
    if is_active is not None:
        query = query.where(League.is_active == is_active)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/leagues/", response_model=LeagueResponse, status_code=201)
async def create_league(
    league: LeagueCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new league."""
    db_league = League(**league.model_dump())
    db.add(db_league)
    await db.commit()
    await db.refresh(db_league)
    return db_league


@router.get("/leagues/{league_id}", response_model=LeagueWithSportResponse)
async def get_league(league_id: int, db: AsyncSession = Depends(get_db)):
    """Get a league by ID with sport info."""
    result = await db.execute(select(League).where(League.id == league_id))
    league = result.scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league


# ===================== TEAMS =====================

@router.get("/teams/", response_model=List[TeamResponse])
async def list_teams(
    league_id: Optional[int] = None,
    country: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all teams with optional filters."""
    query = select(Team)
    
    if league_id:
        query = query.where(Team.league_id == league_id)
    if country:
        query = query.where(Team.country.ilike(f"%{country}%"))
    if search:
        query = query.where(Team.name.ilike(f"%{search}%"))
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/teams/", response_model=TeamResponse, status_code=201)
async def create_team(
    team: TeamCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new team."""
    db_team = Team(**team.model_dump())
    db.add(db_team)
    await db.commit()
    await db.refresh(db_team)
    return db_team


@router.get("/teams/{team_id}", response_model=TeamWithLeagueResponse)
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    """Get a team by ID with league info."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


# ===================== PLAYERS =====================

@router.get("/players/", response_model=List[PlayerResponse])
async def list_players(
    team_id: Optional[int] = None,
    position: Optional[str] = None,
    nationality: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all players with optional filters."""
    query = select(Player)
    
    if team_id:
        query = query.where(Player.team_id == team_id)
    if position:
        query = query.where(Player.position == position)
    if nationality:
        query = query.where(Player.nationality.ilike(f"%{nationality}%"))
    if search:
        query = query.where(Player.name.ilike(f"%{search}%"))
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/players/", response_model=PlayerResponse, status_code=201)
async def create_player(
    player: PlayerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new player."""
    db_player = Player(**player.model_dump())
    db.add(db_player)
    await db.commit()
    await db.refresh(db_player)
    return db_player


@router.get("/players/{player_id}", response_model=PlayerWithTeamResponse)
async def get_player(player_id: int, db: AsyncSession = Depends(get_db)):
    """Get a player by ID with team info."""
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player
