from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.match import Match, MatchStatistics, MatchEvent
from app.models.sport import Team, League
from app.schemas.match import (
    MatchCreate, MatchResponse, MatchWithTeamsResponse,
    MatchStatisticsCreate, MatchStatisticsResponse,
    MatchEventCreate, MatchEventResponse,
    MatchDetailsResponse, MatchScoreUpdate,
    MatchStatus,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("/", response_model=List[MatchWithTeamsResponse])
async def list_matches(
    league_id: Optional[int] = None,
    team_id: Optional[int] = None,
    status: Optional[MatchStatus] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List matches with filters."""
    query = select(Match).options(
        selectinload(Match.home_team),
        selectinload(Match.away_team),
        selectinload(Match.league)
    )
    
    if league_id:
        query = query.where(Match.league_id == league_id)
    if team_id:
        query = query.where(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
        )
    if status:
        query = query.where(Match.status == status.value)
    if date_from:
        query = query.where(Match.match_date >= date_from)
    if date_to:
        query = query.where(Match.match_date <= date_to)
    
    query = query.order_by(Match.match_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    matches = result.scalars().all()
    
    return [
        MatchWithTeamsResponse(
            **m.__dict__,
            home_team={"id": m.home_team.id, "name": m.home_team.name, "logo_url": m.home_team.logo_url} if m.home_team else None,
            away_team={"id": m.away_team.id, "name": m.away_team.name, "logo_url": m.away_team.logo_url} if m.away_team else None,
            league={"id": m.league.id, "name": m.league.name} if m.league else None,
        )
        for m in matches
    ]


@router.get("/live", response_model=List[MatchWithTeamsResponse])
async def get_live_matches(db: AsyncSession = Depends(get_db)):
    """Get all live matches."""
    query = select(Match).options(
        selectinload(Match.home_team),
        selectinload(Match.away_team),
        selectinload(Match.league)
    ).where(Match.status.in_([MatchStatus.LIVE.value, MatchStatus.HALFTIME.value]))
    
    result = await db.execute(query)
    matches = result.scalars().all()
    
    return [
        MatchWithTeamsResponse(
            **m.__dict__,
            home_team={"id": m.home_team.id, "name": m.home_team.name} if m.home_team else None,
            away_team={"id": m.away_team.id, "name": m.away_team.name} if m.away_team else None,
            league={"id": m.league.id, "name": m.league.name} if m.league else None,
        )
        for m in matches
    ]


@router.get("/today", response_model=List[MatchWithTeamsResponse])
async def get_today_matches(db: AsyncSession = Depends(get_db)):
    """Get all matches for today."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    query = select(Match).options(
        selectinload(Match.home_team),
        selectinload(Match.away_team),
        selectinload(Match.league)
    ).where(
        and_(Match.match_date >= today_start, Match.match_date < today_end)
    ).order_by(Match.match_date)
    
    result = await db.execute(query)
    matches = result.scalars().all()
    
    return [
        MatchWithTeamsResponse(
            **m.__dict__,
            home_team={"id": m.home_team.id, "name": m.home_team.name} if m.home_team else None,
            away_team={"id": m.away_team.id, "name": m.away_team.name} if m.away_team else None,
            league={"id": m.league.id, "name": m.league.name} if m.league else None,
        )
        for m in matches
    ]


@router.post("/", response_model=MatchResponse, status_code=201)
async def create_match(
    match: MatchCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new match."""
    db_match = Match(**match.model_dump())
    db.add(db_match)
    await db.commit()
    await db.refresh(db_match)
    return db_match


@router.get("/{match_id}", response_model=MatchDetailsResponse)
async def get_match_details(match_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed match information."""
    query = select(Match).options(
        selectinload(Match.home_team),
        selectinload(Match.away_team),
        selectinload(Match.league),
        selectinload(Match.statistics),
        selectinload(Match.events),
        selectinload(Match.odds),
        selectinload(Match.predictions),
    ).where(Match.id == match_id)
    
    result = await db.execute(query)
    match = result.scalar_one_or_none()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    return MatchDetailsResponse(
        **match.__dict__,
        home_team={"id": match.home_team.id, "name": match.home_team.name} if match.home_team else None,
        away_team={"id": match.away_team.id, "name": match.away_team.name} if match.away_team else None,
        league={"id": match.league.id, "name": match.league.name} if match.league else None,
        statistics=match.statistics,
        events=match.events,
        odds=[{"id": o.id, "market_type": o.market_type, "home_odds": o.home_odds, "draw_odds": o.draw_odds, "away_odds": o.away_odds} for o in match.odds],
        predictions=[{"id": p.id, "model_name": p.model_name, "home_win_prob": p.home_win_prob} for p in match.predictions],
    )


@router.put("/{match_id}/score", response_model=MatchResponse)
async def update_match_score(
    match_id: int,
    score: MatchScoreUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update match score."""
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    match.home_score = score.home_score
    match.away_score = score.away_score
    if score.home_score_ht is not None:
        match.home_score_ht = score.home_score_ht
    if score.away_score_ht is not None:
        match.away_score_ht = score.away_score_ht
    if score.status:
        match.status = score.status.value
    
    await db.commit()
    await db.refresh(match)
    return match


@router.post("/{match_id}/statistics", response_model=MatchStatisticsResponse, status_code=201)
async def add_match_statistics(
    match_id: int,
    statistics: MatchStatisticsCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add or update match statistics."""
    # Check if match exists
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Check if statistics already exist
    result = await db.execute(select(MatchStatistics).where(MatchStatistics.match_id == match_id))
    existing_stats = result.scalar_one_or_none()
    
    if existing_stats:
        # Update existing
        for key, value in statistics.model_dump().items():
            setattr(existing_stats, key, value)
        await db.commit()
        await db.refresh(existing_stats)
        return existing_stats
    else:
        # Create new
        db_stats = MatchStatistics(**statistics.model_dump())
        db.add(db_stats)
        await db.commit()
        await db.refresh(db_stats)
        return db_stats


@router.post("/{match_id}/events", response_model=MatchEventResponse, status_code=201)
async def add_match_event(
    match_id: int,
    event: MatchEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a match event (goal, card, etc.)."""
    # Check if match exists
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    db_event = MatchEvent(**event.model_dump())
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    return db_event


@router.get("/{match_id}/head-to-head", response_model=List[MatchResponse])
async def get_head_to_head(
    match_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get head-to-head history between two teams."""
    # Get the match first
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Get H2H matches
    query = select(Match).where(
        and_(
            Match.status == MatchStatus.FINISHED.value,
            or_(
                and_(Match.home_team_id == match.home_team_id, Match.away_team_id == match.away_team_id),
                and_(Match.home_team_id == match.away_team_id, Match.away_team_id == match.home_team_id),
            )
        )
    ).order_by(Match.match_date.desc()).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()
