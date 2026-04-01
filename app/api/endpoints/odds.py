from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models.odds import Bookmaker, Odds, OddsHistory
from app.models.match import Match
from app.schemas.odds import (
    BookmakerCreate, BookmakerResponse,
    OddsCreate, OddsResponse, OddsWithBookmakerResponse,
    OddsHistoryResponse, OddsMovement, OddsComparison,
)

router = APIRouter()


# ===================== BOOKMAKERS =====================

@router.get("/bookmakers", response_model=List[BookmakerResponse])
async def list_bookmakers(
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all bookmakers."""
    query = select(Bookmaker)
    if is_active is not None:
        query = query.where(Bookmaker.is_active == is_active)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/bookmakers", response_model=BookmakerResponse, status_code=201)
async def create_bookmaker(
    bookmaker: BookmakerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new bookmaker."""
    db_bookmaker = Bookmaker(**bookmaker.model_dump())
    db.add(db_bookmaker)
    await db.commit()
    await db.refresh(db_bookmaker)
    return db_bookmaker


# ===================== ODDS =====================

@router.get("/match/{match_id}", response_model=List[OddsWithBookmakerResponse])
async def get_match_odds(
    match_id: int,
    market_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all odds for a match."""
    query = select(Odds).options(
        selectinload(Odds.bookmaker)
    ).where(Odds.match_id == match_id)
    
    if market_type:
        query = query.where(Odds.market_type == market_type)
    
    result = await db.execute(query)
    odds_list = result.scalars().all()
    
    return [
        OddsWithBookmakerResponse(
            **o.__dict__,
            bookmaker=BookmakerResponse.model_validate(o.bookmaker) if o.bookmaker else None
        )
        for o in odds_list
    ]


@router.post("/", response_model=OddsResponse, status_code=201)
async def create_or_update_odds(
    odds: OddsCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create or update odds for a match."""
    # Check if odds already exist for this match/bookmaker/market
    query = select(Odds).where(
        and_(
            Odds.match_id == odds.match_id,
            Odds.bookmaker_id == odds.bookmaker_id,
            Odds.market_type == odds.market_type,
        )
    )
    result = await db.execute(query)
    existing_odds = result.scalar_one_or_none()
    
    if existing_odds:
        # Save to history before updating
        history = OddsHistory(
            match_id=existing_odds.match_id,
            bookmaker_id=existing_odds.bookmaker_id,
            market_type=existing_odds.market_type,
            home_odds=existing_odds.home_odds,
            draw_odds=existing_odds.draw_odds,
            away_odds=existing_odds.away_odds,
            over_odds=existing_odds.over_odds,
            under_odds=existing_odds.under_odds,
            line=existing_odds.line,
            recorded_at=existing_odds.odds_updated_at or existing_odds.updated_at,
        )
        db.add(history)
        
        # Update existing odds
        for key, value in odds.model_dump().items():
            if value is not None:
                setattr(existing_odds, key, value)
        existing_odds.odds_updated_at = datetime.utcnow()
        
        # Calculate implied probabilities
        if existing_odds.home_odds and existing_odds.draw_odds and existing_odds.away_odds:
            total = (1/existing_odds.home_odds) + (1/existing_odds.draw_odds) + (1/existing_odds.away_odds)
            existing_odds.home_prob = (1/existing_odds.home_odds) / total
            existing_odds.draw_prob = (1/existing_odds.draw_odds) / total
            existing_odds.away_prob = (1/existing_odds.away_odds) / total
        
        await db.commit()
        await db.refresh(existing_odds)
        return existing_odds
    else:
        # Create new odds
        db_odds = Odds(**odds.model_dump())
        db_odds.odds_updated_at = datetime.utcnow()
        
        # Calculate implied probabilities
        if db_odds.home_odds and db_odds.draw_odds and db_odds.away_odds:
            total = (1/db_odds.home_odds) + (1/db_odds.draw_odds) + (1/db_odds.away_odds)
            db_odds.home_prob = (1/db_odds.home_odds) / total
            db_odds.draw_prob = (1/db_odds.draw_odds) / total
            db_odds.away_prob = (1/db_odds.away_odds) / total
        
        db.add(db_odds)
        await db.commit()
        await db.refresh(db_odds)
        return db_odds


@router.get("/match/{match_id}/history", response_model=List[OddsHistoryResponse])
async def get_odds_history(
    match_id: int,
    bookmaker_id: Optional[int] = None,
    market_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get odds movement history for a match."""
    query = select(OddsHistory).where(OddsHistory.match_id == match_id)
    
    if bookmaker_id:
        query = query.where(OddsHistory.bookmaker_id == bookmaker_id)
    if market_type:
        query = query.where(OddsHistory.market_type == market_type)
    
    query = query.order_by(OddsHistory.recorded_at)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/match/{match_id}/comparison")
async def compare_odds(
    match_id: int,
    market_type: str = "1X2",
    db: AsyncSession = Depends(get_db)
):
    """Compare odds from all bookmakers for a match."""
    query = select(Odds).options(
        selectinload(Odds.bookmaker)
    ).where(
        and_(Odds.match_id == match_id, Odds.market_type == market_type)
    )
    
    result = await db.execute(query)
    odds_list = result.scalars().all()
    
    if not odds_list:
        raise HTTPException(status_code=404, detail="No odds found for this match")
    
    # Find best odds
    best_home = max(odds_list, key=lambda x: x.home_odds or 0, default=None)
    best_draw = max(odds_list, key=lambda x: x.draw_odds or 0, default=None)
    best_away = max(odds_list, key=lambda x: x.away_odds or 0, default=None)
    
    return OddsComparison(
        match_id=match_id,
        market_type=market_type,
        bookmakers=[
            {
                "bookmaker": o.bookmaker.name if o.bookmaker else "Unknown",
                "home_odds": o.home_odds,
                "draw_odds": o.draw_odds,
                "away_odds": o.away_odds,
            }
            for o in odds_list
        ],
        best_home_odds={"bookmaker": best_home.bookmaker.name, "odds": best_home.home_odds} if best_home and best_home.home_odds else None,
        best_draw_odds={"bookmaker": best_draw.bookmaker.name, "odds": best_draw.draw_odds} if best_draw and best_draw.draw_odds else None,
        best_away_odds={"bookmaker": best_away.bookmaker.name, "odds": best_away.away_odds} if best_away and best_away.away_odds else None,
    )


@router.get("/value-bets")
async def get_value_bets(
    min_edge: float = Query(5.0, description="Minimum edge percentage"),
    sport_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all identified value bets."""
    query = select(Odds).options(
        selectinload(Odds.match),
        selectinload(Odds.bookmaker)
    ).where(
        and_(
            Odds.is_value_bet == True,
            Odds.value_percentage >= min_edge
        )
    )
    
    result = await db.execute(query)
    value_bets = result.scalars().all()
    
    return [
        {
            "match_id": vb.match_id,
            "match": {
                "home_team_id": vb.match.home_team_id,
                "away_team_id": vb.match.away_team_id,
                "match_date": vb.match.match_date,
            } if vb.match else None,
            "bookmaker": vb.bookmaker.name if vb.bookmaker else "Unknown",
            "market_type": vb.market_type,
            "odds": vb.home_odds or vb.over_odds or vb.yes_odds,
            "edge_percentage": vb.value_percentage,
        }
        for vb in value_bets
    ]
