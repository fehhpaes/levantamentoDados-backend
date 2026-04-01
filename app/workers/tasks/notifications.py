"""
Celery Tasks for Notification Alerts

Handles asynchronous sending of:
- Email digests and alerts
- Telegram notifications
- Push notifications
- Scheduled summaries
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from celery import shared_task
import logging
import asyncio

logger = logging.getLogger(__name__)


# Helper to run async code in Celery tasks
def run_async(coro):
    """Run async coroutine in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============== TELEGRAM NOTIFICATIONS ==============

@shared_task(
    name="notifications.send_telegram_value_bet",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def send_telegram_value_bet(
    self,
    user_ids: List[int],
    home_team: str,
    away_team: str,
    league: str,
    kickoff: str,
    market: str,
    odds: float,
    probability: float,
    edge: float,
    stake: float,
    confidence: float
):
    """Send value bet alert via Telegram."""
    try:
        from app.core.config import settings
        from app.services.telegram import TelegramService, TelegramConfig
        
        config = TelegramConfig(
            bot_token=settings.TELEGRAM_BOT_TOKEN,
            rate_limit_per_second=25
        )
        service = TelegramService(config)
        
        # Load users from database
        # In production, this would fetch from DB
        # For now, using the service's internal user registry
        
        async def send():
            return await service.send_value_bet_alert(
                user_ids=user_ids,
                home_team=home_team,
                away_team=away_team,
                league=league,
                kickoff=kickoff,
                market=market,
                odds=odds,
                probability=probability,
                edge=edge,
                stake=stake,
                confidence=confidence
            )
        
        results = run_async(send())
        
        logger.info(f"Telegram value bet alerts sent: {results}")
        return {"success": True, "results": results}
        
    except Exception as e:
        logger.error(f"Failed to send Telegram value bet: {e}")
        self.retry(exc=e)


@shared_task(
    name="notifications.send_telegram_match_start",
    bind=True,
    max_retries=3,
    default_retry_delay=30
)
def send_telegram_match_start(
    self,
    user_ids: List[int],
    match_data: Dict[str, Any]
):
    """Send match start alert via Telegram."""
    try:
        from app.core.config import settings
        from app.services.telegram import TelegramService, TelegramConfig
        
        config = TelegramConfig(bot_token=settings.TELEGRAM_BOT_TOKEN)
        service = TelegramService(config)
        
        async def send():
            return await service.send_match_start_alert(
                user_ids=user_ids,
                **match_data
            )
        
        results = run_async(send())
        
        logger.info(f"Telegram match start alerts sent: {results}")
        return {"success": True, "results": results}
        
    except Exception as e:
        logger.error(f"Failed to send Telegram match start: {e}")
        self.retry(exc=e)


@shared_task(
    name="notifications.send_telegram_score_update",
    bind=True,
    max_retries=2,
    default_retry_delay=10
)
def send_telegram_score_update(
    self,
    user_ids: List[int],
    score_data: Dict[str, Any]
):
    """Send live score update via Telegram."""
    try:
        from app.core.config import settings
        from app.services.telegram import TelegramService, TelegramConfig
        
        config = TelegramConfig(bot_token=settings.TELEGRAM_BOT_TOKEN)
        service = TelegramService(config)
        
        async def send():
            return await service.send_score_update(
                user_ids=user_ids,
                **score_data
            )
        
        results = run_async(send())
        
        logger.info(f"Telegram score updates sent: {results}")
        return {"success": True, "results": results}
        
    except Exception as e:
        logger.error(f"Failed to send Telegram score update: {e}")
        # Don't retry too much for live updates - they become stale
        if self.request.retries < 1:
            self.retry(exc=e)
        return {"success": False, "error": str(e)}


@shared_task(
    name="notifications.send_telegram_odds_movement",
    bind=True,
    max_retries=2
)
def send_telegram_odds_movement(
    self,
    user_ids: List[int],
    odds_data: Dict[str, Any]
):
    """Send odds movement alert via Telegram."""
    try:
        from app.core.config import settings
        from app.services.telegram import TelegramService, TelegramConfig
        
        config = TelegramConfig(bot_token=settings.TELEGRAM_BOT_TOKEN)
        service = TelegramService(config)
        
        async def send():
            return await service.send_odds_movement_alert(
                user_ids=user_ids,
                **odds_data
            )
        
        results = run_async(send())
        
        logger.info(f"Telegram odds movement alerts sent: {results}")
        return {"success": True, "results": results}
        
    except Exception as e:
        logger.error(f"Failed to send Telegram odds movement: {e}")
        self.retry(exc=e)


@shared_task(name="notifications.send_telegram_daily_summary")
def send_telegram_daily_summary(summary_data: Dict[str, Any]):
    """Send daily summary to all subscribed users via Telegram."""
    try:
        from app.core.config import settings
        from app.services.telegram import TelegramService, TelegramConfig
        
        config = TelegramConfig(bot_token=settings.TELEGRAM_BOT_TOKEN)
        service = TelegramService(config)
        
        # Get users subscribed to daily summary
        user_ids = service.get_users_for_alert_type("daily_summary")
        
        async def send():
            return await service.send_daily_summary(
                user_ids=user_ids,
                **summary_data
            )
        
        results = run_async(send())
        
        logger.info(f"Telegram daily summaries sent to {len(user_ids)} users")
        return {"success": True, "sent_to": len(user_ids), "results": results}
        
    except Exception as e:
        logger.error(f"Failed to send Telegram daily summary: {e}")
        return {"success": False, "error": str(e)}


# ============== EMAIL NOTIFICATIONS ==============

@shared_task(
    name="notifications.send_email_value_bet",
    bind=True,
    max_retries=3,
    default_retry_delay=120
)
def send_email_value_bet(
    self,
    user_id: int,
    value_bet_data: Dict[str, Any]
):
    """Send value bet alert via email."""
    try:
        from app.core.config import settings
        from app.services.email_digest import (
            EmailDigestService, 
            EmailConfig, 
            AlertType
        )
        
        config = EmailConfig(
            smtp_server=settings.SMTP_SERVER,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            from_email=settings.FROM_EMAIL,
            from_name="Sports Analytics"
        )
        
        service = EmailDigestService(config)
        
        alert = service.create_value_bet_alert(
            match=value_bet_data["match"],
            market=value_bet_data["market"],
            odds=value_bet_data["odds"],
            probability=value_bet_data["probability"],
            edge=value_bet_data["edge"],
            recommended_stake=value_bet_data.get("stake", 0.02)
        )
        
        # Add alert for user
        service.add_alert(user_id, alert)
        
        logger.info(f"Email value bet alert created for user {user_id}")
        return {"success": True, "user_id": user_id}
        
    except Exception as e:
        logger.error(f"Failed to send email value bet: {e}")
        self.retry(exc=e)


@shared_task(
    name="notifications.send_email_digest",
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def send_email_digest(
    self,
    user_id: int,
    digest_data: Dict[str, Any]
):
    """Send email digest to user."""
    try:
        from app.core.config import settings
        from app.services.email_digest import EmailDigestService, EmailConfig
        
        config = EmailConfig(
            smtp_server=settings.SMTP_SERVER,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            from_email=settings.FROM_EMAIL,
            from_name="Sports Analytics"
        )
        
        service = EmailDigestService(config)
        
        success = service.send_digest(
            user_id=user_id,
            value_bets=digest_data.get("value_bets"),
            predictions=digest_data.get("predictions"),
            performance=digest_data.get("performance"),
            upcoming_matches=digest_data.get("upcoming_matches")
        )
        
        logger.info(f"Email digest sent to user {user_id}: {success}")
        return {"success": success, "user_id": user_id}
        
    except Exception as e:
        logger.error(f"Failed to send email digest: {e}")
        self.retry(exc=e)


@shared_task(name="notifications.send_daily_email_digests")
def send_daily_email_digests():
    """Send daily email digests to all subscribed users."""
    try:
        from app.core.config import settings
        from app.services.email_digest import (
            EmailDigestService, 
            EmailConfig, 
            DigestFrequency
        )
        
        config = EmailConfig(
            smtp_server=settings.SMTP_SERVER,
            smtp_port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            from_email=settings.FROM_EMAIL,
            from_name="Sports Analytics"
        )
        
        service = EmailDigestService(config)
        
        # Get users with daily digest preference
        user_ids = service.get_users_for_digest(DigestFrequency.DAILY)
        
        # Gather data for digest
        # In production, this would query the database
        digest_data = {
            "value_bets": [],
            "predictions": [],
            "performance": {},
            "upcoming_matches": []
        }
        
        async def send_batch():
            return await service.send_digest_batch(user_ids, **digest_data)
        
        results = run_async(send_batch())
        
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Daily digests sent: {success_count}/{len(user_ids)}")
        
        return {
            "success": True, 
            "total": len(user_ids), 
            "sent": success_count
        }
        
    except Exception as e:
        logger.error(f"Failed to send daily digests: {e}")
        return {"success": False, "error": str(e)}


# ============== UNIFIED NOTIFICATION TASKS ==============

@shared_task(
    name="notifications.send_notification",
    bind=True,
    max_retries=3
)
def send_notification(
    self,
    notification_id: int,
    channels: List[str],
    retry_failed: bool = True
):
    """
    Universal task to send a notification through specified channels.
    
    Args:
        notification_id: ID of the notification in database
        channels: List of channels to use (email, telegram, push, websocket)
        retry_failed: Whether to retry failed channels
    """
    try:
        # In production, fetch notification from database
        # notification = await get_notification(notification_id)
        
        results = {}
        
        for channel in channels:
            try:
                if channel == "telegram":
                    # Send via Telegram
                    results["telegram"] = True
                elif channel == "email":
                    # Send via email
                    results["email"] = True
                elif channel == "push":
                    # Send push notification
                    results["push"] = True
                elif channel == "websocket":
                    # Send via WebSocket
                    results["websocket"] = True
            except Exception as e:
                logger.error(f"Channel {channel} failed: {e}")
                results[channel] = False
        
        # Update notification status in database
        all_sent = all(results.values())
        
        logger.info(f"Notification {notification_id} sent: {results}")
        return {"notification_id": notification_id, "results": results, "success": all_sent}
        
    except Exception as e:
        logger.error(f"Failed to send notification {notification_id}: {e}")
        if retry_failed:
            self.retry(exc=e)
        return {"notification_id": notification_id, "success": False, "error": str(e)}


@shared_task(name="notifications.process_value_bet_alerts")
def process_value_bet_alerts(value_bet: Dict[str, Any]):
    """
    Process a new value bet and send alerts to subscribed users.
    
    Determines which users should receive the alert based on their preferences.
    """
    try:
        # In production, query database for users with:
        # - Value bet alerts enabled
        # - min_edge <= value_bet['edge']
        # - Favorite teams/leagues matching (if set)
        
        # Mock user IDs for demo
        telegram_users = []
        email_users = []
        
        # Dispatch to appropriate channels
        if telegram_users:
            send_telegram_value_bet.delay(
                user_ids=telegram_users,
                home_team=value_bet["home_team"],
                away_team=value_bet["away_team"],
                league=value_bet["league"],
                kickoff=value_bet["kickoff"],
                market=value_bet["market"],
                odds=value_bet["odds"],
                probability=value_bet["probability"],
                edge=value_bet["edge"],
                stake=value_bet.get("stake", 0.02),
                confidence=value_bet.get("confidence", 0.7)
            )
        
        if email_users:
            for user_id in email_users:
                send_email_value_bet.delay(
                    user_id=user_id,
                    value_bet_data=value_bet
                )
        
        logger.info(
            f"Value bet alert dispatched: Telegram={len(telegram_users)}, "
            f"Email={len(email_users)}"
        )
        
        return {
            "success": True,
            "telegram_users": len(telegram_users),
            "email_users": len(email_users)
        }
        
    except Exception as e:
        logger.error(f"Failed to process value bet alerts: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="notifications.process_match_start_alerts")
def process_match_start_alerts(match_id: int, match_data: Dict[str, Any]):
    """
    Process match start and send alerts to interested users.
    """
    try:
        # Query users interested in this match (favorite teams/leagues)
        # or all users with match_start alerts enabled
        
        telegram_users = []
        
        if telegram_users:
            send_telegram_match_start.delay(
                user_ids=telegram_users,
                match_data=match_data
            )
        
        logger.info(f"Match start alerts dispatched for match {match_id}")
        return {"success": True, "match_id": match_id}
        
    except Exception as e:
        logger.error(f"Failed to process match start alerts: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="notifications.process_goal_alert")
def process_goal_alert(match_id: int, goal_data: Dict[str, Any]):
    """Process goal scored and send live updates."""
    try:
        telegram_users = []
        
        if telegram_users:
            send_telegram_score_update.delay(
                user_ids=telegram_users,
                score_data=goal_data
            )
        
        logger.info(f"Goal alert dispatched for match {match_id}")
        return {"success": True, "match_id": match_id}
        
    except Exception as e:
        logger.error(f"Failed to process goal alert: {e}")
        return {"success": False, "error": str(e)}


# ============== SCHEDULED TASKS ==============

@shared_task(name="notifications.daily_digest_scheduler")
def daily_digest_scheduler():
    """
    Scheduled task to send daily digests.
    Should be called by Celery Beat at the appropriate time.
    """
    logger.info("Starting daily digest sending...")
    
    # Send email digests
    send_daily_email_digests.delay()
    
    # Gather summary data for Telegram
    summary_data = {
        "date": datetime.now().strftime("%d/%m/%Y"),
        "matches_count": 0,
        "value_bets_count": 0,
        "predictions_count": 0,
        "wins": 0,
        "total": 0,
        "accuracy": 0.0,
        "roi": 0.0,
        "profit": 0.0,
        "top_pick": "N/A"
    }
    
    # Send Telegram summaries
    send_telegram_daily_summary.delay(summary_data)
    
    logger.info("Daily digest tasks dispatched")
    return {"success": True}


@shared_task(name="notifications.cleanup_old_notifications")
def cleanup_old_notifications(days: int = 30):
    """
    Clean up old notification records from database.
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # In production, delete notifications older than cutoff
        # deleted = await db.execute(
        #     delete(Notification).where(Notification.created_at < cutoff_date)
        # )
        
        logger.info(f"Cleaned up notifications older than {cutoff_date}")
        return {"success": True, "cutoff_date": cutoff_date.isoformat()}
        
    except Exception as e:
        logger.error(f"Failed to cleanup notifications: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="notifications.retry_failed_notifications")
def retry_failed_notifications():
    """
    Retry sending failed notifications.
    """
    try:
        # Query failed notifications that haven't exceeded retry limit
        # failed = await db.execute(
        #     select(Notification).where(
        #         Notification.status == NotificationStatus.FAILED,
        #         Notification.retry_count < 3
        #     )
        # )
        
        # For each failed notification, dispatch send task
        retried = 0
        
        logger.info(f"Retried {retried} failed notifications")
        return {"success": True, "retried": retried}
        
    except Exception as e:
        logger.error(f"Failed to retry notifications: {e}")
        return {"success": False, "error": str(e)}
