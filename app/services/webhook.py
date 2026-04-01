"""
Webhook Service for managing and delivering webhooks.
"""

import hashlib
import hmac
import json
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import httpx
import logging

from app.models.webhook import Webhook, WebhookDelivery, WebhookStatus
from app.schemas.webhook import (
    WebhookCreate, 
    WebhookUpdate, 
    WebhookEventType,
    WebhookEventPayload
)

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for webhook management and delivery."""
    
    def __init__(self):
        """Initialize the webhook service."""
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
    
    # CRUD Operations
    
    async def create_webhook(
        self, 
        webhook_data: WebhookCreate,
        user_id: Optional[str] = None
    ) -> Webhook:
        """Create a new webhook subscription."""
        webhook = Webhook(
            name=webhook_data.name,
            url=str(webhook_data.url),
            secret=webhook_data.secret,
            events=[e.value for e in webhook_data.events],
            headers=webhook_data.headers or {},
            max_retries=webhook_data.max_retries,
            retry_delay=webhook_data.retry_delay,
            user_id=user_id,
            is_active=True
        )
        
        await webhook.save()
        
        logger.info(f"Created webhook {webhook.id}: {webhook.name}")
        return webhook
    
    async def get_webhook(self, webhook_id: str) -> Optional[Webhook]:
        """Get a webhook by ID."""
        return await Webhook.get(webhook_id)
    
    async def get_webhooks(
        self, 
        user_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Webhook]:
        """Get all webhooks with optional filtering."""
        query = Webhook.find()
        
        if user_id is not None:
            query = query.find(Webhook.user_id == user_id)
        
        if is_active is not None:
            query = query.find(Webhook.is_active == is_active)
        
        return await query.skip(skip).limit(limit).to_list()
    
    async def update_webhook(
        self, 
        webhook_id: str, 
        webhook_data: WebhookUpdate
    ) -> Optional[Webhook]:
        """Update a webhook."""
        webhook = await self.get_webhook(webhook_id)
        if not webhook:
            return None
        
        update_data = webhook_data.model_dump(exclude_unset=True)
        
        if "url" in update_data:
            update_data["url"] = str(update_data["url"])
        
        if "events" in update_data:
            update_data["events"] = [e.value for e in update_data["events"]]
        
        for key, value in update_data.items():
            setattr(webhook, key, value)
        
        await webhook.save()
        
        logger.info(f"Updated webhook {webhook_id}")
        return webhook
    
    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        webhook = await self.get_webhook(webhook_id)
        if not webhook:
            return False
        
        await webhook.delete()
        
        logger.info(f"Deleted webhook {webhook_id}")
        return True
    
    # Delivery Operations
    
    async def trigger_event(
        self,
        event_type: WebhookEventType,
        data: Dict[str, Any]
    ) -> List[WebhookDelivery]:
        """
        Trigger an event and deliver to all subscribed webhooks.
        
        Args:
            event_type: Type of event
            data: Event data payload
            
        Returns:
            List of delivery records
        """
        # Get all active webhooks
        webhooks = await Webhook.find(Webhook.is_active == True).to_list()
        
        # Filter webhooks that are subscribed to this event
        subscribed_webhooks = [
            w for w in webhooks 
            if event_type.value in w.events
        ]
        
        if not subscribed_webhooks:
            logger.debug(f"No webhooks subscribed to {event_type.value}")
            return []
        
        # Create delivery tasks
        deliveries = []
        tasks = []
        
        for webhook in subscribed_webhooks:
            delivery = await self._create_delivery(webhook, event_type, data)
            deliveries.append(delivery)
            tasks.append(self._deliver_webhook(delivery, webhook))
        
        # Execute all deliveries concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return deliveries
    
    async def _create_delivery(
        self,
        webhook: Webhook,
        event_type: WebhookEventType,
        data: Dict[str, Any]
    ) -> WebhookDelivery:
        """Create a delivery record."""
        payload = WebhookEventPayload(
            event_type=event_type.value,
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            data=data
        )
        
        delivery = WebhookDelivery(
            webhook_id=str(webhook.id),
            event_type=event_type.value,
            payload=payload.model_dump(mode="json"),
            status=WebhookStatus.PENDING.value,
            attempts=0
        )
        
        await delivery.save()
        
        return delivery
    
    async def _deliver_webhook(
        self,
        delivery: WebhookDelivery,
        webhook: Webhook
    ) -> bool:
        """
        Deliver a webhook with retry logic.
        
        Returns:
            True if delivery was successful
        """
        payload_json = json.dumps(delivery.payload, default=str)
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SportsDataAnalytics-Webhook/1.0",
            "X-Webhook-Event": delivery.event_type,
            "X-Webhook-Delivery-ID": str(delivery.id),
            **(webhook.headers or {})
        }
        
        # Add signature if secret is configured
        if webhook.secret:
            signature = self._sign_payload(payload_json, webhook.secret)
            headers["X-Webhook-Signature"] = signature
            headers["X-Webhook-Signature-256"] = f"sha256={signature}"
        
        # Attempt delivery
        delivery.attempts += 1
        
        try:
            response = await self.http_client.post(
                webhook.url,
                content=payload_json,
                headers=headers
            )
            
            delivery.response_code = response.status_code
            delivery.response_body = response.text[:1000] if response.text else None
            
            if 200 <= response.status_code < 300:
                # Success
                delivery.status = WebhookStatus.DELIVERED.value
                delivery.delivered_at = datetime.utcnow()
                
                # Update webhook stats
                webhook.total_deliveries += 1
                webhook.successful_deliveries += 1
                webhook.last_triggered_at = datetime.utcnow()
                webhook.last_error = None
                
                logger.info(f"Webhook {webhook.id} delivered successfully to {webhook.url}")
                
            else:
                # HTTP error
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response
                )
                
        except Exception as e:
            error_msg = str(e)[:500]
            delivery.error_message = error_msg
            
            # Check if we should retry
            if delivery.attempts < webhook.max_retries:
                delivery.status = WebhookStatus.RETRYING.value
                delivery.next_retry_at = datetime.utcnow() + timedelta(
                    seconds=webhook.retry_delay * delivery.attempts
                )
                logger.warning(
                    f"Webhook {webhook.id} failed, will retry. "
                    f"Attempt {delivery.attempts}/{webhook.max_retries}"
                )
            else:
                delivery.status = WebhookStatus.FAILED.value
                webhook.failed_deliveries += 1
                webhook.last_error = error_msg
                logger.error(f"Webhook {webhook.id} failed permanently: {error_msg}")
            
            webhook.total_deliveries += 1
            webhook.last_triggered_at = datetime.utcnow()
        
        await delivery.save()
        await webhook.save()
        return delivery.status == WebhookStatus.DELIVERED.value
    
    def _sign_payload(self, payload: str, secret: str) -> str:
        """Create HMAC signature for payload."""
        return hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
    
    async def retry_failed_deliveries(self) -> int:
        """
        Retry all failed deliveries that are due.
        
        Returns:
            Number of deliveries retried
        """
        now = datetime.utcnow()
        
        # Get deliveries due for retry
        deliveries = await WebhookDelivery.find(
            WebhookDelivery.status == WebhookStatus.RETRYING.value,
            WebhookDelivery.next_retry_at <= now
        ).to_list()
        
        if not deliveries:
            return 0
        
        logger.info(f"Retrying {len(deliveries)} webhook deliveries")
        
        tasks = []
        for delivery in deliveries:
            # Fetch the webhook
            webhook = await Webhook.get(delivery.webhook_id)
            if webhook and webhook.is_active:
                tasks.append(self._deliver_webhook(delivery, webhook))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return len(deliveries)
    
    async def test_webhook(
        self,
        webhook_id: str,
        event_type: WebhookEventType = WebhookEventType.PREDICTION_READY,
        custom_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a test webhook.
        
        Returns:
            Test result with status, response time, etc.
        """
        webhook = await self.get_webhook(webhook_id)
        if not webhook:
            return {
                "success": False,
                "error": "Webhook not found"
            }
        
        # Build test payload
        test_data = custom_payload or {
            "test": True,
            "message": "This is a test webhook delivery",
            "webhook_id": webhook_id,
            "webhook_name": webhook.name
        }
        
        payload = WebhookEventPayload(
            event_type=event_type.value,
            event_id=f"test_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            data=test_data
        )
        
        payload_json = json.dumps(payload.model_dump(mode="json"), default=str)
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SportsDataAnalytics-Webhook/1.0",
            "X-Webhook-Event": event_type.value,
            "X-Webhook-Test": "true",
            **(webhook.headers or {})
        }
        
        if webhook.secret:
            signature = self._sign_payload(payload_json, webhook.secret)
            headers["X-Webhook-Signature-256"] = f"sha256={signature}"
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            response = await self.http_client.post(
                webhook.url,
                content=payload_json,
                headers=headers
            )
            
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return {
                "success": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "response_time_ms": round(elapsed_ms, 2),
                "error": None if response.status_code < 400 else response.text[:200]
            }
            
        except Exception as e:
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            return {
                "success": False,
                "status_code": None,
                "response_time_ms": round(elapsed_ms, 2),
                "error": str(e)[:200]
            }
    
    async def get_delivery_history(
        self,
        webhook_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[WebhookDelivery]:
        """Get webhook delivery history."""
        query = WebhookDelivery.find().sort(-WebhookDelivery.created_at)
        
        if webhook_id:
            query = query.find(WebhookDelivery.webhook_id == webhook_id)
        
        if status:
            query = query.find(WebhookDelivery.status == status)
        
        return await query.skip(skip).limit(limit).to_list()
    
    async def get_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get webhook statistics."""
        # Get webhooks
        webhooks = await self.get_webhooks(user_id=user_id)
        
        # Calculate stats
        total_deliveries = sum(w.total_deliveries for w in webhooks)
        successful_deliveries = sum(w.successful_deliveries for w in webhooks)
        failed_deliveries = sum(w.failed_deliveries for w in webhooks)
        
        success_rate = (
            successful_deliveries / total_deliveries * 100
            if total_deliveries > 0 else 0
        )
        
        # Get recent failures
        recent_failures = await self.get_delivery_history(
            status=WebhookStatus.FAILED.value,
            limit=10
        )
        
        # Get all deliveries and count by event type
        all_deliveries = await WebhookDelivery.find().to_list()
        deliveries_by_event = {}
        for delivery in all_deliveries:
            event = delivery.event_type
            deliveries_by_event[event] = deliveries_by_event.get(event, 0) + 1
        
        return {
            "total_webhooks": len(webhooks),
            "active_webhooks": len([w for w in webhooks if w.is_active]),
            "total_deliveries": total_deliveries,
            "successful_deliveries": successful_deliveries,
            "failed_deliveries": failed_deliveries,
            "success_rate": round(success_rate, 2),
            "deliveries_by_event": deliveries_by_event,
            "recent_failures": recent_failures
        }


# Singleton instance for use in background tasks
_webhook_service: Optional[WebhookService] = None


async def get_webhook_service() -> WebhookService:
    """Get webhook service instance."""
    return WebhookService()


async def trigger_webhook_event(
    event_type: WebhookEventType,
    data: Dict[str, Any]
) -> None:
    """
    Convenience function to trigger webhook events from anywhere in the app.
    
    Usage:
        await trigger_webhook_event(
            WebhookEventType.VALUE_BET_FOUND,
            {"match_id": 123, "odds": 2.5, "edge": 0.08}
        )
    """
    service = WebhookService()
    try:
        await service.trigger_event(event_type, data)
    finally:
        await service.close()
