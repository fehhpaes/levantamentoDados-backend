"""
Webhook schemas for API requests/responses.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


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


class WebhookCreate(BaseModel):
    """Schema for creating a webhook."""
    name: str = Field(..., min_length=1, max_length=100, description="Webhook name")
    url: HttpUrl = Field(..., description="URL to send webhook to")
    secret: Optional[str] = Field(None, max_length=256, description="Secret for signature verification")
    events: List[WebhookEventType] = Field(..., min_length=1, description="Events to subscribe to")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Custom headers")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts")
    retry_delay: int = Field(default=60, ge=10, le=3600, description="Delay between retries in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Value Bet Notifier",
                "url": "https://myserver.com/webhooks/sports",
                "secret": "my-secret-key",
                "events": ["value_bet_found", "prediction_ready"],
                "headers": {"X-Custom-Header": "value"},
                "max_retries": 3,
                "retry_delay": 60
            }
        }


class WebhookUpdate(BaseModel):
    """Schema for updating a webhook."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[HttpUrl] = None
    secret: Optional[str] = Field(None, max_length=256)
    events: Optional[List[WebhookEventType]] = None
    headers: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    retry_delay: Optional[int] = Field(None, ge=10, le=3600)


class WebhookResponse(BaseModel):
    """Schema for webhook response."""
    id: int
    name: str
    url: str
    is_active: bool
    events: List[str]
    headers: Optional[Dict[str, str]]
    max_retries: int
    retry_delay: int
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    last_triggered_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WebhookDeliveryResponse(BaseModel):
    """Schema for webhook delivery record."""
    id: int
    webhook_id: int
    event_type: str
    payload: Dict[str, Any]
    status: str
    response_code: Optional[int]
    error_message: Optional[str]
    attempts: int
    delivered_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class WebhookTestRequest(BaseModel):
    """Schema for testing a webhook."""
    event_type: WebhookEventType = Field(default=WebhookEventType.PREDICTION_READY)
    payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom test payload"
    )


class WebhookTestResponse(BaseModel):
    """Schema for webhook test result."""
    success: bool
    status_code: Optional[int]
    response_time_ms: float
    error: Optional[str]


class WebhookStatsResponse(BaseModel):
    """Schema for webhook statistics."""
    total_webhooks: int
    active_webhooks: int
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    success_rate: float
    avg_response_time_ms: Optional[float]
    deliveries_by_event: Dict[str, int]
    recent_failures: List[WebhookDeliveryResponse]


class WebhookEventPayload(BaseModel):
    """Base payload structure for webhook events."""
    event_type: str
    event_id: str
    timestamp: datetime
    data: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "value_bet_found",
                "event_id": "evt_123456",
                "timestamp": "2024-01-15T10:30:00Z",
                "data": {
                    "match_id": 123,
                    "match_name": "Team A vs Team B",
                    "market": "home_win",
                    "odds": 2.50,
                    "predicted_probability": 0.48,
                    "edge": 0.08
                }
            }
        }
