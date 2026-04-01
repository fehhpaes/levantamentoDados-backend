"""
Notifications API Endpoints

Handles:
- User notification preferences
- Notification history
- Telegram linking/verification
- Notification statistics
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import secrets

from app.core.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.models.notification import (
    Notification,
    UserNotificationPreferences,
    TelegramVerification,
    NotificationChannel,
    NotificationType,
    NotificationStatus,
    NotificationPriority,
    DigestFrequency,
)
from app.models.notification import (
    NotificationPreferencesCreate,
    NotificationPreferencesUpdate,
    NotificationPreferencesResponse,
    NotificationResponse,
    NotificationListResponse,
    TelegramLinkRequest,
    TelegramLinkResponse,
    TelegramVerifyRequest,
    NotificationStatsResponse,
    BulkNotificationCreate,
)
from app.core.config import settings

router = APIRouter()


# ============== NOTIFICATION PREFERENCES ==============

@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's notification preferences."""
    result = await db.execute(
        select(UserNotificationPreferences).where(
            UserNotificationPreferences.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        # Create default preferences
        preferences = UserNotificationPreferences(
            user_id=current_user.id,
            enabled_alert_types=[
                NotificationType.VALUE_BET.value,
                NotificationType.MATCH_START.value,
                NotificationType.DAILY_SUMMARY.value
            ]
        )
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
    
    return preferences


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    update_data: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user's notification preferences."""
    result = await db.execute(
        select(UserNotificationPreferences).where(
            UserNotificationPreferences.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        preferences = UserNotificationPreferences(user_id=current_user.id)
        db.add(preferences)
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if hasattr(preferences, field):
            # Convert enums to values for JSON storage
            if field == "enabled_alert_types" and value:
                value = [t.value if hasattr(t, 'value') else t for t in value]
            setattr(preferences, field, value)
    
    await db.commit()
    await db.refresh(preferences)
    
    return preferences


@router.post("/preferences/reset", response_model=NotificationPreferencesResponse)
async def reset_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reset notification preferences to defaults."""
    result = await db.execute(
        select(UserNotificationPreferences).where(
            UserNotificationPreferences.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if preferences:
        await db.delete(preferences)
    
    # Create new with defaults
    preferences = UserNotificationPreferences(
        user_id=current_user.id,
        enabled_alert_types=[
            NotificationType.VALUE_BET.value,
            NotificationType.MATCH_START.value,
            NotificationType.DAILY_SUMMARY.value
        ]
    )
    db.add(preferences)
    await db.commit()
    await db.refresh(preferences)
    
    return preferences


# ============== TELEGRAM LINKING ==============

@router.post("/telegram/link", response_model=TelegramLinkResponse)
async def link_telegram_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a verification code to link Telegram account.
    
    User should send this code to our Telegram bot to complete linking.
    """
    # Generate unique verification code
    verification_code = secrets.token_urlsafe(8)[:12].upper()
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    # Delete any existing verification for this user
    await db.execute(
        TelegramVerification.__table__.delete().where(
            TelegramVerification.user_id == current_user.id
        )
    )
    
    # Create new verification
    verification = TelegramVerification(
        user_id=current_user.id,
        verification_code=verification_code,
        expires_at=expires_at
    )
    db.add(verification)
    await db.commit()
    
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'SportsAnalyticsBot')
    
    return TelegramLinkResponse(
        verification_code=verification_code,
        bot_username=bot_username,
        expires_at=expires_at,
        instructions=f"1. Abra o Telegram e procure @{bot_username}\n"
                    f"2. Inicie uma conversa com o bot\n"
                    f"3. Envie o comando: /verify {verification_code}\n"
                    f"4. O código expira em 15 minutos"
    )


@router.post("/telegram/verify")
async def verify_telegram_link(
    verify_data: TelegramVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint called by Telegram bot to verify user linking.
    
    This should be called from the bot's webhook handler.
    """
    # Find valid verification
    result = await db.execute(
        select(TelegramVerification).where(
            and_(
                TelegramVerification.verification_code == verify_data.verification_code,
                TelegramVerification.expires_at > datetime.utcnow(),
                TelegramVerification.verified_at.is_(None)
            )
        )
    )
    verification = result.scalar_one_or_none()
    
    if not verification:
        raise HTTPException(
            status_code=400, 
            detail="Invalid or expired verification code"
        )
    
    # Mark as verified
    verification.verified_at = datetime.utcnow()
    verification.telegram_chat_id = verify_data.telegram_chat_id
    verification.telegram_username = verify_data.telegram_username
    
    # Update user preferences
    result = await db.execute(
        select(UserNotificationPreferences).where(
            UserNotificationPreferences.user_id == verification.user_id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        preferences = UserNotificationPreferences(user_id=verification.user_id)
        db.add(preferences)
    
    preferences.telegram_enabled = True
    preferences.telegram_chat_id = verify_data.telegram_chat_id
    preferences.telegram_username = verify_data.telegram_username
    preferences.telegram_verified = True
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Telegram account linked successfully",
        "user_id": verification.user_id
    }


@router.delete("/telegram/unlink")
async def unlink_telegram_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unlink Telegram account from user profile."""
    result = await db.execute(
        select(UserNotificationPreferences).where(
            UserNotificationPreferences.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if preferences:
        preferences.telegram_enabled = False
        preferences.telegram_chat_id = None
        preferences.telegram_username = None
        preferences.telegram_verified = False
        await db.commit()
    
    return {"success": True, "message": "Telegram account unlinked"}


# ============== NOTIFICATIONS ==============

@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    notification_type: Optional[NotificationType] = None,
    channel: Optional[NotificationChannel] = None,
    status: Optional[NotificationStatus] = None,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's notifications with pagination and filters."""
    query = select(Notification).where(
        Notification.user_id == current_user.id
    )
    
    # Apply filters
    if notification_type:
        query = query.where(Notification.notification_type == notification_type)
    if channel:
        query = query.where(Notification.channel == channel)
    if status:
        query = query.where(Notification.status == status)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Count unread
    unread_query = select(func.count()).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None)
        )
    )
    unread_count = await db.scalar(unread_query)
    
    # Paginate
    query = query.order_by(Notification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return NotificationListResponse(
        notifications=notifications,
        total=total or 0,
        unread_count=unread_count or 0,
        page=page,
        page_size=page_size
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific notification."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == current_user.id
            )
        )
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return notification


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a notification as read."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == current_user.id
            )
        )
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if not notification.read_at:
        notification.read_at = datetime.utcnow()
        await db.commit()
    
    return {"success": True, "read_at": notification.read_at}


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all notifications as read."""
    from sqlalchemy import update
    
    await db.execute(
        update(Notification).where(
            and_(
                Notification.user_id == current_user.id,
                Notification.read_at.is_(None)
            )
        ).values(read_at=datetime.utcnow())
    )
    await db.commit()
    
    return {"success": True, "message": "All notifications marked as read"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a notification."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == current_user.id
            )
        )
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    await db.delete(notification)
    await db.commit()
    
    return {"success": True, "message": "Notification deleted"}


@router.delete("/")
async def delete_all_notifications(
    older_than_days: Optional[int] = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete all notifications or those older than specified days."""
    from sqlalchemy import delete
    
    query = delete(Notification).where(
        Notification.user_id == current_user.id
    )
    
    if older_than_days:
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        query = query.where(Notification.created_at < cutoff)
    
    result = await db.execute(query)
    await db.commit()
    
    return {
        "success": True, 
        "deleted_count": result.rowcount
    }


# ============== STATISTICS ==============

@router.get("/stats", response_model=NotificationStatsResponse)
async def get_notification_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get notification statistics for current user."""
    # Total count
    total = await db.scalar(
        select(func.count()).where(
            Notification.user_id == current_user.id
        )
    )
    
    # Unread count
    unread = await db.scalar(
        select(func.count()).where(
            and_(
                Notification.user_id == current_user.id,
                Notification.read_at.is_(None)
            )
        )
    )
    
    # Today's count
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today = await db.scalar(
        select(func.count()).where(
            and_(
                Notification.user_id == current_user.id,
                Notification.created_at >= today_start
            )
        )
    )
    
    # This week's count
    week_start = today_start - timedelta(days=today_start.weekday())
    this_week = await db.scalar(
        select(func.count()).where(
            and_(
                Notification.user_id == current_user.id,
                Notification.created_at >= week_start
            )
        )
    )
    
    # By type
    type_counts = {}
    for ntype in NotificationType:
        count = await db.scalar(
            select(func.count()).where(
                and_(
                    Notification.user_id == current_user.id,
                    Notification.notification_type == ntype
                )
            )
        )
        type_counts[ntype.value] = count or 0
    
    # By channel
    channel_counts = {}
    for channel in NotificationChannel:
        count = await db.scalar(
            select(func.count()).where(
                and_(
                    Notification.user_id == current_user.id,
                    Notification.channel == channel
                )
            )
        )
        channel_counts[channel.value] = count or 0
    
    # By status
    status_counts = {}
    for status in NotificationStatus:
        count = await db.scalar(
            select(func.count()).where(
                and_(
                    Notification.user_id == current_user.id,
                    Notification.status == status
                )
            )
        )
        status_counts[status.value] = count or 0
    
    return NotificationStatsResponse(
        total_notifications=total or 0,
        unread_count=unread or 0,
        notifications_today=today or 0,
        notifications_this_week=this_week or 0,
        by_type=type_counts,
        by_channel=channel_counts,
        by_status=status_counts
    )


# ============== ADMIN ENDPOINTS ==============

@router.post("/admin/send-bulk", tags=["Admin"])
async def send_bulk_notification(
    notification_data: BulkNotificationCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send notification to multiple users (admin only).
    """
    # Check admin role
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Create notifications for each user and channel
    created_count = 0
    for user_id in notification_data.user_ids:
        for channel in notification_data.channels:
            notification = Notification(
                user_id=user_id,
                notification_type=notification_data.notification_type,
                channel=channel,
                priority=notification_data.priority,
                title=notification_data.title,
                message=notification_data.message,
                data=notification_data.data,
                scheduled_at=notification_data.scheduled_at or datetime.utcnow()
            )
            db.add(notification)
            created_count += 1
    
    await db.commit()
    
    # Queue sending tasks
    from app.workers.tasks.notifications import send_notification
    # background_tasks.add_task(send_notification.delay, ...)
    
    return {
        "success": True,
        "created_count": created_count,
        "user_count": len(notification_data.user_ids),
        "channels": [c.value for c in notification_data.channels]
    }


@router.get("/admin/stats/global", tags=["Admin"])
async def get_global_notification_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get global notification statistics (admin only)."""
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Total notifications
    total = await db.scalar(select(func.count()).select_from(Notification))
    
    # Pending notifications
    pending = await db.scalar(
        select(func.count()).where(
            Notification.status == NotificationStatus.PENDING
        )
    )
    
    # Failed notifications
    failed = await db.scalar(
        select(func.count()).where(
            Notification.status == NotificationStatus.FAILED
        )
    )
    
    # Users with Telegram
    telegram_users = await db.scalar(
        select(func.count()).where(
            UserNotificationPreferences.telegram_verified == True
        )
    )
    
    # Notifications sent today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = await db.scalar(
        select(func.count()).where(
            and_(
                Notification.sent_at >= today_start,
                Notification.status == NotificationStatus.SENT
            )
        )
    )
    
    return {
        "total_notifications": total or 0,
        "pending": pending or 0,
        "failed": failed or 0,
        "telegram_users": telegram_users or 0,
        "sent_today": sent_today or 0
    }
