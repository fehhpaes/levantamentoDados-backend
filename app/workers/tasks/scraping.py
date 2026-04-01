"""
Scraping tasks for collecting sports data.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from celery import shared_task
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models import Match, League, Team, Sport
from app.scrapers.football.football_data import FootballDataScraper
from app.scrapers.sofascore import SofascoreScraper
from app.scrapers.api_sports import APISportsScraper

logger = logging.getLogger(__name__)


def get_async_session() -> async_sessionmaker[AsyncSession]:
    """Create async session for Celery tasks."""
    engine = create_async_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _scrape_football_matches_async(
    league_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Async implementation of football match scraping.
    
    Args:
        league_ids: Optional list of league IDs to scrape
        
    Returns:
        Result summary
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            # Get active leagues
            query = select(League).where(League.is_active == True)
            if league_ids:
                query = query.where(League.id.in_(league_ids))
            
            result = await db.execute(query)
            leagues = list(result.scalars().all())
            
            if not leagues:
                logger.warning("No active leagues found to scrape")
                return {"success": True, "matches_found": 0, "message": "No leagues to scrape"}
            
            total_matches = 0
            errors = []
            
            # Initialize scrapers
            scrapers = []
            
            if settings.FOOTBALL_DATA_API_KEY:
                scrapers.append(FootballDataScraper(settings.FOOTBALL_DATA_API_KEY))
            
            if settings.API_SPORTS_KEY:
                scrapers.append(APISportsScraper(settings.API_SPORTS_KEY))
            
            # Try SofaScore as fallback (no API key needed)
            scrapers.append(SofascoreScraper())
            
            for league in leagues:
                try:
                    for scraper in scrapers:
                        try:
                            matches = await scraper.get_upcoming_matches(
                                league_id=league.external_id,
                                days_ahead=7
                            )
                            
                            if matches:
                                # Save matches to database
                                for match_data in matches:
                                    await _save_match(db, league, match_data)
                                
                                total_matches += len(matches)
                                logger.info(
                                    f"Scraped {len(matches)} matches for {league.name} "
                                    f"using {scraper.__class__.__name__}"
                                )
                                break  # Success, move to next league
                                
                        except Exception as e:
                            logger.warning(
                                f"Scraper {scraper.__class__.__name__} failed for "
                                f"{league.name}: {e}"
                            )
                            continue
                            
                except Exception as e:
                    error_msg = f"Failed to scrape league {league.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            await db.commit()
            
            return {
                "success": True,
                "matches_found": total_matches,
                "leagues_processed": len(leagues),
                "errors": errors if errors else None
            }
            
        except Exception as e:
            logger.error(f"Football scraping failed: {e}")
            await db.rollback()
            return {
                "success": False,
                "error": str(e)
            }


async def _save_match(
    db: AsyncSession,
    league: League,
    match_data: Dict[str, Any]
) -> Optional[Match]:
    """Save or update a match in the database."""
    try:
        # Check if match already exists
        external_id = match_data.get("external_id")
        
        if external_id:
            result = await db.execute(
                select(Match).where(Match.external_id == external_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing match
                for key, value in match_data.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                return existing
        
        # Get or create teams
        home_team = await _get_or_create_team(
            db, 
            match_data.get("home_team_name"),
            match_data.get("home_team_external_id"),
            league.sport_id
        )
        
        away_team = await _get_or_create_team(
            db,
            match_data.get("away_team_name"),
            match_data.get("away_team_external_id"),
            league.sport_id
        )
        
        # Create new match
        match = Match(
            external_id=external_id,
            league_id=league.id,
            home_team_id=home_team.id if home_team else None,
            away_team_id=away_team.id if away_team else None,
            match_date=match_data.get("match_date"),
            status=match_data.get("status", "scheduled"),
            home_score=match_data.get("home_score"),
            away_score=match_data.get("away_score"),
            venue=match_data.get("venue"),
            round=match_data.get("round"),
        )
        
        db.add(match)
        return match
        
    except Exception as e:
        logger.error(f"Failed to save match: {e}")
        return None


async def _get_or_create_team(
    db: AsyncSession,
    name: str,
    external_id: Optional[str],
    sport_id: int
) -> Optional[Team]:
    """Get existing team or create new one."""
    if not name:
        return None
    
    try:
        # Try to find by external_id first
        if external_id:
            result = await db.execute(
                select(Team).where(Team.external_id == external_id)
            )
            team = result.scalar_one_or_none()
            if team:
                return team
        
        # Try to find by name
        result = await db.execute(
            select(Team).where(
                and_(Team.name == name, Team.sport_id == sport_id)
            )
        )
        team = result.scalar_one_or_none()
        
        if team:
            return team
        
        # Create new team
        team = Team(
            name=name,
            external_id=external_id,
            sport_id=sport_id,
        )
        db.add(team)
        await db.flush()
        
        return team
        
    except Exception as e:
        logger.error(f"Failed to get/create team {name}: {e}")
        return None


async def _scrape_live_matches_async() -> Dict[str, Any]:
    """Scrape currently live matches."""
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            scrapers = []
            
            if settings.API_SPORTS_KEY:
                scrapers.append(APISportsScraper(settings.API_SPORTS_KEY))
            
            scrapers.append(SofascoreScraper())
            
            total_live = 0
            
            for scraper in scrapers:
                try:
                    live_matches = await scraper.get_live_matches()
                    
                    if live_matches:
                        for match_data in live_matches:
                            external_id = match_data.get("external_id")
                            if not external_id:
                                continue
                            
                            # Update existing match
                            result = await db.execute(
                                select(Match).where(Match.external_id == external_id)
                            )
                            match = result.scalar_one_or_none()
                            
                            if match:
                                match.status = match_data.get("status", "live")
                                match.home_score = match_data.get("home_score")
                                match.away_score = match_data.get("away_score")
                                match.minute = match_data.get("minute")
                                total_live += 1
                        
                        await db.commit()
                        logger.info(f"Updated {total_live} live matches")
                        break
                        
                except Exception as e:
                    logger.warning(f"Live scraper {scraper.__class__.__name__} failed: {e}")
                    continue
            
            return {
                "success": True,
                "live_matches_updated": total_live
            }
            
        except Exception as e:
            logger.error(f"Live scraping failed: {e}")
            await db.rollback()
            return {
                "success": False,
                "error": str(e)
            }


# Celery Tasks

@shared_task(
    bind=True,
    name="app.workers.tasks.scraping.scrape_football_matches",
    max_retries=3,
    default_retry_delay=300
)
def scrape_football_matches(
    self,
    league_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Celery task to scrape football matches.
    
    Args:
        league_ids: Optional list of specific league IDs to scrape
        
    Returns:
        Result summary
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            _scrape_football_matches_async(league_ids)
        )
        loop.close()
        
        if not result.get("success"):
            raise Exception(result.get("error", "Unknown error"))
        
        return result
        
    except Exception as e:
        logger.error(f"Scrape football matches task failed: {e}")
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    name="app.workers.tasks.scraping.scrape_live_matches",
    max_retries=2,
    default_retry_delay=60
)
def scrape_live_matches(self) -> Dict[str, Any]:
    """
    Celery task to scrape live match updates.
    
    Returns:
        Result summary
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_scrape_live_matches_async())
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error(f"Scrape live matches task failed: {e}")
        raise self.retry(exc=e)


@shared_task(
    name="app.workers.tasks.scraping.scrape_league",
)
def scrape_league(league_id: int) -> Dict[str, Any]:
    """
    Scrape matches for a specific league.
    
    Args:
        league_id: ID of the league to scrape
        
    Returns:
        Result summary
    """
    return scrape_football_matches.delay([league_id])


@shared_task(
    name="app.workers.tasks.scraping.scrape_historical_matches",
)
def scrape_historical_matches(
    league_id: int,
    season: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scrape historical matches for backtesting.
    
    Args:
        league_id: League to scrape
        season: Season identifier (e.g., "2023-2024")
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        
    Returns:
        Result summary
    """
    async def _scrape():
        SessionLocal = get_async_session()
        
        async with SessionLocal() as db:
            result = await db.execute(
                select(League).where(League.id == league_id)
            )
            league = result.scalar_one_or_none()
            
            if not league:
                return {"success": False, "error": "League not found"}
            
            # Use Football-Data.org for historical data
            if not settings.FOOTBALL_DATA_API_KEY:
                return {"success": False, "error": "No API key for historical data"}
            
            scraper = FootballDataScraper(settings.FOOTBALL_DATA_API_KEY)
            
            try:
                matches = await scraper.get_historical_matches(
                    league_id=league.external_id,
                    season=season,
                    date_from=start_date,
                    date_to=end_date
                )
                
                saved = 0
                for match_data in matches:
                    await _save_match(db, league, match_data)
                    saved += 1
                
                await db.commit()
                
                return {
                    "success": True,
                    "matches_saved": saved,
                    "league": league.name,
                    "season": season
                }
                
            except Exception as e:
                logger.error(f"Historical scraping failed: {e}")
                return {"success": False, "error": str(e)}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_scrape())
    loop.close()
    
    return result
