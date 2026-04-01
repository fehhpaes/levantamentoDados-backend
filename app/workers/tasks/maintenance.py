"""
Maintenance tasks for cleanup and system health.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
import logging

from celery import shared_task
from sqlalchemy import select, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models import Match, OddsHistory, Prediction, PredictionResult
from app.models.webhook import WebhookDelivery, WebhookStatus
from app.services.webhook import WebhookService

logger = logging.getLogger(__name__)


def get_async_session() -> async_sessionmaker[AsyncSession]:
    """Create async session for Celery tasks."""
    engine = create_async_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _cleanup_old_data_async(
    odds_history_days: int = 90,
    webhook_delivery_days: int = 30
) -> Dict[str, Any]:
    """
    Clean up old data to save storage.
    
    Args:
        odds_history_days: Days to keep odds history
        webhook_delivery_days: Days to keep webhook deliveries
        
    Returns:
        Cleanup summary
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            now = datetime.utcnow()
            
            # Clean old odds history
            odds_cutoff = now - timedelta(days=odds_history_days)
            result = await db.execute(
                delete(OddsHistory).where(
                    OddsHistory.timestamp < odds_cutoff
                )
            )
            odds_deleted = result.rowcount
            
            # Clean old webhook deliveries
            webhook_cutoff = now - timedelta(days=webhook_delivery_days)
            result = await db.execute(
                delete(WebhookDelivery).where(
                    and_(
                        WebhookDelivery.created_at < webhook_cutoff,
                        WebhookDelivery.status.in_([
                            WebhookStatus.DELIVERED.value,
                            WebhookStatus.FAILED.value
                        ])
                    )
                )
            )
            webhooks_deleted = result.rowcount
            
            await db.commit()
            
            logger.info(
                f"Cleanup complete: {odds_deleted} odds history, "
                f"{webhooks_deleted} webhook deliveries removed"
            )
            
            return {
                "success": True,
                "odds_history_deleted": odds_deleted,
                "webhook_deliveries_deleted": webhooks_deleted
            }
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            await db.rollback()
            return {"success": False, "error": str(e)}


async def _retry_failed_webhooks_async() -> Dict[str, Any]:
    """
    Retry failed webhook deliveries.
    
    Returns:
        Retry summary
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            service = WebhookService(db)
            count = await service.retry_failed_deliveries()
            await service.close()
            
            return {
                "success": True,
                "retried_count": count
            }
            
        except Exception as e:
            logger.error(f"Webhook retry failed: {e}")
            return {"success": False, "error": str(e)}


async def _generate_daily_stats_async() -> Dict[str, Any]:
    """
    Generate daily statistics report.
    
    Returns:
        Daily stats
    """
    SessionLocal = get_async_session()
    
    async with SessionLocal() as db:
        try:
            now = datetime.utcnow()
            yesterday = now - timedelta(days=1)
            
            # Count matches
            result = await db.execute(
                select(func.count(Match.id)).where(
                    and_(
                        Match.match_date >= yesterday,
                        Match.match_date < now
                    )
                )
            )
            matches_count = result.scalar() or 0
            
            # Count finished matches
            result = await db.execute(
                select(func.count(Match.id)).where(
                    and_(
                        Match.match_date >= yesterday,
                        Match.match_date < now,
                        Match.status == "finished"
                    )
                )
            )
            finished_count = result.scalar() or 0
            
            # Count predictions
            result = await db.execute(
                select(func.count(Prediction.id)).where(
                    Prediction.created_at >= yesterday
                )
            )
            predictions_count = result.scalar() or 0
            
            # Count correct predictions
            result = await db.execute(
                select(func.count(PredictionResult.id)).where(
                    and_(
                        PredictionResult.created_at >= yesterday,
                        PredictionResult.is_correct == True
                    )
                )
            )
            correct_count = result.scalar() or 0
            
            # Total results from yesterday
            result = await db.execute(
                select(func.count(PredictionResult.id)).where(
                    PredictionResult.created_at >= yesterday
                )
            )
            total_results = result.scalar() or 0
            
            accuracy = (
                round(correct_count / total_results * 100, 2)
                if total_results > 0 else 0
            )
            
            stats = {
                "date": yesterday.date().isoformat(),
                "matches_total": matches_count,
                "matches_finished": finished_count,
                "predictions_made": predictions_count,
                "predictions_evaluated": total_results,
                "predictions_correct": correct_count,
                "accuracy": accuracy
            }
            
            logger.info(f"Daily stats: {stats}")
            
            return {
                "success": True,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Stats generation failed: {e}")
            return {"success": False, "error": str(e)}


async def _health_check_async() -> Dict[str, Any]:
    """
    Perform system health check.
    
    Returns:
        Health status
    """
    SessionLocal = get_async_session()
    
    health = {
        "database": False,
        "redis": False,
        "scrapers": False,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Check database
    try:
        async with SessionLocal() as db:
            await db.execute(select(1))
            health["database"] = True
    except Exception as e:
        health["database_error"] = str(e)
    
    # Check Redis
    try:
        from app.core.redis import cache
        await cache.connect()
        await cache.set("health_check", "ok", ttl=10)
        result = await cache.get("health_check")
        health["redis"] = result == "ok"
    except Exception as e:
        health["redis_error"] = str(e)
    
    # Overall status
    health["healthy"] = all([health["database"], health["redis"]])
    
    return health


# Celery Tasks

@shared_task(
    bind=True,
    name="app.workers.tasks.maintenance.cleanup_old_data",
    max_retries=2,
    default_retry_delay=300
)
def cleanup_old_data(
    self,
    odds_history_days: int = 90,
    webhook_delivery_days: int = 30
) -> Dict[str, Any]:
    """
    Clean up old data from the database.
    
    Args:
        odds_history_days: Days to keep odds history
        webhook_delivery_days: Days to keep webhook deliveries
        
    Returns:
        Cleanup summary
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            _cleanup_old_data_async(odds_history_days, webhook_delivery_days)
        )
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        raise self.retry(exc=e)


@shared_task(
    name="app.workers.tasks.maintenance.retry_failed_webhooks",
)
def retry_failed_webhooks() -> Dict[str, Any]:
    """
    Retry failed webhook deliveries.
    
    Returns:
        Retry summary
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_retry_failed_webhooks_async())
    loop.close()
    
    return result


@shared_task(
    name="app.workers.tasks.maintenance.generate_daily_stats",
)
def generate_daily_stats() -> Dict[str, Any]:
    """
    Generate daily statistics report.
    
    Returns:
        Daily stats
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_generate_daily_stats_async())
    loop.close()
    
    return result


@shared_task(
    name="app.workers.tasks.maintenance.health_check",
)
def health_check() -> Dict[str, Any]:
    """
    Perform system health check.
    
    Returns:
        Health status
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_health_check_async())
    loop.close()
    
    return result


@shared_task(
    name="app.workers.tasks.maintenance.backup_database",
)
def backup_database() -> Dict[str, Any]:
    """
    Trigger database backup.
    
    This is a placeholder - actual backup implementation
    depends on your infrastructure (pg_dump, cloud backups, etc.)
    
    Returns:
        Backup status
    """
    logger.info("Database backup task triggered")
    
    # Placeholder - implement based on your backup strategy
    # Example: run pg_dump, upload to S3, etc.
    
    return {
        "success": True,
        "message": "Backup task triggered",
        "timestamp": datetime.utcnow().isoformat()
    }
