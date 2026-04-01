"""
Tests for Webhook API endpoints.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.asyncio


class TestWebhookCRUD:
    """Tests for webhook CRUD operations."""

    async def test_create_webhook(self, client: AsyncClient, sample_webhook_data):
        """Test creating a new webhook."""
        response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_webhook_data["name"]
        assert data["url"] == sample_webhook_data["url"]
        assert data["is_active"] is True
        assert data["max_retries"] == sample_webhook_data["max_retries"]
        assert "id" in data
        assert "created_at" in data

    async def test_create_webhook_invalid_url(self, client: AsyncClient, sample_webhook_data):
        """Test creating a webhook with invalid URL."""
        sample_webhook_data["url"] = "not-a-valid-url"
        response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        
        assert response.status_code == 422

    async def test_create_webhook_missing_events(self, client: AsyncClient, sample_webhook_data):
        """Test creating a webhook without events."""
        del sample_webhook_data["events"]
        response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        
        assert response.status_code == 422

    async def test_list_webhooks_empty(self, client: AsyncClient):
        """Test listing webhooks when none exist."""
        response = await client.get("/api/v1/webhooks/")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_list_webhooks(self, client: AsyncClient, sample_webhook_data):
        """Test listing webhooks."""
        # Create a webhook first
        await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        
        response = await client.get("/api/v1/webhooks/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_webhook_data["name"]

    async def test_list_webhooks_filter_active(self, client: AsyncClient, sample_webhook_data):
        """Test filtering webhooks by active status."""
        # Create a webhook
        await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        
        # Filter by active=True
        response = await client.get("/api/v1/webhooks/", params={"is_active": True})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        # Filter by active=False
        response = await client.get("/api/v1/webhooks/", params={"is_active": False})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    async def test_get_webhook(self, client: AsyncClient, sample_webhook_data):
        """Test getting a single webhook."""
        # Create a webhook
        create_response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        webhook_id = create_response.json()["id"]
        
        response = await client.get(f"/api/v1/webhooks/{webhook_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == webhook_id
        assert data["name"] == sample_webhook_data["name"]

    async def test_get_webhook_not_found(self, client: AsyncClient):
        """Test getting a non-existent webhook."""
        response = await client.get("/api/v1/webhooks/99999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_update_webhook(self, client: AsyncClient, sample_webhook_data):
        """Test updating a webhook."""
        # Create a webhook
        create_response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        webhook_id = create_response.json()["id"]
        
        # Update webhook
        update_data = {"name": "Updated Webhook Name", "is_active": False}
        response = await client.patch(f"/api/v1/webhooks/{webhook_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Webhook Name"
        assert data["is_active"] is False

    async def test_update_webhook_not_found(self, client: AsyncClient):
        """Test updating a non-existent webhook."""
        response = await client.patch("/api/v1/webhooks/99999", json={"name": "Test"})
        
        assert response.status_code == 404

    async def test_delete_webhook(self, client: AsyncClient, sample_webhook_data):
        """Test deleting a webhook."""
        # Create a webhook
        create_response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        webhook_id = create_response.json()["id"]
        
        # Delete webhook
        response = await client.delete(f"/api/v1/webhooks/{webhook_id}")
        
        assert response.status_code == 204
        
        # Verify it's deleted
        get_response = await client.get(f"/api/v1/webhooks/{webhook_id}")
        assert get_response.status_code == 404

    async def test_delete_webhook_not_found(self, client: AsyncClient):
        """Test deleting a non-existent webhook."""
        response = await client.delete("/api/v1/webhooks/99999")
        
        assert response.status_code == 404


class TestWebhookEvents:
    """Tests for webhook event types."""

    async def test_list_event_types(self, client: AsyncClient):
        """Test listing available event types."""
        response = await client.get("/api/v1/webhooks/events")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Check event structure
        event = data[0]
        assert "type" in event
        assert "name" in event
        assert "description" in event

    async def test_event_types_include_expected(self, client: AsyncClient):
        """Test that expected event types are present."""
        response = await client.get("/api/v1/webhooks/events")
        data = response.json()
        
        event_types = [e["type"] for e in data]
        expected_events = ["value_bet_found", "prediction_ready", "match_start", "match_end"]
        
        for expected in expected_events:
            assert expected in event_types


class TestWebhookStats:
    """Tests for webhook statistics."""

    async def test_get_stats_empty(self, client: AsyncClient):
        """Test getting stats when no webhooks exist."""
        response = await client.get("/api/v1/webhooks/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_webhooks"] == 0
        assert data["total_deliveries"] == 0

    async def test_get_stats_with_webhook(self, client: AsyncClient, sample_webhook_data):
        """Test getting stats with webhooks."""
        # Create a webhook
        await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        
        response = await client.get("/api/v1/webhooks/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_webhooks"] == 1
        assert data["active_webhooks"] == 1


class TestWebhookDeliveries:
    """Tests for webhook delivery operations."""

    async def test_get_deliveries_empty(self, client: AsyncClient, sample_webhook_data):
        """Test getting deliveries when none exist."""
        # Create a webhook
        create_response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        webhook_id = create_response.json()["id"]
        
        response = await client.get(f"/api/v1/webhooks/{webhook_id}/deliveries")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_deliveries_not_found(self, client: AsyncClient):
        """Test getting deliveries for non-existent webhook."""
        response = await client.get("/api/v1/webhooks/99999/deliveries")
        
        assert response.status_code == 404


class TestWebhookTest:
    """Tests for webhook test functionality."""

    @patch("app.services.webhook.WebhookService.test_webhook")
    async def test_test_webhook_success(
        self, mock_test, client: AsyncClient, sample_webhook_data
    ):
        """Test testing a webhook successfully."""
        # Mock the test_webhook method
        mock_test.return_value = {
            "success": True,
            "status_code": 200,
            "response_time_ms": 150.5,
            "error": None
        }
        
        # Create a webhook
        create_response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        webhook_id = create_response.json()["id"]
        
        response = await client.post(f"/api/v1/webhooks/{webhook_id}/test")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status_code"] == 200
        assert data["response_time_ms"] == 150.5

    async def test_test_webhook_not_found(self, client: AsyncClient):
        """Test testing a non-existent webhook."""
        response = await client.post("/api/v1/webhooks/99999/test")
        
        assert response.status_code == 404

    @patch("app.services.webhook.WebhookService.test_webhook")
    async def test_test_webhook_with_custom_payload(
        self, mock_test, client: AsyncClient, sample_webhook_data
    ):
        """Test testing a webhook with custom payload."""
        mock_test.return_value = {
            "success": True,
            "status_code": 200,
            "response_time_ms": 100.0,
            "error": None
        }
        
        # Create a webhook
        create_response = await client.post("/api/v1/webhooks/", json=sample_webhook_data)
        webhook_id = create_response.json()["id"]
        
        test_data = {
            "event_type": "value_bet_found",
            "payload": {"custom": "data"}
        }
        
        response = await client.post(
            f"/api/v1/webhooks/{webhook_id}/test",
            json=test_data
        )
        
        assert response.status_code == 200


class TestWebhookPagination:
    """Tests for webhook pagination."""

    async def test_pagination_skip(self, client: AsyncClient, sample_webhook_data):
        """Test skip parameter in pagination."""
        # Create multiple webhooks
        for i in range(3):
            data = sample_webhook_data.copy()
            data["name"] = f"Webhook {i}"
            await client.post("/api/v1/webhooks/", json=data)
        
        # Get with skip
        response = await client.get("/api/v1/webhooks/", params={"skip": 1})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_pagination_limit(self, client: AsyncClient, sample_webhook_data):
        """Test limit parameter in pagination."""
        # Create multiple webhooks
        for i in range(5):
            data = sample_webhook_data.copy()
            data["name"] = f"Webhook {i}"
            await client.post("/api/v1/webhooks/", json=data)
        
        # Get with limit
        response = await client.get("/api/v1/webhooks/", params={"limit": 2})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_pagination_combined(self, client: AsyncClient, sample_webhook_data):
        """Test combined skip and limit."""
        # Create multiple webhooks
        for i in range(5):
            data = sample_webhook_data.copy()
            data["name"] = f"Webhook {i}"
            await client.post("/api/v1/webhooks/", json=data)
        
        response = await client.get(
            "/api/v1/webhooks/",
            params={"skip": 2, "limit": 2}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
