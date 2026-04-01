from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from app.models.sport import Sport, League, Team, Player

router = APIRouter()


# ===================== SPORTS =====================

@router.get("/", response_model=List[Sport])
async def list_sports(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    is_active: Optional[bool] = None,
):
    query = {}
    if is_active is not None:
        query["is_active"] = is_active
    return await Sport.find(query).skip(skip).limit(limit).to_list()


@router.post("/", response_model=Sport, status_code=201)
async def create_sport(sport: Sport):
    await sport.save()
    return sport


@router.get("/{sport_id}", response_model=Sport)
async def get_sport(sport_id: str):
    sport = await Sport.get(sport_id)
    if not sport:
        raise HTTPException(status_code=404, detail="Sport not found")
    return sport


# ===================== LEAGUES =====================

@router.get("/leagues/", response_model=List[League])
async def list_leagues(
    sport_id: Optional[str] = None,
    country: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    query = {}
    if sport_id:
        query["sport_id"] = sport_id
    if country:
        query["name"] = {"$regex": country, "$options": "i"}
    if is_active is not None:
        query["is_active"] = is_active
    return await League.find(query).skip(skip).limit(limit).to_list()


@router.post("/leagues/", response_model=League, status_code=201)
async def create_league(league: League):
    await league.save()
    return league


@router.get("/leagues/{league_id}", response_model=League)
async def get_league(league_id: str):
    league = await League.get(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league


# ===================== TEAMS =====================

@router.get("/teams/", response_model=List[Team])
async def list_teams(
    league_id: Optional[str] = None,
    country: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    query = {}
    if league_id:
        query["league_id"] = league_id
    if country:
        query["country"] = {"$regex": country, "$options": "i"}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    return await Team.find(query).skip(skip).limit(limit).to_list()


@router.post("/teams/", response_model=Team, status_code=201)
async def create_team(team: Team):
    await team.save()
    return team


@router.get("/teams/{team_id}", response_model=Team)
async def get_team(team_id: str):
    team = await Team.get(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


# ===================== PLAYERS =====================

@router.get("/players/", response_model=List[Player])
async def list_players(
    team_id: Optional[str] = None,
    position: Optional[str] = None,
    nationality: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    query = {}
    if team_id:
        query["team_id"] = team_id
    if position:
        query["position"] = position
    if nationality:
        query["nationality"] = {"$regex": nationality, "$options": "i"}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    return await Player.find(query).skip(skip).limit(limit).to_list()


@router.post("/players/", response_model=Player, status_code=201)
async def create_player(player: Player):
    await player.save()
    return player


@router.get("/players/{player_id}", response_model=Player)
async def get_player(player_id: str):
    player = await Player.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player
