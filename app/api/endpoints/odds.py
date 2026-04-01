from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from app.models.odds import Bookmaker, Odds, OddsHistory
from app.models.match import Match

router = APIRouter()


# ===================== BOOKMAKERS =====================

@router.get("/bookmakers", response_model=List[Bookmaker])
async def list_bookmakers(
    is_active: Optional[bool] = None,
):
    query = {}
    if is_active is not None:
        query["is_active"] = is_active
    return await Bookmaker.find(query).to_list()


@router.post("/bookmakers", response_model=Bookmaker, status_code=201)
async def create_bookmaker(bookmaker: Bookmaker):
    await bookmaker.save()
    return bookmaker


# ===================== ODDS =====================

@router.get("/match/{match_id}", response_model=List[Odds])
async def get_match_odds(
    match_id: str,
    market_type: Optional[str] = None,
):
    query = {"match_id": match_id}
    if market_type:
        query["market_type"] = market_type
    return await Odds.find(query).to_list()


@router.post("/", response_model=Odds, status_code=201)
async def create_or_update_odds(odds: Odds):
    existing = await Odds.find_one(
        {"match_id": odds.match_id, "bookmaker_id": odds.bookmaker_id, "market_type": odds.market_type}
    )
    if existing:
        if odds.home_odds is not None:
            existing.home_odds = odds.home_odds
        if odds.draw_odds is not None:
            existing.draw_odds = odds.draw_odds
        if odds.away_odds is not None:
            existing.away_odds = odds.away_odds
        if odds.over_odds is not None:
            existing.over_odds = odds.over_odds
        if odds.under_odds is not None:
            existing.under_odds = odds.under_odds
        if odds.line is not None:
            existing.line = odds.line
        if odds.yes_odds is not None:
            existing.yes_odds = odds.yes_odds
        if odds.no_odds is not None:
            existing.no_odds = odds.no_odds
        if odds.is_value_bet is not None:
            existing.is_value_bet = odds.is_value_bet
        if odds.value_percentage is not None:
            existing.value_percentage = odds.value_percentage
        existing.odds_updated_at = datetime.utcnow()
        if existing.home_odds and existing.draw_odds and existing.away_odds:
            total = (1/existing.home_odds) + (1/existing.draw_odds) + (1/existing.away_odds)
            existing.home_prob = (1/existing.home_odds) / total
            existing.draw_prob = (1/existing.draw_odds) / total
            existing.away_prob = (1/existing.away_odds) / total
        await existing.save()
        return existing
    else:
        odds.odds_updated_at = datetime.utcnow()
        if odds.home_odds and odds.draw_odds and odds.away_odds:
            total = (1/odds.home_odds) + (1/odds.draw_odds) + (1/odds.away_odds)
            odds.home_prob = (1/odds.home_odds) / total
            odds.draw_prob = (1/odds.draw_odds) / total
            odds.away_prob = (1/odds.away_odds) / total
        await odds.save()
        return odds


@router.get("/match/{match_id}/history", response_model=List[OddsHistory])
async def get_odds_history(
    match_id: str,
    bookmaker_id: Optional[str] = None,
    market_type: Optional[str] = None,
):
    query = {"match_id": match_id}
    if bookmaker_id:
        query["bookmaker_id"] = bookmaker_id
    if market_type:
        query["market_type"] = market_type
    return await OddsHistory.find(query).sort("recorded_at").to_list()


@router.get("/match/{match_id}/comparison")
async def compare_odds(
    match_id: str,
    market_type: str = "1X2",
):
    odds_list = await Odds.find(
        {"match_id": match_id, "market_type": market_type}
    ).to_list()
    if not odds_list:
        raise HTTPException(status_code=404, detail="No odds found for this match")
    best_home = max(odds_list, key=lambda x: x.home_odds or 0, default=None)
    best_draw = max(odds_list, key=lambda x: x.draw_odds or 0, default=None)
    best_away = max(odds_list, key=lambda x: x.away_odds or 0, default=None)
    return {
        "match_id": match_id,
        "market_type": market_type,
        "bookmakers": [
            {
                "bookmaker_id": o.bookmaker_id,
                "home_odds": o.home_odds,
                "draw_odds": o.draw_odds,
                "away_odds": o.away_odds,
            }
            for o in odds_list
        ],
        "best_home_odds": {"bookmaker_id": best_home.bookmaker_id, "odds": best_home.home_odds} if best_home and best_home.home_odds else None,
        "best_draw_odds": {"bookmaker_id": best_draw.bookmaker_id, "odds": best_draw.draw_odds} if best_draw and best_draw.draw_odds else None,
        "best_away_odds": {"bookmaker_id": best_away.bookmaker_id, "odds": best_away.away_odds} if best_away and best_away.away_odds else None,
    }


@router.get("/value-bets")
async def get_value_bets(
    min_edge: float = Query(5.0, description="Minimum edge percentage"),
):
    return await Odds.find(
        {"is_value_bet": True, "value_percentage": {"$gte": min_edge}}
    ).to_list()
