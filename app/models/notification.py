"""
Notification Models for Alerts System

Handles user notification preferences and notification history.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float,
    Enum as SQLEnum, ForeignKey, JSON, Text, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from .base import BaseModel as DBBaseModel, Base


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


# SQLAlchemy Models

class UserNotificationPreferences(Base):
    """User preferences for notifications."""
    __tablename__ = "user_notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    
    # Channel settings
    email_enabled = Column(Boolean, default=True)
    telegram_enabled = Column(Boolean, default=False)
    push_enabled = Column(Boolean, default=True)
    websocket_enabled = Column(Boolean, default=True)
    
    # Telegram settings
    telegram_chat_id = Column(String(50))
    telegram_username = Column(String(100))
    telegram_verified = Column(Boolean, default=False)
    
    # Digest settings
    digest_frequency = Column(SQLEnum(DigestFrequency), default=DigestFrequency.DAILY)
    digest_time = Column(String(5), default="09:00")  # HH:MM format
    
    # Alert types (JSON array of NotificationType values)
    enabled_alert_types = Column(JSON, default=list)
    
    # Thresholds
    min_edge_percentage = Column(Float, default=5.0)  # Minimum edge for value bet alerts
    min_confidence = Column(Float, default=0.6)  # Minimum confidence for predictions
    min_odds_change = Column(Float, default=5.0)  # Minimum % change for odds movement
    
    # Favorite filters
    favorite_teams = Column(JSON, default=list)  # List of team IDs
    favorite_leagues = Column(JSON, default=list)  # List of league IDs
    favorite_sports = Column(JSON, default=list)  # List of sport IDs
    
    # Quiet hours
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String(5))  # HH:MM
    quiet_hours_end = Column(String(5))  # HH:MM
    
    # Timezone
    timezone = Column(String(50), default="America/Sao_Paulo")
    language = Column(String(10), default="pt")
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationship
    # user = relationship("User", back_populates="notification_preferences")
    
    __table_args__ = (
        Index('idx_user_notification_prefs_user_id', 'user_id'),
    )


class Notification(Base):
    """Individual notification record."""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Notification details
    notification_type = Column(SQLEnum(NotificationType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.MEDIUM)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    
    # Content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSON)  # Additional structured data
    
    # Related entities
    match_id = Column(Integer, ForeignKey('matches.id'))
    prediction_id = Column(Integer)
    
    # Delivery tracking
    scheduled_at = Column(DateTime, default=func.now())
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)
    
    # Error handling
    retry_count = Column(Integer, default=0)
    last_error = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    # user = relationship("User", back_populates="notifications")
    # match = relationship("Match")
    
    __table_args__ = (
        Index('idx_notifications_user_status', 'user_id', 'status'),
        Index('idx_notifications_type_created', 'notification_type', 'created_at'),
        Index('idx_notifications_scheduled', 'scheduled_at', 'status'),
    )


class NotificationTemplate(Base):
    """Templates for notification messages."""
    __tablename__ = "notification_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    
    name = Column(String(100), unique=True, nullable=False)
    notification_type = Column(SQLEnum(NotificationType), nullable=False)
    language = Column(String(10), default="pt")
    
    # Template content
    title_template = Column(String(255), nullable=False)
    message_template = Column(Text, nullable=False)
    
    # Channel-specific templates
    email_html_template = Column(Text)
    telegram_template = Column(Text)
    push_template = Column(Text)
    
    # Variables (JSON schema of expected variables)
    variables = Column(JSON)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TelegramVerification(Base):
    """Telegram verification tokens."""
    __tablename__ = "telegram_verifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    verification_code = Column(String(20), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    
    verified_at = Column(DateTime)
    telegram_chat_id = Column(String(50))
    telegram_username = Column(String(100))
    
    created_at = Column(DateTime, server_default=func.now())


# Pydantic Schemas

class NotificationPreferencesBase(BaseModel):
    """Base schema for notification preferences."""
    email_enabled: bool = True
    telegram_enabled: bool = False
    push_enabled: bool = True
    websocket_enabled: bool = True
    
    digest_frequency: DigestFrequency = DigestFrequency.DAILY
    digest_time: str = "09:00"
    
    enabled_alert_types: List[NotificationType] = Field(
        default_factory=lambda: [
            NotificationType.VALUE_BET,
            NotificationType.MATCH_START,
            NotificationType.DAILY_SUMMARY
        ]
    )
    
    min_edge_percentage: float = 5.0
    min_confidence: float = 0.6
    min_odds_change: float = 5.0
    
    favorite_teams: List[int] = Field(default_factory=list)
    favorite_leagues: List[int] = Field(default_factory=list)
    favorite_sports: List[int] = Field(default_factory=list)
    
    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    
    timezone: str = "America/Sao_Paulo"
    language: str = "pt"


class NotificationPreferencesCreate(NotificationPreferencesBase):
    """Schema for creating notification preferences."""
    pass


class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences."""
    email_enabled: Optional[bool] = None
    telegram_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    websocket_enabled: Optional[bool] = None
    
    digest_frequency: Optional[DigestFrequency] = None
    digest_time: Optional[str] = None
    
    enabled_alert_types: Optional[List[NotificationType]] = None
    
    min_edge_percentage: Optional[float] = None
    min_confidence: Optional[float] = None
    min_odds_change: Optional[float] = None
    
    favorite_teams: Optional[List[int]] = None
    favorite_leagues: Optional[List[int]] = None
    favorite_sports: Optional[List[int]] = None
    
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    
    timezone: Optional[str] = None
    language: Optional[str] = None


class NotificationPreferencesResponse(NotificationPreferencesBase):
    """Response schema for notification preferences."""
    id: int
    user_id: int
    telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    telegram_verified: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class NotificationBase(BaseModel):
    """Base schema for notifications."""
    notification_type: NotificationType
    channel: NotificationChannel
    priority: NotificationPriority = NotificationPriority.MEDIUM
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase):
    """Schema for creating a notification."""
    user_id: int
    match_id: Optional[int] = None
    prediction_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None


class NotificationResponse(NotificationBase):
    """Response schema for notifications."""
    id: int
    user_id: int
    status: NotificationStatus
    match_id: Optional[int] = None
    prediction_id: Optional[int] = None
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Response for list of notifications."""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class TelegramLinkRequest(BaseModel):
    """Request to link Telegram account."""
    pass  # No input needed, returns verification code


class TelegramLinkResponse(BaseModel):
    """Response with Telegram verification code."""
    verification_code: str
    bot_username: str
    expires_at: datetime
    instructions: str


class TelegramVerifyRequest(BaseModel):
    """Request from Telegram bot to verify user."""
    verification_code: str
    telegram_chat_id: str
    telegram_username: Optional[str] = None


class NotificationStatsResponse(BaseModel):
    """Statistics about user notifications."""
    total_notifications: int
    unread_count: int
    notifications_today: int
    notifications_this_week: int
    by_type: Dict[str, int]
    by_channel: Dict[str, int]
    by_status: Dict[str, int]


class BulkNotificationCreate(BaseModel):
    """Schema for creating notifications for multiple users."""
    user_ids: List[int]
    notification_type: NotificationType
    channels: List[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.MEDIUM
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None


class ValueBetNotificationData(BaseModel):
    """Structured data for value bet notifications."""
    match_id: int
    home_team: str
    away_team: str
    league: str
    kickoff: datetime
    market: str
    selection: str
    odds: float
    probability: float
    edge: float
    recommended_stake: float
    confidence: float
    bookmaker: str


class OddsMovementNotificationData(BaseModel):
    """Structured data for odds movement notifications."""
    match_id: int
    home_team: str
    away_team: str
    market: str
    bookmaker: str
    old_odds: float
    new_odds: float
    change_percentage: float
    direction: str  # "up" or "down"
    timestamp: datetime


class MatchStartNotificationData(BaseModel):
    """Structured data for match start notifications."""
    match_id: int
    home_team: str
    away_team: str
    league: str
    kickoff: datetime
    prediction: Optional[Dict[str, float]] = None  # home_win, draw, away_win
    best_value_bet: Optional[Dict[str, Any]] = None


class ScoreUpdateNotificationData(BaseModel):
    """Structured data for score update notifications."""
    match_id: int
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    minute: int
    event_type: str  # "goal", "red_card", "penalty", etc.
    player: Optional[str] = None
    team: Optional[str] = None
