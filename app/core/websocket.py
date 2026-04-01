"""
WebSocket manager for real-time updates.
"""

import asyncio
import json
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """Types of WebSocket channels."""
    LIVE_MATCHES = "live_matches"
    MATCH = "match"  # match:{match_id}
    ODDS = "odds"  # odds:{match_id}
    PREDICTIONS = "predictions"
    VALUE_BETS = "value_bets"
    NOTIFICATIONS = "notifications"


class WSMessage(BaseModel):
    """WebSocket message structure."""
    type: str  # event type
    channel: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Connection:
    """Represents a WebSocket connection."""
    websocket: WebSocket
    user_id: Optional[int] = None
    subscriptions: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)


class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting.
    
    Features:
    - Connection pooling
    - Channel subscriptions
    - Broadcasting to specific channels
    - User-specific messaging
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Dict[str, Connection] = {}
        self.channel_subscribers: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(
        self, 
        websocket: WebSocket,
        connection_id: str,
        user_id: Optional[int] = None
    ) -> Connection:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket instance
            connection_id: Unique connection identifier
            user_id: Optional user ID for authenticated connections
            
        Returns:
            Connection object
        """
        await websocket.accept()
        
        connection = Connection(
            websocket=websocket,
            user_id=user_id,
            subscriptions=set()
        )
        
        async with self._lock:
            self.active_connections[connection_id] = connection
        
        logger.info(f"WebSocket connected: {connection_id}")
        
        # Send welcome message
        await self.send_personal(connection_id, {
            "type": "connected",
            "channel": "system",
            "data": {
                "connection_id": connection_id,
                "message": "Connected to Sports Data Analytics"
            }
        })
        
        return connection
    
    async def disconnect(self, connection_id: str) -> None:
        """
        Disconnect a WebSocket connection.
        
        Args:
            connection_id: Connection to disconnect
        """
        async with self._lock:
            if connection_id in self.active_connections:
                connection = self.active_connections[connection_id]
                
                # Remove from all subscribed channels
                for channel in connection.subscriptions:
                    if channel in self.channel_subscribers:
                        self.channel_subscribers[channel].discard(connection_id)
                
                del self.active_connections[connection_id]
                logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def subscribe(
        self, 
        connection_id: str, 
        channel: str
    ) -> bool:
        """
        Subscribe a connection to a channel.
        
        Args:
            connection_id: Connection ID
            channel: Channel to subscribe to
            
        Returns:
            True if subscription successful
        """
        async with self._lock:
            if connection_id not in self.active_connections:
                return False
            
            connection = self.active_connections[connection_id]
            connection.subscriptions.add(channel)
            
            if channel not in self.channel_subscribers:
                self.channel_subscribers[channel] = set()
            
            self.channel_subscribers[channel].add(connection_id)
            logger.debug(f"Connection {connection_id} subscribed to {channel}")
            
            return True
    
    async def unsubscribe(
        self, 
        connection_id: str, 
        channel: str
    ) -> bool:
        """
        Unsubscribe a connection from a channel.
        
        Args:
            connection_id: Connection ID
            channel: Channel to unsubscribe from
            
        Returns:
            True if unsubscription successful
        """
        async with self._lock:
            if connection_id not in self.active_connections:
                return False
            
            connection = self.active_connections[connection_id]
            connection.subscriptions.discard(channel)
            
            if channel in self.channel_subscribers:
                self.channel_subscribers[channel].discard(connection_id)
            
            return True
    
    async def send_personal(
        self, 
        connection_id: str, 
        message: Dict[str, Any]
    ) -> bool:
        """
        Send a message to a specific connection.
        
        Args:
            connection_id: Target connection
            message: Message to send
            
        Returns:
            True if message sent successfully
        """
        if connection_id not in self.active_connections:
            return False
        
        try:
            connection = self.active_connections[connection_id]
            await connection.websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False
    
    async def broadcast_to_channel(
        self, 
        channel: str, 
        message: Dict[str, Any]
    ) -> int:
        """
        Broadcast a message to all subscribers of a channel.
        
        Args:
            channel: Target channel
            message: Message to broadcast
            
        Returns:
            Number of connections that received the message
        """
        if channel not in self.channel_subscribers:
            return 0
        
        subscribers = list(self.channel_subscribers[channel])
        sent_count = 0
        failed_connections = []
        
        for connection_id in subscribers:
            if connection_id in self.active_connections:
                try:
                    connection = self.active_connections[connection_id]
                    await connection.websocket.send_json(message)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Broadcast failed for {connection_id}: {e}")
                    failed_connections.append(connection_id)
        
        # Clean up failed connections
        for conn_id in failed_connections:
            await self.disconnect(conn_id)
        
        return sent_count
    
    async def broadcast_to_all(
        self, 
        message: Dict[str, Any]
    ) -> int:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: Message to broadcast
            
        Returns:
            Number of connections that received the message
        """
        connection_ids = list(self.active_connections.keys())
        sent_count = 0
        failed_connections = []
        
        for connection_id in connection_ids:
            try:
                connection = self.active_connections[connection_id]
                await connection.websocket.send_json(message)
                sent_count += 1
            except Exception:
                failed_connections.append(connection_id)
        
        for conn_id in failed_connections:
            await self.disconnect(conn_id)
        
        return sent_count
    
    async def broadcast_to_user(
        self, 
        user_id: int, 
        message: Dict[str, Any]
    ) -> int:
        """
        Broadcast a message to all connections of a specific user.
        
        Args:
            user_id: Target user ID
            message: Message to send
            
        Returns:
            Number of connections that received the message
        """
        sent_count = 0
        
        for conn_id, connection in self.active_connections.items():
            if connection.user_id == user_id:
                try:
                    await connection.websocket.send_json(message)
                    sent_count += 1
                except Exception:
                    pass
        
        return sent_count
    
    def get_channel_subscribers_count(self, channel: str) -> int:
        """Get number of subscribers for a channel."""
        return len(self.channel_subscribers.get(channel, set()))
    
    def get_active_connections_count(self) -> int:
        """Get total number of active connections."""
        return len(self.active_connections)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.active_connections),
            "channels": {
                channel: len(subscribers)
                for channel, subscribers in self.channel_subscribers.items()
            }
        }


# Global connection manager instance
manager = ConnectionManager()


# Helper functions for broadcasting events

async def broadcast_live_match_update(match_data: Dict[str, Any]) -> int:
    """
    Broadcast a live match update.
    
    Args:
        match_data: Match data to broadcast
        
    Returns:
        Number of recipients
    """
    message = {
        "type": "match_update",
        "channel": ChannelType.LIVE_MATCHES.value,
        "data": match_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Broadcast to general live matches channel
    count = await manager.broadcast_to_channel(
        ChannelType.LIVE_MATCHES.value,
        message
    )
    
    # Also broadcast to specific match channel
    match_id = match_data.get("match_id")
    if match_id:
        await manager.broadcast_to_channel(
            f"match:{match_id}",
            message
        )
    
    return count


async def broadcast_odds_update(
    match_id: int,
    odds_data: Dict[str, Any]
) -> int:
    """
    Broadcast odds update for a match.
    
    Args:
        match_id: Match ID
        odds_data: Odds data
        
    Returns:
        Number of recipients
    """
    message = {
        "type": "odds_update",
        "channel": f"odds:{match_id}",
        "data": {
            "match_id": match_id,
            **odds_data
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return await manager.broadcast_to_channel(
        f"odds:{match_id}",
        message
    )


async def broadcast_value_bet(value_bet_data: Dict[str, Any]) -> int:
    """
    Broadcast a new value bet opportunity.
    
    Args:
        value_bet_data: Value bet details
        
    Returns:
        Number of recipients
    """
    message = {
        "type": "value_bet",
        "channel": ChannelType.VALUE_BETS.value,
        "data": value_bet_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return await manager.broadcast_to_channel(
        ChannelType.VALUE_BETS.value,
        message
    )


async def broadcast_prediction(prediction_data: Dict[str, Any]) -> int:
    """
    Broadcast a new prediction.
    
    Args:
        prediction_data: Prediction details
        
    Returns:
        Number of recipients
    """
    message = {
        "type": "prediction",
        "channel": ChannelType.PREDICTIONS.value,
        "data": prediction_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return await manager.broadcast_to_channel(
        ChannelType.PREDICTIONS.value,
        message
    )


async def send_notification(
    user_id: int,
    notification: Dict[str, Any]
) -> int:
    """
    Send a notification to a specific user.
    
    Args:
        user_id: Target user
        notification: Notification content
        
    Returns:
        Number of connections notified
    """
    message = {
        "type": "notification",
        "channel": ChannelType.NOTIFICATIONS.value,
        "data": notification,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return await manager.broadcast_to_user(user_id, message)
