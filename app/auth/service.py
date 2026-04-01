"""
Authentication Service
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
import logging

from .models import (
    User, UserRole, SubscriptionPlan,
    RefreshToken, PasswordReset, EmailVerification,
    UserCreate, UserUpdate, UserResponse, UserProfile,
    LoginRequest, TokenResponse
)
from .jwt import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, verify_token,
    generate_api_key, generate_verification_token, generate_password_reset_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
)

logger = logging.getLogger(__name__)


class AuthService:
    """
    Authentication and user management service.
    
    Features:
    - User registration and login
    - JWT token management
    - Password reset
    - Email verification
    - Role-based access control
    - API key management
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize auth service with database session."""
        self.db = db
    
    async def register_user(
        self,
        user_data: UserCreate,
        role: UserRole = UserRole.USER
    ) -> Tuple[User, str]:
        """
        Register a new user.
        
        Args:
            user_data: User registration data
            role: User role (default: USER)
            
        Returns:
            Tuple of (User, verification_token)
        """
        # Check if email exists
        existing = await self.get_user_by_email(user_data.email)
        if existing:
            raise ValueError("Email already registered")
        
        # Check if username exists
        existing = await self.get_user_by_username(user_data.username)
        if existing:
            raise ValueError("Username already taken")
        
        # Create user
        user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=role,
            api_key=generate_api_key()
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        # Create verification token
        verification_token = generate_verification_token()
        verification = EmailVerification(
            user_id=user.id,
            token=verification_token,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        self.db.add(verification)
        await self.db.commit()
        
        logger.info(f"User registered: {user.email}")
        return user, verification_token
    
    async def authenticate_user(
        self,
        login_data: LoginRequest
    ) -> Optional[User]:
        """
        Authenticate a user.
        
        Args:
            login_data: Login credentials
            
        Returns:
            User if authentication successful, None otherwise
        """
        user = await self.get_user_by_email(login_data.email)
        
        if not user:
            return None
        
        if not verify_password(login_data.password, user.hashed_password):
            return None
        
        if not user.is_active:
            return None
        
        if user.is_banned:
            return None
        
        # Update last login
        user.last_login_at = datetime.utcnow()
        await self.db.commit()
        
        return user
    
    async def login(
        self,
        login_data: LoginRequest
    ) -> Optional[TokenResponse]:
        """
        Login user and generate tokens.
        
        Args:
            login_data: Login credentials
            
        Returns:
            TokenResponse with access and refresh tokens
        """
        user = await self.authenticate_user(login_data)
        
        if not user:
            return None
        
        # Create tokens
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value
            }
        )
        
        refresh_token = None
        if login_data.remember_me:
            refresh_token = create_refresh_token(
                data={"sub": str(user.id)}
            )
            
            # Store refresh token
            token_record = RefreshToken(
                user_id=user.id,
                token=refresh_token,
                expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            )
            self.db.add(token_record)
            await self.db.commit()
        
        logger.info(f"User logged in: {user.email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    async def refresh_access_token(
        self,
        refresh_token: str
    ) -> Optional[TokenResponse]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New TokenResponse
        """
        payload = verify_token(refresh_token, token_type="refresh")
        
        if not payload:
            return None
        
        user_id = payload.get("sub")
        
        # Verify token exists in database
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token == refresh_token,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.utcnow()
            )
        )
        token_record = result.scalar_one_or_none()
        
        if not token_record:
            return None
        
        # Get user
        user = await self.get_user_by_id(int(user_id))
        
        if not user or not user.is_active:
            return None
        
        # Create new access token
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value
            }
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    async def logout(
        self,
        user_id: int,
        refresh_token: Optional[str] = None
    ) -> None:
        """
        Logout user by revoking refresh tokens.
        
        Args:
            user_id: User ID
            refresh_token: Specific token to revoke (None for all)
        """
        if refresh_token:
            await self.db.execute(
                update(RefreshToken)
                .where(RefreshToken.token == refresh_token)
                .values(revoked_at=datetime.utcnow())
            )
        else:
            # Revoke all user tokens
            await self.db.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None)
                )
                .values(revoked_at=datetime.utcnow())
            )
        
        await self.db.commit()
        logger.info(f"User logged out: {user_id}")
    
    async def verify_email(self, token: str) -> bool:
        """
        Verify user email with token.
        
        Args:
            token: Verification token
            
        Returns:
            True if verification successful
        """
        result = await self.db.execute(
            select(EmailVerification).where(
                EmailVerification.token == token,
                EmailVerification.expires_at > datetime.utcnow()
            )
        )
        verification = result.scalar_one_or_none()
        
        if not verification:
            return False
        
        # Update user
        await self.db.execute(
            update(User)
            .where(User.id == verification.user_id)
            .values(is_verified=True)
        )
        
        # Delete verification token
        await self.db.delete(verification)
        await self.db.commit()
        
        logger.info(f"Email verified for user: {verification.user_id}")
        return True
    
    async def request_password_reset(
        self,
        email: str
    ) -> Optional[str]:
        """
        Request password reset.
        
        Args:
            email: User email
            
        Returns:
            Reset token if user exists
        """
        user = await self.get_user_by_email(email)
        
        if not user:
            return None
        
        # Delete existing reset requests
        await self.db.execute(
            delete(PasswordReset).where(PasswordReset.user_id == user.id)
        )
        
        # Create reset token
        token = generate_password_reset_token()
        reset = PasswordReset(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        self.db.add(reset)
        await self.db.commit()
        
        logger.info(f"Password reset requested: {email}")
        return token
    
    async def reset_password(
        self,
        token: str,
        new_password: str
    ) -> bool:
        """
        Reset password with token.
        
        Args:
            token: Reset token
            new_password: New password
            
        Returns:
            True if reset successful
        """
        result = await self.db.execute(
            select(PasswordReset).where(
                PasswordReset.token == token,
                PasswordReset.expires_at > datetime.utcnow(),
                PasswordReset.used_at.is_(None)
            )
        )
        reset = result.scalar_one_or_none()
        
        if not reset:
            return False
        
        # Update password
        await self.db.execute(
            update(User)
            .where(User.id == reset.user_id)
            .values(hashed_password=get_password_hash(new_password))
        )
        
        # Mark token as used
        reset.used_at = datetime.utcnow()
        
        # Revoke all refresh tokens
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == reset.user_id)
            .values(revoked_at=datetime.utcnow())
        )
        
        await self.db.commit()
        
        logger.info(f"Password reset completed for user: {reset.user_id}")
        return True
    
    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Change user password.
        
        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            
        Returns:
            True if change successful
        """
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return False
        
        if not verify_password(current_password, user.hashed_password):
            return False
        
        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        
        logger.info(f"Password changed for user: {user_id}")
        return True
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """Get user by API key."""
        result = await self.db.execute(
            select(User).where(
                User.api_key == api_key,
                User.is_active == True
            )
        )
        return result.scalar_one_or_none()
    
    async def update_user(
        self,
        user_id: int,
        update_data: UserUpdate
    ) -> Optional[User]:
        """Update user profile."""
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            setattr(user, field, value)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def regenerate_api_key(self, user_id: int) -> Optional[str]:
        """Regenerate user API key."""
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return None
        
        new_key = generate_api_key()
        user.api_key = new_key
        await self.db.commit()
        
        logger.info(f"API key regenerated for user: {user_id}")
        return new_key
    
    async def update_subscription(
        self,
        user_id: int,
        plan: SubscriptionPlan,
        expires_at: datetime
    ) -> bool:
        """Update user subscription."""
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return False
        
        user.subscription_plan = plan
        user.subscription_expires_at = expires_at
        
        # Update API limits based on plan
        limits = {
            SubscriptionPlan.FREE: 100,
            SubscriptionPlan.BASIC: 1000,
            SubscriptionPlan.PRO: 10000,
            SubscriptionPlan.ENTERPRISE: 100000
        }
        user.api_requests_limit = limits.get(plan, 100)
        
        await self.db.commit()
        
        logger.info(f"Subscription updated for user {user_id}: {plan.value}")
        return True
    
    async def check_api_rate_limit(self, user_id: int) -> bool:
        """Check if user has exceeded API rate limit."""
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return False
        
        return user.api_requests_today < user.api_requests_limit
    
    async def increment_api_usage(self, user_id: int) -> None:
        """Increment API usage counter."""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(api_requests_today=User.api_requests_today + 1)
        )
        await self.db.commit()
    
    async def reset_daily_api_usage(self) -> int:
        """Reset daily API usage for all users. Called by scheduler."""
        result = await self.db.execute(
            update(User).values(api_requests_today=0)
        )
        await self.db.commit()
        
        logger.info("Daily API usage reset for all users")
        return result.rowcount
