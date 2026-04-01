"""
Tests for WebSocket functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from app.core.websocket import (
    ConnectionManager, 
    Connection, 
    ChannelType,
    broadcast_live_match_update,
    broadcast_odds_update,
    broadcast_value_bet,
    broadcast_prediction,
    send_notification,
    manager
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def connection_manager():
    """Create a fresh connection manager for each test."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestConnectionManager:
    """Tests for ConnectionManager."""

    async def test_connect(self, connection_manager, mock_websocket):
        """Test connecting a WebSocket."""
        connection = await connection_manager.connect(
            mock_websocket,
            "conn_1"
        )
        
        assert connection is not None
        assert "conn_1" in connection_manager.active_connections
        mock_websocket.accept.assert_called_once()
        mock_websocket.send_json.assert_called_once()

    async def test_connect_with_user_id(self, connection_manager, mock_websocket):
        """Test connecting with user ID."""
        connection = await connection_manager.connect(
            mock_websocket,
            "conn_1",
            user_id=123
        )
        
        assert connection.user_id == 123

    async def test_disconnect(self, connection_manager, mock_websocket):
        """Test disconnecting a WebSocket."""
        await connection_manager.connect(mock_websocket, "conn_1")
        
        await connection_manager.disconnect("conn_1")
        
        assert "conn_1" not in connection_manager.active_connections

    async def test_disconnect_with_subscriptions(
        self, connection_manager, mock_websocket
    ):
        """Test disconnecting removes channel subscriptions."""
        await connection_manager.connect(mock_websocket, "conn_1")
        await connection_manager.subscribe("conn_1", "live_matches")
        
        await connection_manager.disconnect("conn_1")
        
        assert "conn_1" not in connection_manager.channel_subscribers.get(
            "live_matches", set()
        )

    async def test_disconnect_nonexistent(self, connection_manager):
        """Test disconnecting non-existent connection."""
        # Should not raise
        await connection_manager.disconnect("nonexistent")


class TestChannelSubscription:
    """Tests for channel subscription."""

    async def test_subscribe(self, connection_manager, mock_websocket):
        """Test subscribing to a channel."""
        await connection_manager.connect(mock_websocket, "conn_1")
        
        result = await connection_manager.subscribe("conn_1", "live_matches")
        
        assert result is True
        assert "live_matches" in connection_manager.active_connections["conn_1"].subscriptions
        assert "conn_1" in connection_manager.channel_subscribers["live_matches"]

    async def test_subscribe_nonexistent_connection(self, connection_manager):
        """Test subscribing non-existent connection."""
        result = await connection_manager.subscribe("nonexistent", "live_matches")
        
        assert result is False

    async def test_subscribe_multiple_channels(
        self, connection_manager, mock_websocket
    ):
        """Test subscribing to multiple channels."""
        await connection_manager.connect(mock_websocket, "conn_1")
        
        await connection_manager.subscribe("conn_1", "live_matches")
        await connection_manager.subscribe("conn_1", "value_bets")
        await connection_manager.subscribe("conn_1", "predictions")
        
        subscriptions = connection_manager.active_connections["conn_1"].subscriptions
        assert len(subscriptions) == 3

    async def test_unsubscribe(self, connection_manager, mock_websocket):
        """Test unsubscribing from a channel."""
        await connection_manager.connect(mock_websocket, "conn_1")
        await connection_manager.subscribe("conn_1", "live_matches")
        
        result = await connection_manager.unsubscribe("conn_1", "live_matches")
        
        assert result is True
        assert "live_matches" not in connection_manager.active_connections["conn_1"].subscriptions

    async def test_unsubscribe_nonexistent_connection(self, connection_manager):
        """Test unsubscribing non-existent connection."""
        result = await connection_manager.unsubscribe("nonexistent", "live_matches")
        
        assert result is False


class TestMessageSending:
    """Tests for message sending."""

    async def test_send_personal(self, connection_manager, mock_websocket):
        """Test sending personal message."""
        await connection_manager.connect(mock_websocket, "conn_1")
        
        # Reset mock to ignore welcome message
        mock_websocket.send_json.reset_mock()
        
        result = await connection_manager.send_personal(
            "conn_1",
            {"type": "test", "data": "hello"}
        )
        
        assert result is True
        mock_websocket.send_json.assert_called_once_with(
            {"type": "test", "data": "hello"}
        )

    async def test_send_personal_nonexistent(self, connection_manager):
        """Test sending to non-existent connection."""
        result = await connection_manager.send_personal(
            "nonexistent",
            {"data": "test"}
        )
        
        assert result is False

    async def test_send_personal_failed(self, connection_manager, mock_websocket):
        """Test handling send failure."""
        await connection_manager.connect(mock_websocket, "conn_1")
        mock_websocket.send_json.side_effect = Exception("Connection closed")
        
        result = await connection_manager.send_personal(
            "conn_1",
            {"data": "test"}
        )
        
        assert result is False
        # Connection should be disconnected
        assert "conn_1" not in connection_manager.active_connections


class TestBroadcasting:
    """Tests for broadcasting messages."""

    async def test_broadcast_to_channel(self, connection_manager, mock_websocket):
        """Test broadcasting to a channel."""
        await connection_manager.connect(mock_websocket, "conn_1")
        await connection_manager.subscribe("conn_1", "live_matches")
        
        mock_websocket.send_json.reset_mock()
        
        count = await connection_manager.broadcast_to_channel(
            "live_matches",
            {"type": "update", "data": "test"}
        )
        
        assert count == 1
        mock_websocket.send_json.assert_called_once()

    async def test_broadcast_to_empty_channel(self, connection_manager):
        """Test broadcasting to channel with no subscribers."""
        count = await connection_manager.broadcast_to_channel(
            "empty_channel",
            {"data": "test"}
        )
        
        assert count == 0

    async def test_broadcast_to_channel_multiple_subscribers(
        self, connection_manager
    ):
        """Test broadcasting to multiple subscribers."""
        # Create multiple connections
        websockets = []
        for i in range(3):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            websockets.append(ws)
            await connection_manager.connect(ws, f"conn_{i}")
            await connection_manager.subscribe(f"conn_{i}", "live_matches")
        
        count = await connection_manager.broadcast_to_channel(
            "live_matches",
            {"type": "update"}
        )
        
        assert count == 3

    async def test_broadcast_to_all(self, connection_manager):
        """Test broadcasting to all connections."""
        websockets = []
        for i in range(3):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            websockets.append(ws)
            await connection_manager.connect(ws, f"conn_{i}")
        
        count = await connection_manager.broadcast_to_all({"type": "global"})
        
        assert count == 3

    async def test_broadcast_to_user(self, connection_manager):
        """Test broadcasting to specific user."""
        # Create connections for different users
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        
        await connection_manager.connect(ws1, "conn_1", user_id=100)
        await connection_manager.connect(ws2, "conn_2", user_id=200)
        
        ws1.send_json.reset_mock()
        ws2.send_json.reset_mock()
        
        count = await connection_manager.broadcast_to_user(
            100,
            {"type": "user_notification"}
        )
        
        assert count == 1
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_not_called()


class TestConnectionStats:
    """Tests for connection statistics."""

    async def test_get_channel_subscribers_count(
        self, connection_manager, mock_websocket
    ):
        """Test getting channel subscriber count."""
        await connection_manager.connect(mock_websocket, "conn_1")
        await connection_manager.subscribe("conn_1", "live_matches")
        
        count = connection_manager.get_channel_subscribers_count("live_matches")
        
        assert count == 1

    async def test_get_channel_subscribers_count_empty(self, connection_manager):
        """Test getting count for empty channel."""
        count = connection_manager.get_channel_subscribers_count("empty")
        
        assert count == 0

    async def test_get_active_connections_count(
        self, connection_manager, mock_websocket
    ):
        """Test getting active connection count."""
        assert connection_manager.get_active_connections_count() == 0
        
        await connection_manager.connect(mock_websocket, "conn_1")
        
        assert connection_manager.get_active_connections_count() == 1

    async def test_get_stats(self, connection_manager, mock_websocket):
        """Test getting full statistics."""
        await connection_manager.connect(mock_websocket, "conn_1")
        await connection_manager.subscribe("conn_1", "live_matches")
        await connection_manager.subscribe("conn_1", "value_bets")
        
        stats = connection_manager.get_stats()
        
        assert stats["total_connections"] == 1
        assert "live_matches" in stats["channels"]
        assert "value_bets" in stats["channels"]


class TestBroadcastHelpers:
    """Tests for broadcast helper functions."""

    @patch("app.core.websocket.manager")
    async def test_broadcast_live_match_update(self, mock_manager):
        """Test broadcasting live match update."""
        mock_manager.broadcast_to_channel = AsyncMock(return_value=5)
        
        match_data = {
            "match_id": 123,
            "home_score": 2,
            "away_score": 1,
            "status": "live"
        }
        
        count = await broadcast_live_match_update(match_data)
        
        assert count == 5
        # Should broadcast to both live_matches and match:123
        assert mock_manager.broadcast_to_channel.call_count == 2

    @patch("app.core.websocket.manager")
    async def test_broadcast_odds_update(self, mock_manager):
        """Test broadcasting odds update."""
        mock_manager.broadcast_to_channel = AsyncMock(return_value=3)
        
        odds_data = {
            "home_odds": 2.10,
            "draw_odds": 3.50,
            "away_odds": 3.20
        }
        
        count = await broadcast_odds_update(123, odds_data)
        
        assert count == 3
        mock_manager.broadcast_to_channel.assert_called_once()

    @patch("app.core.websocket.manager")
    async def test_broadcast_value_bet(self, mock_manager):
        """Test broadcasting value bet."""
        mock_manager.broadcast_to_channel = AsyncMock(return_value=10)
        
        value_bet = {
            "match_id": 123,
            "edge": 8.5,
            "market": "home_win"
        }
        
        count = await broadcast_value_bet(value_bet)
        
        assert count == 10
        mock_manager.broadcast_to_channel.assert_called_with(
            ChannelType.VALUE_BETS.value,
            {
                "type": "value_bet",
                "channel": ChannelType.VALUE_BETS.value,
                "data": value_bet,
                "timestamp": mock_manager.broadcast_to_channel.call_args[0][1]["timestamp"]
            }
        )

    @patch("app.core.websocket.manager")
    async def test_broadcast_prediction(self, mock_manager):
        """Test broadcasting prediction."""
        mock_manager.broadcast_to_channel = AsyncMock(return_value=7)
        
        prediction = {
            "match_id": 123,
            "home_win_prob": 0.45,
            "model": "poisson"
        }
        
        count = await broadcast_prediction(prediction)
        
        assert count == 7

    @patch("app.core.websocket.manager")
    async def test_send_notification(self, mock_manager):
        """Test sending user notification."""
        mock_manager.broadcast_to_user = AsyncMock(return_value=2)
        
        notification = {
            "title": "Value Bet Found",
            "message": "New opportunity available"
        }
        
        count = await send_notification(100, notification)
        
        assert count == 2
        mock_manager.broadcast_to_user.assert_called_once()


class TestChannelTypes:
    """Tests for channel types."""

    def test_channel_types_exist(self):
        """Test all channel types are defined."""
        assert ChannelType.LIVE_MATCHES.value == "live_matches"
        assert ChannelType.MATCH.value == "match"
        assert ChannelType.ODDS.value == "odds"
        assert ChannelType.PREDICTIONS.value == "predictions"
        assert ChannelType.VALUE_BETS.value == "value_bets"
        assert ChannelType.NOTIFICATIONS.value == "notifications"


class TestConnection:
    """Tests for Connection dataclass."""

    def test_connection_defaults(self, mock_websocket):
        """Test Connection default values."""
        conn = Connection(websocket=mock_websocket)
        
        assert conn.user_id is None
        assert conn.subscriptions == set()
        assert conn.connected_at is not None

    def test_connection_with_values(self, mock_websocket):
        """Test Connection with custom values."""
        conn = Connection(
            websocket=mock_websocket,
            user_id=123,
            subscriptions={"live_matches", "value_bets"}
        )
        
        assert conn.user_id == 123
        assert len(conn.subscriptions) == 2


class TestConcurrency:
    """Tests for concurrent operations."""

    async def test_concurrent_connections(self, connection_manager):
        """Test handling multiple concurrent connections."""
        import asyncio
        
        async def connect_client(i):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            await connection_manager.connect(ws, f"conn_{i}")
            return f"conn_{i}"
        
        # Connect 10 clients concurrently
        tasks = [connect_client(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        assert connection_manager.get_active_connections_count() == 10

    async def test_concurrent_subscriptions(self, connection_manager):
        """Test handling concurrent subscriptions."""
        import asyncio
        
        # First create a connection
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        await connection_manager.connect(ws, "conn_1")
        
        # Subscribe to multiple channels concurrently
        channels = [f"channel_{i}" for i in range(10)]
        tasks = [
            connection_manager.subscribe("conn_1", ch) 
            for ch in channels
        ]
        await asyncio.gather(*tasks)
        
        assert len(connection_manager.active_connections["conn_1"].subscriptions) == 10
