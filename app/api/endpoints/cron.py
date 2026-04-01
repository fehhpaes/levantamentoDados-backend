from fastapi import APIRouter, Header, HTTPException
from datetime import datetime, timedelta
import httpx
from loguru import logger

from app.core.config import settings
from app.models.sport import Sport, League, Team
from app.models.match import Match, MatchStatus
from app.models.odds import Bookmaker, Odds
from app.models.prediction import Prediction

router = APIRouter()

CRON_SECRET = "cron-sports-data-2024"


def verify_cron(x_cron_secret: str = Header(None)):
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Invalid cron secret")


async def fetch_football_data(endpoint: str, params: dict = None):
    if not settings.FOOTBALL_DATA_API_KEY:
        return None
    url = f"https://api.football-data.org/v4/{endpoint}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params=params,
            headers={"X-Auth-Token": settings.FOOTBALL_DATA_API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_odds_api(sport: str = "soccer_epl"):
    if not settings.THE_ODDS_API_KEY:
        return None
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params={
                "apiKey": settings.THE_ODDS_API_KEY,
                "regions": "eu",
                "markets": "h2h,totals",
                "oddsFormat": "decimal",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


def map_status(api_status: str) -> str:
    status_map = {
        "SCHEDULED": "scheduled",
        "TIMED": "scheduled",
        "IN_PLAY": "live",
        "PAUSED": "halftime",
        "FINISHED": "finished",
        "SUSPENDED": "suspended",
        "POSTPONED": "postponed",
        "CANCELLED": "cancelled",
        "AWARDED": "finished",
    }
    return status_map.get(api_status, "scheduled")


@router.get("/update-matches")
async def update_matches(x_cron_secret: str = Header(None)):
    verify_cron(x_cron_secret)
    if not settings.FOOTBALL_DATA_API_KEY:
        return {"error": "FOOTBALL_DATA_API_KEY not configured", "matches_updated": 0}
    try:
        data = await fetch_football_data("matches", {"dateFrom": (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d"), "dateTo": (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")})
        if not data or "matches" not in data:
            return {"matches_updated": 0, "message": "No matches found"}
        matches_data = data["matches"]
        count = 0
        for md in matches_data:
            home_name = md.get("homeTeam", {}).get("name")
            away_name = md.get("awayTeam", {}).get("name")
            if not home_name or not away_name:
                continue
            home_team = await Team.find_one({"name": home_name})
            away_team = await Team.find_one({"name": away_name})
            if not home_team or not away_team:
                continue
            comp_name = md.get("competition", {}).get("name")
            league = await League.find_one({"name": comp_name})
            if not league:
                continue
            external_id = str(md.get("id"))
            existing = await Match.find_one({"external_id": external_id})
            match_date = datetime.fromisoformat(md["utcDate"].replace("Z", "+00:00"))
            if existing:
                existing.status = map_status(md.get("status"))
                existing.home_score = md.get("score", {}).get("fullTime", {}).get("home")
                existing.away_score = md.get("score", {}).get("fullTime", {}).get("away")
                existing.home_score_ht = md.get("score", {}).get("halfTime", {}).get("home")
                existing.away_score_ht = md.get("score", {}).get("halfTime", {}).get("away")
                await existing.save()
            else:
                match = Match(
                    league_id=str(league.id),
                    home_team_id=str(home_team.id),
                    away_team_id=str(away_team.id),
                    match_date=match_date,
                    status=map_status(md.get("status")),
                    home_score=md.get("score", {}).get("fullTime", {}).get("home"),
                    away_score=md.get("score", {}).get("fullTime", {}).get("away"),
                    home_score_ht=md.get("score", {}).get("halfTime", {}).get("home"),
                    away_score_ht=md.get("score", {}).get("halfTime", {}).get("away"),
                    external_id=external_id,
                    venue=md.get("venue"),
                    home_team={"id": str(home_team.id), "name": home_team.name, "logo_url": home_team.logo_url},
                    away_team={"id": str(away_team.id), "name": away_team.name, "logo_url": away_team.logo_url},
                    league={"id": str(league.id), "name": league.name},
                )
                await match.save()
                count += 1
        return {"message": "Matches updated", "matches_updated": count, "total_fetched": len(matches_data)}
    except Exception as e:
        logger.error(f"Error updating matches: {e}")
        return {"error": str(e)}


@router.get("/update-live")
async def update_live(x_cron_secret: str = Header(None)):
    verify_cron(x_cron_secret)
    if not settings.FOOTBALL_DATA_API_KEY:
        return {"error": "FOOTBALL_DATA_API_KEY not configured", "live_updated": 0}
    try:
        data = await fetch_football_data("matches", {"status": "LIVE"})
        if not data or "matches" not in data:
            return {"live_updated": 0, "message": "No live matches"}
        updated = 0
        for md in data["matches"]:
            external_id = str(md.get("id"))
            existing = await Match.find_one({"external_id": external_id})
            if existing:
                existing.status = map_status(md.get("status"))
                existing.home_score = md.get("score", {}).get("fullTime", {}).get("home")
                existing.away_score = md.get("score", {}).get("fullTime", {}).get("away")
                await existing.save()
                updated += 1
        return {"message": "Live matches updated", "live_updated": updated, "total_live": len(data["matches"])}
    except Exception as e:
        logger.error(f"Error updating live: {e}")
        return {"error": str(e)}


@router.get("/update-odds")
async def update_odds(x_cron_secret: str = Header(None)):
    verify_cron(x_cron_secret)
    if not settings.THE_ODDS_API_KEY:
        return {"error": "THE_ODDS_API_KEY not configured", "odds_updated": 0}
    try:
        sports = ["soccer_epl", "soccer_spain_la_liga", "soccer_brazil_campeonato"]
        total = 0
        for sport in sports:
            data = await fetch_odds_api(sport)
            if not data:
                continue
            for event in data:
                home_name = event.get("home_team")
                away_name = event.get("away_team")
                if not home_name or not away_name:
                    continue
                match = await Match.find_one({
                    "$or": [
                        {"home_team.name": home_name, "away_team.name": away_name},
                        {"home_team.name": away_name, "away_team.name": home_name},
                    ]
                })
                if not match:
                    continue
                for bm in event.get("bookmakers", [])[:5]:
                    bm_name = bm.get("title") or bm.get("key")
                    if not bm_name:
                        continue
                    bookmaker = await Bookmaker.find_one({"name": bm_name})
                    if not bookmaker:
                        bookmaker = Bookmaker(name=bm_name, slug=bm_name.lower().replace(" ", "-"))
                        await bookmaker.save()
                    for market in bm.get("markets", []):
                        market_type = market.get("key")
                        outcomes = market.get("outcomes", [])
                        if market_type == "h2h":
                            home_odds = next((o.get("price") for o in outcomes if o.get("name") == home_name), None)
                            away_odds = next((o.get("price") for o in outcomes if o.get("name") == away_name), None)
                            draw_odds = next((o.get("price") for o in outcomes if o.get("name") == "Draw"), None)
                            existing = await Odds.find_one({
                                "match_id": str(match.id),
                                "bookmaker_id": str(bookmaker.id),
                                "market_type": "1X2",
                            })
                            if existing:
                                existing.home_odds = home_odds
                                existing.draw_odds = draw_odds
                                existing.away_odds = away_odds
                                existing.odds_updated_at = datetime.utcnow()
                                await existing.save()
                            else:
                                odds = Odds(
                                    match_id=str(match.id),
                                    bookmaker_id=str(bookmaker.id),
                                    market_type="1X2",
                                    home_odds=home_odds,
                                    draw_odds=draw_odds,
                                    away_odds=away_odds,
                                    odds_updated_at=datetime.utcnow(),
                                )
                                await odds.save()
                                total += 1
        return {"message": "Odds updated", "odds_updated": total}
    except Exception as e:
        logger.error(f"Error updating odds: {e}")
        return {"error": str(e)}


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
