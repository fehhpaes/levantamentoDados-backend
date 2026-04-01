"""
Odds-related tasks for updating and analyzing odds.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from celery import shared_task
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models import Match, Odds, OddsHistory, Bookmaker
from app.scrapers.odds import OddsScraper
from app.services.odds_comparator import OddsComparator
from app.services.webhook import trigger_webhook_event
from app.schemas.webhook import WebhookEventType

logger = logging.getLogger(__name__)


def get_async_session() -> async_sessionmaker[AsyncSession]:
    """Create async session for Celery tasks."""
    engine = create_async_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _update_odds_async(match_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    Update odds for matches.
    
    Args:
        match_ids: Optional list of specific match IDs
        
    Returns:
        Result summary
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            # Get upcoming matches
            now = datetime.utcnow()
            query = select(Match).where(
                and_(
                    Match.match_date > now,
                    Match.match_date < now + timedelta(days=7),
                    Match.status.in_(["scheduled", "upcoming"])
                )
            )
            
            if match_ids:
                query = query.where(Match.id.in_(match_ids))
            
            result = await db.execute(query)
            matches = list(result.scalars().all())
            
            if not matches:
                return {"success": True, "odds_updated": 0, "message": "No matches to update"}
            
            # Initialize odds scraper
            scraper = OddsScraper(api_key=settings.THE_ODDS_API_KEY)
            
            total_updated = 0
            significant_changes = []
            
            for match in matches:
                try:
                    # Get odds from multiple bookmakers
                    odds_data = await scraper.get_odds(
                        match_id=match.external_id,
                        sport=match.league.sport.slug if match.league and match.league.sport else "soccer"
                    )
                    
                    if not odds_data:
                        continue
                    
                    for bookmaker_odds in odds_data:
                        # Save odds
                        bookmaker = await _get_or_create_bookmaker(
                            db, 
                            bookmaker_odds.get("bookmaker_name"),
                            bookmaker_odds.get("bookmaker_key")
                        )
                        
                        if not bookmaker:
                            continue
                        
                        # Check for existing odds
                        result = await db.execute(
                            select(Odds).where(
                                and_(
                                    Odds.match_id == match.id,
                                    Odds.bookmaker_id == bookmaker.id
                                )
                            )
                        )
                        existing_odds = result.scalar_one_or_none()
                        
                        old_odds = None
                        if existing_odds:
                            old_odds = {
                                "home": existing_odds.home_odds,
                                "draw": existing_odds.draw_odds,
                                "away": existing_odds.away_odds
                            }
                            
                            # Update odds
                            existing_odds.home_odds = bookmaker_odds.get("home_odds")
                            existing_odds.draw_odds = bookmaker_odds.get("draw_odds")
                            existing_odds.away_odds = bookmaker_odds.get("away_odds")
                            existing_odds.over_25 = bookmaker_odds.get("over_25")
                            existing_odds.under_25 = bookmaker_odds.get("under_25")
                            existing_odds.btts_yes = bookmaker_odds.get("btts_yes")
                            existing_odds.btts_no = bookmaker_odds.get("btts_no")
                        else:
                            # Create new odds
                            existing_odds = Odds(
                                match_id=match.id,
                                bookmaker_id=bookmaker.id,
                                home_odds=bookmaker_odds.get("home_odds"),
                                draw_odds=bookmaker_odds.get("draw_odds"),
                                away_odds=bookmaker_odds.get("away_odds"),
                                over_25=bookmaker_odds.get("over_25"),
                                under_25=bookmaker_odds.get("under_25"),
                                btts_yes=bookmaker_odds.get("btts_yes"),
                                btts_no=bookmaker_odds.get("btts_no"),
                            )
                            db.add(existing_odds)
                        
                        # Save to history
                        history = OddsHistory(
                            match_id=match.id,
                            bookmaker_id=bookmaker.id,
                            home_odds=bookmaker_odds.get("home_odds"),
                            draw_odds=bookmaker_odds.get("draw_odds"),
                            away_odds=bookmaker_odds.get("away_odds"),
                            timestamp=datetime.utcnow()
                        )
                        db.add(history)
                        
                        # Check for significant changes
                        if old_odds:
                            change = _check_significant_change(old_odds, bookmaker_odds)
                            if change:
                                significant_changes.append({
                                    "match_id": match.id,
                                    "bookmaker": bookmaker.name,
                                    **change
                                })
                        
                        total_updated += 1
                
                except Exception as e:
                    logger.error(f"Failed to update odds for match {match.id}: {e}")
                    continue
            
            await db.commit()
            
            # Trigger webhooks for significant changes
            if significant_changes:
                for change in significant_changes:
                    await trigger_webhook_event(
                        db,
                        WebhookEventType.ODDS_CHANGE,
                        change
                    )
            
            return {
                "success": True,
                "odds_updated": total_updated,
                "matches_processed": len(matches),
                "significant_changes": len(significant_changes)
            }
            
        except Exception as e:
            logger.error(f"Odds update failed: {e}")
            await db.rollback()
            return {"success": False, "error": str(e)}


async def _get_or_create_bookmaker(
    db: AsyncSession,
    name: str,
    key: Optional[str] = None
) -> Optional[Bookmaker]:
    """Get or create a bookmaker."""
    if not name:
        return None
    
    try:
        result = await db.execute(
            select(Bookmaker).where(Bookmaker.name == name)
        )
        bookmaker = result.scalar_one_or_none()
        
        if bookmaker:
            return bookmaker
        
        bookmaker = Bookmaker(
            name=name,
            key=key or name.lower().replace(" ", "_"),
            is_active=True
        )
        db.add(bookmaker)
        await db.flush()
        
        return bookmaker
        
    except Exception as e:
        logger.error(f"Failed to get/create bookmaker {name}: {e}")
        return None


def _check_significant_change(
    old_odds: Dict[str, float],
    new_odds: Dict[str, Any],
    threshold: float = 0.1
) -> Optional[Dict[str, Any]]:
    """
    Check if odds change is significant (> 10% by default).
    
    Returns change details if significant, None otherwise.
    """
    changes = {}
    
    for key in ["home", "draw", "away"]:
        old_val = old_odds.get(key)
        new_val = new_odds.get(f"{key}_odds")
        
        if old_val and new_val and old_val > 0:
            change_pct = abs(new_val - old_val) / old_val
            if change_pct > threshold:
                changes[key] = {
                    "old": old_val,
                    "new": new_val,
                    "change_pct": round(change_pct * 100, 2)
                }
    
    if changes:
        return {
            "changes": changes,
            "direction": "up" if sum(
                c["new"] - c["old"] for c in changes.values()
            ) > 0 else "down"
        }
    
    return None


async def _detect_value_bets_async() -> Dict[str, Any]:
    """
    Detect value betting opportunities.
    
    Returns:
        List of value bets found
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            comparator = OddsComparator(db)
            value_bets = await comparator.find_value_bets(
                min_edge=0.05,  # 5% minimum edge
                min_confidence=0.6
            )
            
            if value_bets:
                # Trigger webhooks
                for bet in value_bets:
                    await trigger_webhook_event(
                        db,
                        WebhookEventType.VALUE_BET_FOUND,
                        bet
                    )
            
            return {
                "success": True,
                "value_bets_found": len(value_bets),
                "bets": value_bets
            }
            
        except Exception as e:
            logger.error(f"Value bet detection failed: {e}")
            return {"success": False, "error": str(e)}


async def _detect_arbitrage_async() -> Dict[str, Any]:
    """
    Detect arbitrage opportunities across bookmakers.
    
    Returns:
        List of arbitrage opportunities
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            comparator = OddsComparator(db)
            arbs = await comparator.find_arbitrage_opportunities(
                min_profit=0.01  # 1% minimum profit
            )
            
            if arbs:
                for arb in arbs:
                    await trigger_webhook_event(
                        db,
                        WebhookEventType.ARBITRAGE_FOUND,
                        arb
                    )
            
            return {
                "success": True,
                "arbitrage_found": len(arbs),
                "opportunities": arbs
            }
            
        except Exception as e:
            logger.error(f"Arbitrage detection failed: {e}")
            return {"success": False, "error": str(e)}


# Celery Tasks

@shared_task(
    bind=True,
    name="app.workers.tasks.odds.update_all_odds",
    max_retries=3,
    default_retry_delay=120
)
def update_all_odds(self, match_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    Update odds for all upcoming matches.
    
    Args:
        match_ids: Optional list of specific matches
        
    Returns:
        Result summary
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_update_odds_async(match_ids))
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error(f"Update odds task failed: {e}")
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    name="app.workers.tasks.odds.detect_value_bets",
    max_retries=2,
    default_retry_delay=60
)
def detect_value_bets(self) -> Dict[str, Any]:
    """
    Detect value betting opportunities.
    
    Returns:
        Value bets found
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_detect_value_bets_async())
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error(f"Detect value bets task failed: {e}")
        raise self.retry(exc=e)


@shared_task(
    name="app.workers.tasks.odds.detect_arbitrage",
)
def detect_arbitrage() -> Dict[str, Any]:
    """
    Detect arbitrage opportunities.
    
    Returns:
        Arbitrage opportunities found
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_detect_arbitrage_async())
    loop.close()
    
    return result


@shared_task(
    name="app.workers.tasks.odds.update_match_odds",
)
def update_match_odds(match_id: int) -> Dict[str, Any]:
    """
    Update odds for a specific match.
    
    Args:
        match_id: Match ID
        
    Returns:
        Result
    """
    return update_all_odds.delay([match_id])
