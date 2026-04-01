"""
Notification Models for Alerts System - MongoDB Version
"""

from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from .base import BaseDocument


# Enums

class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    EMAIL = "email"
    TELEGRAM = "telegram"
    PUSH = "push"
    WEBSOCKET = "websocket"
    SMS = "sms"


class NotificationType(str, Enum):
    """Types of notifications."""
    VALUE_BET = "value_bet"
    MATCH_START = "match_start"
    MATCH_END = "match_end"
    SCORE_UPDATE = "score_update"
    ODDS_MOVEMENT = "odds_movement"
    PREDICTION_RESULT = "prediction_result"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_REPORT = "weekly_report"
    SYSTEM_ALERT = "system_alert"
    PROMO = "promo"


class NotificationStatus(str, Enum):
    """Status of notification delivery."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DigestFrequency(str, Enum):
    """Frequency of digest notifications."""
    INSTANT = "instant"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


# MongoDB Documents

class NotificationPreferences(BaseDocument):
    """User preferences for notifications."""
    user_id: Indexed(str, unique=True)
    
    # Channel settings
    email_enabled: bool = True
    telegram_enabled: bool = False
    push_enabled: bool = True
    websocket_enabled: bool = True
    
    # Telegram settings
    telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    telegram_verified: bool = False
    
    # Digest settings
    digest_frequency: DigestFrequency = DigestFrequency.DAILY
    digest_time: str = "09:00"  # HH:MM format
    
    # Alert types
    enabled_alert_types: List[NotificationType] = Field(
        default_factory=lambda: [
            NotificationType.VALUE_BET,
            NotificationType.MATCH_START,
            NotificationType.DAILY_SUMMARY
        ]
    )
    
    # Thresholds
    min_edge_percentage: float = 5.0
    min_confidence: float = 0.6
    min_odds_change: float = 5.0
    
    # Favorite filters
    favorite_teams: List[str] = Field(default_factory=list)
    favorite_leagues: List[str] = Field(default_factory=list)
    favorite_sports: List[str] = Field(default_factory=list)
    
    # Quiet hours
    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    
    # Timezone
    timezone: str = "America/Sao_Paulo"
    language: str = "pt"
    
    class Settings:
        name = "notification_preferences"


class Notification(BaseDocument):
    """Individual notification record."""
    user_id: Indexed(str)
    
    # Notification details
    notification_type: NotificationType
    channel: NotificationChannel
    priority: NotificationPriority = NotificationPriority.MEDIUM
    status: NotificationStatus = NotificationStatus.PENDING
    
    # Content
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    
    # Related entities
    match_id: Optional[str] = None
    prediction_id: Optional[str] = None
    
    # Delivery tracking
    scheduled_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    
    # Error handling
    retry_count: int = 0
    last_error: Optional[str] = None
    
    class Settings:
        name = "notifications"


class NotificationTemplate(BaseDocument):
    """Templates for notification messages."""
    name: Indexed(str, unique=True)
    notification_type: NotificationType
    language: str = "pt"
    
    # Template content
    title_template: str
    message_template: str
    
    # Channel-specific templates
    email_html_template: Optional[str] = None
    telegram_template: Optional[str] = None
    push_template: Optional[str] = None
    
    # Variables
    variables: Optional[Dict[str, Any]] = None
    
    # Status
    is_active: bool = True
    
    class Settings:
        name = "notification_templates"


class TelegramVerification(BaseDocument):
    """Telegram verification tokens."""
    user_id: Indexed(str)
    
    verification_code: Indexed(str, unique=True)
    expires_at: datetime
    
    verified_at: Optional[datetime] = None
    telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    
    class Settings:
        name = "telegram_verifications"


# Alias for backwards compatibility
UserNotificationPreferences = NotificationPreferences
