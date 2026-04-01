"""
Webhook models for external notifications - MongoDB Version
"""

from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from .base import BaseDocument


class WebhookEventType(str, Enum):
    """Types of events that can trigger webhooks."""
    MATCH_START = "match_start"
    MATCH_END = "match_end"
    MATCH_GOAL = "match_goal"
    VALUE_BET_FOUND = "value_bet_found"
    ODDS_CHANGE = "odds_change"
    PREDICTION_READY = "prediction_ready"
    DAILY_SUMMARY = "daily_summary"
    ARBITRAGE_FOUND = "arbitrage_found"
    ALERT_TRIGGERED = "alert_triggered"


class WebhookStatus(str, Enum):
    """Status of webhook deliveries."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class Webhook(BaseDocument):
    """Webhook subscription model."""
    name: str
    url: str
    secret: Optional[str] = None
    is_active: bool = True
    user_id: Optional[str] = None
    
    # Event subscriptions
    events: List[WebhookEventType] = Field(default_factory=list)
    
    # Headers to include in webhook requests
    headers: Dict[str, str] = Field(default_factory=dict)
    
    # Rate limiting
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    
    # Stats
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    last_triggered_at: Optional[datetime] = None
    last_error: Optional[str] = None
    
    class Settings:
        name = "webhooks"


class WebhookDelivery(BaseDocument):
    """Record of webhook delivery attempts."""
    webhook_id: Indexed(str)
    event_type: str
    payload: Dict[str, Any]
    
    status: WebhookStatus = WebhookStatus.PENDING
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    
    attempts: int = 0
    next_retry_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    class Settings:
        name = "webhook_deliveries"
