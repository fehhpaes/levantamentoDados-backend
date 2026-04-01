"""
Authentication API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from ..auth.models import (
    User, UserRole,
    UserCreate, UserUpdate, UserResponse, UserProfile,
    LoginRequest, TokenResponse,
    PasswordChangeRequest, PasswordResetRequest, PasswordResetConfirm
)
from ..auth.service import AuthService
from ..auth.dependencies import (
    get_current_user, get_current_active_user,
    require_admin, get_optional_user
)
from ..core.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    
    - **email**: Valid email address (unique)
    - **username**: Username (3-50 characters, unique)
    - **password**: Password (minimum 8 characters)
    - **full_name**: Optional full name
    """
    auth_service = AuthService(db)
    
    try:
        user, verification_token = await auth_service.register_user(user_data)
        
        # TODO: Send verification email
        # await send_verification_email(user.email, verification_token)
        
        return user
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login and get access token.
    
    - **email**: User email
    - **password**: User password
    - **remember_me**: Issue refresh token for persistent sessions
    """
    auth_service = AuthService(db)
    
    result = await auth_service.login(login_data)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return result


@router.post("/login/form", response_model=TokenResponse)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Login using OAuth2 password flow (for Swagger UI).
    """
    login_data = LoginRequest(
        email=form_data.username,  # OAuth2 uses 'username' field
        password=form_data.password,
        remember_me=False
    )
    
    auth_service = AuthService(db)
    result = await auth_service.login(login_data)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    """
    auth_service = AuthService(db)
    
    result = await auth_service.refresh_access_token(refresh_token)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    return result


@router.post("/logout")
async def logout(
    refresh_token: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout and revoke tokens.
    
    - **refresh_token**: Optional specific token to revoke (revokes all if not provided)
    """
    auth_service = AuthService(db)
    await auth_service.logout(current_user.id, refresh_token)
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user profile.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user profile.
    """
    auth_service = AuthService(db)
    
    user = await auth_service.update_user(current_user.id, update_data)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change current user's password.
    """
    auth_service = AuthService(db)
    
    success = await auth_service.change_password(
        current_user.id,
        password_data.current_password,
        password_data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset email.
    """
    auth_service = AuthService(db)
    
    token = await auth_service.request_password_reset(request.email)
    
    # Always return success to prevent email enumeration
    # TODO: Send reset email if token exists
    # if token:
    #     await send_password_reset_email(request.email, token)
    
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using token from email.
    """
    auth_service = AuthService(db)
    
    success = await auth_service.reset_password(request.token, request.new_password)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return {"message": "Password reset successfully"}


@router.post("/verify-email/{token}")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify email address using token.
    """
    auth_service = AuthService(db)
    
    success = await auth_service.verify_email(token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    return {"message": "Email verified successfully"}


@router.post("/regenerate-api-key")
async def regenerate_api_key(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Regenerate API key for current user.
    """
    auth_service = AuthService(db)
    
    new_key = await auth_service.regenerate_api_key(current_user.id)
    
    return {"api_key": new_key}


@router.get("/api-key")
async def get_api_key(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current API key.
    """
    return {
        "api_key": current_user.api_key,
        "requests_today": current_user.api_requests_today,
        "requests_limit": current_user.api_requests_limit
    }


# Admin endpoints
@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    List all users (admin only).
    """
    from sqlalchemy import select
    from ..auth.models import User
    
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role: UserRole,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user role (admin only).
    """
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.role = role
    await db.commit()
    
    return {"message": f"User role updated to {role.value}"}


@router.patch("/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    ban: bool = True,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Ban or unban a user (admin only).
    """
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot ban yourself"
        )
    
    user.is_banned = ban
    await db.commit()
    
    action = "banned" if ban else "unbanned"
    return {"message": f"User {action}"}
