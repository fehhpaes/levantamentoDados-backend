"""
Webhook API endpoints for managing webhook subscriptions.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.auth.dependencies import get_current_user, get_current_user_optional
from app.auth.models import User
from app.services.webhook import WebhookService, get_webhook_service
from app.schemas.webhook import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookDeliveryResponse,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookStatsResponse,
    WebhookEventType,
)

router = APIRouter()


# Webhooks CRUD

@router.post(
    "/",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new webhook",
    description="Create a new webhook subscription to receive notifications for specific events."
)
async def create_webhook(
    webhook_data: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Create a new webhook subscription.
    
    - **name**: A descriptive name for the webhook
    - **url**: The URL to send webhook notifications to (must be HTTPS in production)
    - **secret**: Optional secret for HMAC signature verification
    - **events**: List of event types to subscribe to
    - **headers**: Custom headers to include in webhook requests
    - **max_retries**: Maximum retry attempts for failed deliveries (default: 3)
    - **retry_delay**: Delay between retries in seconds (default: 60)
    """
    service = WebhookService(db)
    try:
        user_id = current_user.id if current_user else None
        webhook = await service.create_webhook(webhook_data, user_id=user_id)
        return webhook
    finally:
        await service.close()


@router.get(
    "/",
    response_model=List[WebhookResponse],
    summary="List webhooks",
    description="Get all webhooks, optionally filtered by active status."
)
async def list_webhooks(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """List all webhooks with optional filtering."""
    service = WebhookService(db)
    try:
        user_id = current_user.id if current_user else None
        webhooks = await service.get_webhooks(
            user_id=user_id,
            is_active=is_active,
            skip=skip,
            limit=limit
        )
        return webhooks
    finally:
        await service.close()


@router.get(
    "/stats",
    response_model=WebhookStatsResponse,
    summary="Get webhook statistics",
    description="Get aggregated statistics about webhook deliveries."
)
async def get_webhook_stats(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get webhook delivery statistics."""
    service = WebhookService(db)
    try:
        user_id = current_user.id if current_user else None
        stats = await service.get_stats(user_id=user_id)
        
        # Convert recent failures to response model
        stats["recent_failures"] = [
            WebhookDeliveryResponse.model_validate(d) 
            for d in stats["recent_failures"]
        ]
        
        return stats
    finally:
        await service.close()


@router.get(
    "/events",
    response_model=List[dict],
    summary="List available event types",
    description="Get list of all event types that can be subscribed to."
)
async def list_event_types():
    """List all available webhook event types."""
    return [
        {
            "type": event.value,
            "name": event.name.replace("_", " ").title(),
            "description": _get_event_description(event)
        }
        for event in WebhookEventType
    ]


def _get_event_description(event: WebhookEventType) -> str:
    """Get human-readable description for event type."""
    descriptions = {
        WebhookEventType.MATCH_START: "Triggered when a match begins",
        WebhookEventType.MATCH_END: "Triggered when a match finishes",
        WebhookEventType.MATCH_GOAL: "Triggered when a goal is scored",
        WebhookEventType.VALUE_BET_FOUND: "Triggered when a value betting opportunity is identified",
        WebhookEventType.ODDS_CHANGE: "Triggered when odds change significantly",
        WebhookEventType.PREDICTION_READY: "Triggered when a new prediction is available",
        WebhookEventType.DAILY_SUMMARY: "Daily summary of all events and results",
        WebhookEventType.ARBITRAGE_FOUND: "Triggered when an arbitrage opportunity is found",
        WebhookEventType.ALERT_TRIGGERED: "Triggered when a custom alert condition is met",
    }
    return descriptions.get(event, "")


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook details",
    description="Get detailed information about a specific webhook."
)
async def get_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get webhook by ID."""
    service = WebhookService(db)
    try:
        webhook = await service.get_webhook(webhook_id)
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        # Check ownership if user is authenticated
        if current_user and webhook.user_id and webhook.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this webhook"
            )
        
        return webhook
    finally:
        await service.close()


@router.patch(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update webhook",
    description="Update an existing webhook subscription."
)
async def update_webhook(
    webhook_id: int,
    webhook_data: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Update webhook settings."""
    service = WebhookService(db)
    try:
        # Check if webhook exists and user has access
        existing = await service.get_webhook(webhook_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        if current_user and existing.user_id and existing.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this webhook"
            )
        
        webhook = await service.update_webhook(webhook_id, webhook_data)
        return webhook
    finally:
        await service.close()


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete webhook",
    description="Delete a webhook subscription."
)
async def delete_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Delete a webhook."""
    service = WebhookService(db)
    try:
        # Check if webhook exists and user has access
        existing = await service.get_webhook(webhook_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        if current_user and existing.user_id and existing.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this webhook"
            )
        
        await service.delete_webhook(webhook_id)
    finally:
        await service.close()


# Testing and Deliveries

@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    summary="Test webhook",
    description="Send a test request to verify webhook configuration."
)
async def test_webhook(
    webhook_id: int,
    test_data: Optional[WebhookTestRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Send a test webhook request.
    
    This endpoint sends a test payload to the webhook URL to verify
    that it's correctly configured and responding.
    """
    service = WebhookService(db)
    try:
        # Check if webhook exists
        existing = await service.get_webhook(webhook_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        event_type = test_data.event_type if test_data else WebhookEventType.PREDICTION_READY
        custom_payload = test_data.payload if test_data else None
        
        result = await service.test_webhook(
            webhook_id,
            event_type=event_type,
            custom_payload=custom_payload
        )
        
        return WebhookTestResponse(**result)
    finally:
        await service.close()


@router.get(
    "/{webhook_id}/deliveries",
    response_model=List[WebhookDeliveryResponse],
    summary="Get delivery history",
    description="Get the delivery history for a specific webhook."
)
async def get_webhook_deliveries(
    webhook_id: int,
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get delivery history for a webhook."""
    service = WebhookService(db)
    try:
        # Check if webhook exists
        existing = await service.get_webhook(webhook_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        deliveries = await service.get_delivery_history(
            webhook_id=webhook_id,
            status=status,
            skip=skip,
            limit=limit
        )
        
        return deliveries
    finally:
        await service.close()


@router.post(
    "/deliveries/retry",
    summary="Retry failed deliveries",
    description="Manually trigger retry of failed webhook deliveries."
)
async def retry_failed_deliveries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retry all failed webhook deliveries that are due for retry.
    
    Requires authentication.
    """
    service = WebhookService(db)
    try:
        count = await service.retry_failed_deliveries()
        return {
            "message": f"Retried {count} deliveries",
            "retried_count": count
        }
    finally:
        await service.close()
