from fastapi import APIRouter, Header, HTTPException
from datetime import datetime
from loguru import logger

from app.core.config import settings
from app.models.sport import Sport, League, Team
from app.models.match import Match, MatchStatus
from app.models.odds import Bookmaker, Odds
from app.scrapers.football.football_data import FootballDataScraper
from app.scrapers.odds import TheOddsAPIScraper

router = APIRouter()

CRON_SECRET = "cron-sports-data-2024"


def verify_cron(x_cron_secret: str = Header(None)):
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Invalid cron secret")


@router.get("/update-matches")
async def update_matches(x_cron_secret: str = Header(None)):
    verify_cron(x_cron_secret)
    scraper = FootballDataScraper()
    result = await scraper.get_today_matches()
    if not result.success:
        return {"error": result.error}
    matches_data = await scraper.parse(result.data)
    count = 0
    for md in matches_data:
        match_info = scraper.transform_match(md)
        home_name = match_info.get("home_team_name")
        away_name = match_info.get("away_team_name")
        if not home_name or not away_name:
            continue
        home_team = await Team.find_one({"name": home_name})
        away_team = await Team.find_one({"name": away_name})
        if not home_team or not away_team:
            continue
        existing = await Match.find_one({"external_id": match_info.get("external_id")})
        if existing:
            existing.status = match_info.get("status", existing.status)
            existing.home_score = match_info.get("home_score", existing.home_score)
            existing.away_score = match_info.get("away_score", existing.away_score)
            existing.home_score_ht = match_info.get("home_score_ht", existing.home_score_ht)
            existing.away_score_ht = match_info.get("away_score_ht", existing.away_score_ht)
            await existing.save()
        else:
            league = await League.find_one({"external_id": match_info.get("league_external_id")})
            if not league:
                continue
            match = Match(
                league_id=str(league.id),
                home_team_id=str(home_team.id),
                away_team_id=str(away_team.id),
                match_date=datetime.fromisoformat(match_info["match_date"].replace("Z", "+00:00")) if match_info.get("match_date") else datetime.utcnow(),
                status=match_info.get("status", "scheduled"),
                home_score=match_info.get("home_score"),
                away_score=match_info.get("away_score"),
                home_score_ht=match_info.get("home_score_ht"),
                away_score_ht=match_info.get("away_score_ht"),
                external_id=match_info.get("external_id"),
                venue=match_info.get("venue"),
                referee=match_info.get("referee"),
                home_team={"id": str(home_team.id), "name": home_team.name, "logo_url": home_team.logo_url},
                away_team={"id": str(away_team.id), "name": away_team.name, "logo_url": away_team.logo_url},
                league={"id": str(league.id), "name": league.name},
            )
            await match.save()
            count += 1
    return {"message": "Matches updated", "new_matches": count, "total_fetched": len(matches_data)}


@router.get("/update-live")
async def update_live(x_cron_secret: str = Header(None)):
    verify_cron(x_cron_secret)
    scraper = FootballDataScraper()
    result = await scraper.get_live_matches()
    if not result.success:
        return {"error": result.error}
    matches_data = await scraper.parse(result.data)
    updated = 0
    for md in matches_data:
        match_info = scraper.transform_match(md)
        existing = await Match.find_one({"external_id": match_info.get("external_id")})
        if existing:
            existing.status = match_info.get("status", "live")
            existing.home_score = match_info.get("home_score")
            existing.away_score = match_info.get("away_score")
            await existing.save()
            updated += 1
    return {"message": "Live matches updated", "updated": updated, "total_live": len(matches_data)}


@router.get("/update-odds")
async def update_odds(x_cron_secret: str = Header(None)):
    verify_cron(x_cron_secret)
    if not settings.THE_ODDS_API_KEY:
        return {"error": "THE_ODDS_API_KEY not configured"}
    scraper = TheOddsAPIScraper()
    result = await scraper.get_odds(sport="soccer_epl")
    if not result.success:
        return {"error": result.error}
    odds_data = await scraper.parse(result.data)
    count = 0
    for od in odds_data[:50]:
        match = await Match.find_one({"external_id": od.get("match_external_id")})
        if not match:
            continue
        bookmaker = await Bookmaker.find_one({"name": od.get("bookmaker_name")})
        if not bookmaker:
            bookmaker = Bookmaker(name=od.get("bookmaker_name", "Unknown"), slug=od.get("bookmaker_name", "unknown").lower().replace(" ", "-"))
            await bookmaker.save()
        existing = await Odds.find_one({
            "match_id": str(match.id),
            "bookmaker_id": str(bookmaker.id),
            "market_type": od.get("market_type", "1X2"),
        })
        if existing:
            existing.home_odds = od.get("home_odds")
            existing.draw_odds = od.get("draw_odds")
            existing.away_odds = od.get("away_odds")
            existing.odds_updated_at = datetime.utcnow()
            await existing.save()
        else:
            odds = Odds(
                match_id=str(match.id),
                bookmaker_id=str(bookmaker.id),
                market_type=od.get("market_type", "1X2"),
                home_odds=od.get("home_odds"),
                draw_odds=od.get("draw_odds"),
                away_odds=od.get("away_odds"),
                odds_updated_at=datetime.utcnow(),
            )
            await odds.save()
            count += 1
    return {"message": "Odds updated", "new_odds": count, "total_fetched": len(odds_data)}


@router.get("/update-all")
async def update_all(x_cron_secret: str = Header(None)):
    verify_cron(x_cron_secret)
    results = {}
    try:
        results["matches"] = await update_matches(x_cron_secret)
    except Exception as e:
        results["matches"] = {"error": str(e)}
    try:
        results["live"] = await update_live(x_cron_secret)
    except Exception as e:
        results["live"] = {"error": str(e)}
    try:
        results["odds"] = await update_odds(x_cron_secret)
    except Exception as e:
        results["odds"] = {"error": str(e)}
    return {"message": "All data updated", "results": results}
