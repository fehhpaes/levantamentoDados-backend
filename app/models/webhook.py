"""
Webhook models for external notifications.
"""

from sqlalchemy import Column, String, Boolean, Text, DateTime, Integer, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .base import BaseModel


class WebhookEventType(enum.Enum):
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


class WebhookStatus(enum.Enum):
    """Status of webhook deliveries."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class Webhook(BaseModel):
    """Webhook subscription model."""
    __tablename__ = "webhooks"
    
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    secret = Column(String(256), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Event subscriptions (comma-separated list or JSON)
    events = Column(JSON, default=list, nullable=False)
    
    # Headers to include in webhook requests
    headers = Column(JSON, default=dict, nullable=True)
    
    # Rate limiting
    max_retries = Column(Integer, default=3, nullable=False)
    retry_delay = Column(Integer, default=60, nullable=False)  # seconds
    
    # Stats
    total_deliveries = Column(Integer, default=0, nullable=False)
    successful_deliveries = Column(Integer, default=0, nullable=False)
    failed_deliveries = Column(Integer, default=0, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Relationships
    deliveries = relationship("WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan")


class WebhookDelivery(BaseModel):
    """Record of webhook delivery attempts."""
    __tablename__ = "webhook_deliveries"
    
    webhook_id = Column(Integer, ForeignKey("webhooks.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    
    status = Column(String(20), default=WebhookStatus.PENDING.value, nullable=False)
    response_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    attempts = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    webhook = relationship("Webhook", back_populates="deliveries")
