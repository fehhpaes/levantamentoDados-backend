"""
Tests for Webhook Service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.services.webhook import WebhookService, trigger_webhook_event
from app.models.webhook import Webhook, WebhookDelivery, WebhookStatus
from app.schemas.webhook import WebhookCreate, WebhookUpdate, WebhookEventType

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def webhook_service(test_db: AsyncSession):
    """Create a webhook service instance."""
    service = WebhookService(test_db)
    yield service
    await service.close()


@pytest.fixture
async def test_webhook(test_db: AsyncSession):
    """Create a test webhook."""
    webhook = Webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
        secret="test-secret",
        events=["value_bet_found", "prediction_ready"],
        headers={"X-Custom": "header"},
        max_retries=3,
        retry_delay=60,
        is_active=True
    )
    test_db.add(webhook)
    await test_db.commit()
    await test_db.refresh(webhook)
    return webhook


class TestWebhookServiceCRUD:
    """Tests for webhook service CRUD operations."""

    async def test_create_webhook(
        self, webhook_service: WebhookService, sample_webhook_data
    ):
        """Test creating a webhook."""
        webhook_data = WebhookCreate(**sample_webhook_data)
        
        webhook = await webhook_service.create_webhook(webhook_data)
        
        assert webhook.id is not None
        assert webhook.name == sample_webhook_data["name"]
        assert webhook.url == sample_webhook_data["url"]
        assert webhook.is_active is True
        assert "value_bet_found" in webhook.events

    async def test_create_webhook_with_user_id(
        self, webhook_service: WebhookService, sample_webhook_data
    ):
        """Test creating a webhook with user association."""
        webhook_data = WebhookCreate(**sample_webhook_data)
        
        webhook = await webhook_service.create_webhook(webhook_data, user_id=123)
        
        assert webhook.user_id == 123

    async def test_get_webhook(
        self, webhook_service: WebhookService, test_webhook
    ):
        """Test getting a webhook by ID."""
        webhook = await webhook_service.get_webhook(test_webhook.id)
        
        assert webhook is not None
        assert webhook.id == test_webhook.id
        assert webhook.name == test_webhook.name

    async def test_get_webhook_not_found(
        self, webhook_service: WebhookService
    ):
        """Test getting a non-existent webhook."""
        webhook = await webhook_service.get_webhook(99999)
        
        assert webhook is None

    async def test_get_webhooks(
        self, webhook_service: WebhookService, test_webhook
    ):
        """Test getting all webhooks."""
        webhooks = await webhook_service.get_webhooks()
        
        assert len(webhooks) == 1
        assert webhooks[0].id == test_webhook.id

    async def test_get_webhooks_filter_active(
        self, webhook_service: WebhookService, test_db: AsyncSession
    ):
        """Test filtering webhooks by active status."""
        # Create active and inactive webhooks
        active = Webhook(
            name="Active",
            url="https://example.com/active",
            events=["match_start"],
            is_active=True
        )
        inactive = Webhook(
            name="Inactive",
            url="https://example.com/inactive",
            events=["match_start"],
            is_active=False
        )
        test_db.add_all([active, inactive])
        await test_db.commit()
        
        # Get only active
        webhooks = await webhook_service.get_webhooks(is_active=True)
        
        assert len(webhooks) == 1
        assert webhooks[0].name == "Active"

    async def test_update_webhook(
        self, webhook_service: WebhookService, test_webhook
    ):
        """Test updating a webhook."""
        update_data = WebhookUpdate(name="Updated Name", is_active=False)
        
        webhook = await webhook_service.update_webhook(test_webhook.id, update_data)
        
        assert webhook is not None
        assert webhook.name == "Updated Name"
        assert webhook.is_active is False

    async def test_update_webhook_not_found(
        self, webhook_service: WebhookService
    ):
        """Test updating a non-existent webhook."""
        update_data = WebhookUpdate(name="Test")
        
        webhook = await webhook_service.update_webhook(99999, update_data)
        
        assert webhook is None

    async def test_delete_webhook(
        self, webhook_service: WebhookService, test_webhook
    ):
        """Test deleting a webhook."""
        result = await webhook_service.delete_webhook(test_webhook.id)
        
        assert result is True
        
        # Verify it's deleted
        webhook = await webhook_service.get_webhook(test_webhook.id)
        assert webhook is None

    async def test_delete_webhook_not_found(
        self, webhook_service: WebhookService
    ):
        """Test deleting a non-existent webhook."""
        result = await webhook_service.delete_webhook(99999)
        
        assert result is False


class TestWebhookDelivery:
    """Tests for webhook delivery operations."""

    @patch("httpx.AsyncClient.post")
    async def test_trigger_event_success(
        self, mock_post, webhook_service: WebhookService, test_webhook
    ):
        """Test triggering an event successfully."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response
        
        deliveries = await webhook_service.trigger_event(
            WebhookEventType.VALUE_BET_FOUND,
            {"match_id": 123, "odds": 2.5}
        )
        
        assert len(deliveries) == 1
        # Note: The delivery status check may need to await db refresh
        # due to async updates

    async def test_trigger_event_no_subscribers(
        self, webhook_service: WebhookService, test_webhook
    ):
        """Test triggering an event with no subscribers."""
        deliveries = await webhook_service.trigger_event(
            WebhookEventType.ARBITRAGE_FOUND,  # Not subscribed
            {"data": "test"}
        )
        
        assert len(deliveries) == 0

    @patch("httpx.AsyncClient.post")
    async def test_trigger_event_failure(
        self, mock_post, webhook_service: WebhookService, test_webhook
    ):
        """Test handling delivery failure."""
        # Mock failed response
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        
        deliveries = await webhook_service.trigger_event(
            WebhookEventType.VALUE_BET_FOUND,
            {"match_id": 123}
        )
        
        assert len(deliveries) == 1
        # The delivery should be marked for retry

    @patch("httpx.AsyncClient.post")
    async def test_delivery_includes_signature(
        self, mock_post, webhook_service: WebhookService, test_webhook
    ):
        """Test that deliveries include HMAC signature."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response
        
        await webhook_service.trigger_event(
            WebhookEventType.VALUE_BET_FOUND,
            {"test": "data"}
        )
        
        # Verify signature header was included
        call_args = mock_post.call_args
        headers = call_args.kwargs.get("headers", {})
        assert "X-Webhook-Signature-256" in headers


class TestWebhookSignature:
    """Tests for webhook signature generation."""

    async def test_sign_payload(self, webhook_service: WebhookService):
        """Test payload signing."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        
        signature = webhook_service._sign_payload(payload, secret)
        
        assert signature is not None
        assert len(signature) == 64  # SHA256 hex digest length

    async def test_sign_payload_consistency(
        self, webhook_service: WebhookService
    ):
        """Test that signing is deterministic."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        
        sig1 = webhook_service._sign_payload(payload, secret)
        sig2 = webhook_service._sign_payload(payload, secret)
        
        assert sig1 == sig2

    async def test_sign_payload_different_secrets(
        self, webhook_service: WebhookService
    ):
        """Test that different secrets produce different signatures."""
        payload = '{"test": "data"}'
        
        sig1 = webhook_service._sign_payload(payload, "secret1")
        sig2 = webhook_service._sign_payload(payload, "secret2")
        
        assert sig1 != sig2


class TestWebhookTest:
    """Tests for webhook test functionality."""

    @patch("httpx.AsyncClient.post")
    async def test_test_webhook_success(
        self, mock_post, webhook_service: WebhookService, test_webhook
    ):
        """Test successful webhook test."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response
        
        result = await webhook_service.test_webhook(test_webhook.id)
        
        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["response_time_ms"] is not None

    @patch("httpx.AsyncClient.post")
    async def test_test_webhook_failure(
        self, mock_post, webhook_service: WebhookService, test_webhook
    ):
        """Test failed webhook test."""
        mock_post.side_effect = httpx.ConnectError("Connection failed")
        
        result = await webhook_service.test_webhook(test_webhook.id)
        
        assert result["success"] is False
        assert result["error"] is not None

    async def test_test_webhook_not_found(
        self, webhook_service: WebhookService
    ):
        """Test testing non-existent webhook."""
        result = await webhook_service.test_webhook(99999)
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @patch("httpx.AsyncClient.post")
    async def test_test_webhook_with_custom_payload(
        self, mock_post, webhook_service: WebhookService, test_webhook
    ):
        """Test webhook test with custom payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response
        
        custom_payload = {"custom": "data", "test_value": 123}
        
        result = await webhook_service.test_webhook(
            test_webhook.id,
            custom_payload=custom_payload
        )
        
        assert result["success"] is True
        
        # Verify custom payload was sent
        call_args = mock_post.call_args
        sent_content = call_args.kwargs.get("content", "")
        assert "custom" in sent_content


class TestWebhookRetry:
    """Tests for webhook retry functionality."""

    async def test_retry_failed_deliveries_empty(
        self, webhook_service: WebhookService
    ):
        """Test retrying when no deliveries need retry."""
        count = await webhook_service.retry_failed_deliveries()
        
        assert count == 0

    async def test_retry_failed_deliveries(
        self, webhook_service: WebhookService, test_db: AsyncSession, test_webhook
    ):
        """Test retrying failed deliveries."""
        # Create a delivery due for retry
        delivery = WebhookDelivery(
            webhook_id=test_webhook.id,
            event_type="value_bet_found",
            payload={"test": "data"},
            status=WebhookStatus.RETRYING.value,
            attempts=1,
            next_retry_at=datetime.utcnow() - timedelta(minutes=5)
        )
        test_db.add(delivery)
        await test_db.commit()
        
        with patch.object(
            webhook_service, "_deliver_webhook", return_value=True
        ):
            count = await webhook_service.retry_failed_deliveries()
        
        assert count == 1


class TestWebhookHistory:
    """Tests for webhook delivery history."""

    async def test_get_delivery_history_empty(
        self, webhook_service: WebhookService
    ):
        """Test getting history when empty."""
        history = await webhook_service.get_delivery_history()
        
        assert isinstance(history, list)
        assert len(history) == 0

    async def test_get_delivery_history(
        self, webhook_service: WebhookService, test_db: AsyncSession, test_webhook
    ):
        """Test getting delivery history."""
        # Create deliveries
        for i in range(3):
            delivery = WebhookDelivery(
                webhook_id=test_webhook.id,
                event_type="value_bet_found",
                payload={"index": i},
                status=WebhookStatus.DELIVERED.value,
                attempts=1
            )
            test_db.add(delivery)
        await test_db.commit()
        
        history = await webhook_service.get_delivery_history(
            webhook_id=test_webhook.id
        )
        
        assert len(history) == 3

    async def test_get_delivery_history_filter_by_status(
        self, webhook_service: WebhookService, test_db: AsyncSession, test_webhook
    ):
        """Test filtering history by status."""
        # Create deliveries with different statuses
        delivered = WebhookDelivery(
            webhook_id=test_webhook.id,
            event_type="match_start",
            payload={},
            status=WebhookStatus.DELIVERED.value,
            attempts=1
        )
        failed = WebhookDelivery(
            webhook_id=test_webhook.id,
            event_type="match_start",
            payload={},
            status=WebhookStatus.FAILED.value,
            attempts=3
        )
        test_db.add_all([delivered, failed])
        await test_db.commit()
        
        # Get only failed
        history = await webhook_service.get_delivery_history(
            status=WebhookStatus.FAILED.value
        )
        
        assert len(history) == 1
        assert history[0].status == WebhookStatus.FAILED.value


class TestWebhookStats:
    """Tests for webhook statistics."""

    async def test_get_stats_empty(self, webhook_service: WebhookService):
        """Test getting stats when no webhooks exist."""
        stats = await webhook_service.get_stats()
        
        assert stats["total_webhooks"] == 0
        assert stats["total_deliveries"] == 0
        assert stats["success_rate"] == 0

    async def test_get_stats_with_webhooks(
        self, webhook_service: WebhookService, test_db: AsyncSession
    ):
        """Test getting stats with webhooks."""
        # Create webhook with stats
        webhook = Webhook(
            name="Test",
            url="https://example.com",
            events=["match_start"],
            is_active=True,
            total_deliveries=100,
            successful_deliveries=90,
            failed_deliveries=10
        )
        test_db.add(webhook)
        await test_db.commit()
        
        stats = await webhook_service.get_stats()
        
        assert stats["total_webhooks"] == 1
        assert stats["active_webhooks"] == 1
        assert stats["total_deliveries"] == 100
        assert stats["successful_deliveries"] == 90
        assert stats["failed_deliveries"] == 10
        assert stats["success_rate"] == 90.0


class TestTriggerWebhookEvent:
    """Tests for the convenience trigger function."""

    @patch("app.services.webhook.WebhookService.trigger_event")
    @patch("app.services.webhook.WebhookService.close")
    async def test_trigger_webhook_event(
        self, mock_close, mock_trigger, test_db: AsyncSession
    ):
        """Test the convenience trigger function."""
        mock_trigger.return_value = []
        
        await trigger_webhook_event(
            test_db,
            WebhookEventType.VALUE_BET_FOUND,
            {"match_id": 123}
        )
        
        mock_trigger.assert_called_once()
        mock_close.assert_called_once()
