"""
WebSocket API endpoints for real-time updates.
"""

import uuid
from typing import Optional
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket import manager, ChannelType
from app.core.database import get_db
from app.auth.jwt import decode_token

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_user_from_token(token: Optional[str]) -> Optional[int]:
    """Extract user ID from JWT token if provided."""
    if not token:
        return None
    
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except Exception:
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Main WebSocket endpoint for real-time updates.
    
    Query Parameters:
        token: Optional JWT token for authenticated connections
        
    Message Format (client -> server):
        {
            "action": "subscribe" | "unsubscribe",
            "channel": "channel_name"
        }
        
    Message Format (server -> client):
        {
            "type": "event_type",
            "channel": "channel_name",
            "data": {...},
            "timestamp": "ISO datetime"
        }
    
    Available Channels:
        - live_matches: Updates for all live matches
        - match:{match_id}: Updates for a specific match
        - odds:{match_id}: Odds updates for a specific match
        - predictions: New predictions
        - value_bets: Value bet opportunities
        - notifications: User-specific notifications (requires auth)
    """
    connection_id = str(uuid.uuid4())
    user_id = await get_user_from_token(token)
    
    try:
        # Accept connection
        connection = await manager.connect(
            websocket,
            connection_id,
            user_id
        )
        
        # Auto-subscribe to live matches
        await manager.subscribe(connection_id, ChannelType.LIVE_MATCHES.value)
        
        # If authenticated, subscribe to notifications
        if user_id:
            await manager.subscribe(connection_id, ChannelType.NOTIFICATIONS.value)
        
        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_json()
                await handle_client_message(connection_id, data)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                await manager.send_personal(connection_id, {
                    "type": "error",
                    "channel": "system",
                    "data": {"message": str(e)}
                })
                
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(connection_id)


async def handle_client_message(
    connection_id: str,
    data: dict
) -> None:
    """
    Handle incoming client messages.
    
    Args:
        connection_id: Connection ID
        data: Message data
    """
    action = data.get("action")
    channel = data.get("channel")
    
    if not action or not channel:
        await manager.send_personal(connection_id, {
            "type": "error",
            "channel": "system",
            "data": {"message": "Invalid message format"}
        })
        return
    
    if action == "subscribe":
        success = await manager.subscribe(connection_id, channel)
        await manager.send_personal(connection_id, {
            "type": "subscribed" if success else "error",
            "channel": channel,
            "data": {
                "message": f"Subscribed to {channel}" if success 
                    else f"Failed to subscribe to {channel}"
            }
        })
        
    elif action == "unsubscribe":
        success = await manager.unsubscribe(connection_id, channel)
        await manager.send_personal(connection_id, {
            "type": "unsubscribed" if success else "error",
            "channel": channel,
            "data": {
                "message": f"Unsubscribed from {channel}" if success 
                    else f"Failed to unsubscribe from {channel}"
            }
        })
        
    elif action == "ping":
        await manager.send_personal(connection_id, {
            "type": "pong",
            "channel": "system",
            "data": {}
        })
        
    else:
        await manager.send_personal(connection_id, {
            "type": "error",
            "channel": "system",
            "data": {"message": f"Unknown action: {action}"}
        })


@router.websocket("/ws/match/{match_id}")
async def match_websocket(
    websocket: WebSocket,
    match_id: int,
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for a specific match.
    
    Automatically subscribes to:
        - match:{match_id}
        - odds:{match_id}
    """
    connection_id = str(uuid.uuid4())
    user_id = await get_user_from_token(token)
    
    try:
        connection = await manager.connect(
            websocket,
            connection_id,
            user_id
        )
        
        # Subscribe to match channels
        await manager.subscribe(connection_id, f"match:{match_id}")
        await manager.subscribe(connection_id, f"odds:{match_id}")
        
        # Handle messages
        while True:
            try:
                data = await websocket.receive_json()
                await handle_client_message(connection_id, data)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(connection_id)


@router.get("/ws/stats")
async def websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Returns:
        Connection and channel statistics
    """
    return manager.get_stats()


@router.get("/ws/channels")
async def list_channels():
    """
    List available WebSocket channels.
    
    Returns:
        List of available channels with descriptions
    """
    return {
        "channels": [
            {
                "name": ChannelType.LIVE_MATCHES.value,
                "description": "Updates for all live matches",
                "auto_subscribe": True
            },
            {
                "name": "match:{match_id}",
                "description": "Updates for a specific match",
                "auto_subscribe": False,
                "example": "match:123"
            },
            {
                "name": "odds:{match_id}",
                "description": "Odds updates for a specific match",
                "auto_subscribe": False,
                "example": "odds:123"
            },
            {
                "name": ChannelType.PREDICTIONS.value,
                "description": "New prediction notifications",
                "auto_subscribe": False
            },
            {
                "name": ChannelType.VALUE_BETS.value,
                "description": "Value bet opportunities",
                "auto_subscribe": False
            },
            {
                "name": ChannelType.NOTIFICATIONS.value,
                "description": "User-specific notifications (requires auth)",
                "auto_subscribe": True,
                "requires_auth": True
            }
        ]
    }
