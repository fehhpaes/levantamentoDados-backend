from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta

from app.models.match import Match, MatchStatistics, MatchEvent, MatchStatus
from app.models.sport import Team, League

router = APIRouter()


@router.get("/", response_model=List[Match])
async def list_matches(
    league_id: Optional[str] = None,
    team_id: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = {}
    if league_id:
        query["league_id"] = league_id
    if team_id:
        query["$or"] = [{"home_team_id": team_id}, {"away_team_id": team_id}]
    if status:
        query["status"] = status
    if date_from:
        query["match_date"] = {"$gte": date_from}
    if date_to:
        if "match_date" in query:
            query["match_date"]["$lte"] = date_to
        else:
            query["match_date"] = {"$lte": date_to}
    return await Match.find(query).sort("-match_date").skip(skip).limit(limit).to_list()


@router.get("/live", response_model=List[Match])
async def get_live_matches():
    return await Match.find(
        {"status": {"$in": [MatchStatus.LIVE.value, MatchStatus.HALFTIME.value]}}
    ).to_list()


@router.get("/today", response_model=List[Match])
async def get_today_matches():
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    return await Match.find(
        {"match_date": {"$gte": today_start, "$lt": today_end}}
    ).sort("match_date").to_list()


@router.post("/", response_model=Match, status_code=201)
async def create_match(match: Match):
    await match.save()
    return match


@router.get("/{match_id}", response_model=Match)
async def get_match_details(match_id: str):
    match = await Match.get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.put("/{match_id}/score", response_model=Match)
async def update_match_score(
    match_id: str,
    home_score: Optional[int] = None,
    away_score: Optional[int] = None,
    home_score_ht: Optional[int] = None,
    away_score_ht: Optional[int] = None,
    status: Optional[str] = None,
):
    match = await Match.get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if home_score is not None:
        match.home_score = home_score
    if away_score is not None:
        match.away_score = away_score
    if home_score_ht is not None:
        match.home_score_ht = home_score_ht
    if away_score_ht is not None:
        match.away_score_ht = away_score_ht
    if status:
        match.status = status
    await match.save()
    return match


@router.post("/{match_id}/statistics", response_model=MatchStatistics, status_code=201)
async def add_match_statistics(match_id: str, statistics: MatchStatistics):
    match = await Match.get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    statistics.match_id = match_id
    existing = await MatchStatistics.find_one({"match_id": match_id})
    if existing:
        for key, value in statistics.model_dump(exclude_unset=True).items():
            setattr(existing, key, value)
        await existing.save()
        return existing
    await statistics.save()
    return statistics


@router.post("/{match_id}/events", response_model=MatchEvent, status_code=201)
async def add_match_event(match_id: str, event: MatchEvent):
    match = await Match.get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    event.match_id = match_id
    await event.save()
    return event


@router.get("/{match_id}/head-to-head", response_model=List[Match])
async def get_head_to_head(
    match_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    match = await Match.get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return await Match.find(
        {
            "status": MatchStatus.FINISHED.value,
            "$or": [
                {"home_team_id": match.home_team_id, "away_team_id": match.away_team_id},
                {"home_team_id": match.away_team_id, "away_team_id": match.home_team_id},
            ]
        }
    ).sort("-match_date").limit(limit).to_list()
