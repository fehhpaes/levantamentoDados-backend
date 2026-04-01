"""
Celery configuration and app initialization.
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "sports_data_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.scraping",
        "app.workers.tasks.predictions",
        "app.workers.tasks.odds",
        "app.workers.tasks.maintenance",
        "app.workers.tasks.notifications",
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,  # 50 minutes soft limit
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    
    # Result settings
    result_expires=86400,  # 24 hours
    
    # Task routing
    task_routes={
        "app.workers.tasks.scraping.*": {"queue": "scraping"},
        "app.workers.tasks.predictions.*": {"queue": "predictions"},
        "app.workers.tasks.odds.*": {"queue": "odds"},
        "app.workers.tasks.maintenance.*": {"queue": "maintenance"},
        "app.workers.tasks.notifications.*": {"queue": "notifications"},
        "notifications.*": {"queue": "notifications"},
    },
    
    # Rate limiting
    task_default_rate_limit="10/m",
    
    # Beat schedule (periodic tasks)
    beat_schedule={
        # Scraping tasks
        "scrape-football-matches-hourly": {
            "task": "app.workers.tasks.scraping.scrape_football_matches",
            "schedule": crontab(minute=0),  # Every hour
            "options": {"queue": "scraping"},
        },
        "scrape-live-matches": {
            "task": "app.workers.tasks.scraping.scrape_live_matches",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "options": {"queue": "scraping"},
        },
        
        # Odds tasks
        "update-odds-frequently": {
            "task": "app.workers.tasks.odds.update_all_odds",
            "schedule": crontab(minute="*/10"),  # Every 10 minutes
            "options": {"queue": "odds"},
        },
        "detect-value-bets": {
            "task": "app.workers.tasks.odds.detect_value_bets",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
            "options": {"queue": "odds"},
        },
        
        # Prediction tasks
        "generate-daily-predictions": {
            "task": "app.workers.tasks.predictions.generate_daily_predictions",
            "schedule": crontab(hour=6, minute=0),  # 6 AM daily
            "options": {"queue": "predictions"},
        },
        "update-prediction-results": {
            "task": "app.workers.tasks.predictions.update_prediction_results",
            "schedule": crontab(minute="*/30"),  # Every 30 minutes
            "options": {"queue": "predictions"},
        },
        
        # Notification tasks
        "daily-digest-morning": {
            "task": "notifications.daily_digest_scheduler",
            "schedule": crontab(hour=9, minute=0),  # 9 AM daily
            "options": {"queue": "notifications"},
        },
        "retry-failed-notifications": {
            "task": "notifications.retry_failed_notifications",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
            "options": {"queue": "notifications"},
        },
        "cleanup-old-notifications": {
            "task": "notifications.cleanup_old_notifications",
            "schedule": crontab(hour=2, minute=0),  # 2 AM daily
            "args": (30,),  # Keep 30 days
            "options": {"queue": "notifications"},
        },
        
        # Maintenance tasks
        "cleanup-old-data": {
            "task": "app.workers.tasks.maintenance.cleanup_old_data",
            "schedule": crontab(hour=3, minute=0),  # 3 AM daily
            "options": {"queue": "maintenance"},
        },
        "retry-failed-webhooks": {
            "task": "app.workers.tasks.maintenance.retry_failed_webhooks",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "options": {"queue": "maintenance"},
        },
        "generate-daily-stats": {
            "task": "app.workers.tasks.maintenance.generate_daily_stats",
            "schedule": crontab(hour=0, minute=5),  # 00:05 daily
            "options": {"queue": "maintenance"},
        },
    },
)


# Task priority
celery_app.conf.task_queue_max_priority = 10
celery_app.conf.task_default_priority = 5
