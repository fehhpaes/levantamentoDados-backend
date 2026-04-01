"""
User and Authentication Models - MongoDB/Beanie Version
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from beanie import Document, Indexed
import uuid


class UserRole(str, Enum):
    """User roles for authorization."""
    ADMIN = "admin"
    MODERATOR = "moderator"
    PREMIUM = "premium"
    USER = "user"
    GUEST = "guest"


class SubscriptionPlan(str, Enum):
    """Subscription plans."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# Beanie Document Models (for MongoDB)

class User(Document):
    """User database model."""
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: Indexed(str, unique=True)
    username: Indexed(str, unique=True)
    hashed_password: str
    
    # Profile
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"
    
    # Role and subscription
    role: UserRole = UserRole.USER
    subscription_plan: SubscriptionPlan = SubscriptionPlan.FREE
    subscription_expires_at: Optional[datetime] = None
    
    # Status
    is_active: bool = True
    is_verified: bool = False
    is_banned: bool = False
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None
    
    # API access
    api_key: Optional[Indexed(str, unique=True)] = None
    api_requests_today: int = 0
    api_requests_limit: int = 100
    
    # Favorites (list of team IDs)
    favorite_team_ids: List[str] = []
    
    class Settings:
        name = "users"


class RefreshToken(Document):
    """Refresh token for JWT authentication."""
    user_id: Indexed(str)
    token: Indexed(str, unique=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    revoked_at: Optional[datetime] = None
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    
    class Settings:
        name = "refresh_tokens"


class PasswordReset(Document):
    """Password reset request."""
    user_id: Indexed(str)
    token: Indexed(str, unique=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    used_at: Optional[datetime] = None
    
    class Settings:
        name = "password_resets"


class EmailVerification(Document):
    """Email verification token."""
    user_id: Indexed(str)
    token: Indexed(str, unique=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "email_verifications"


# Pydantic Schemas (for API)

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    full_name: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: str
    uuid: str
    role: UserRole
    subscription_plan: SubscriptionPlan
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    """Extended user profile."""
    timezone: str
    language: str
    avatar_url: Optional[str]
    api_requests_today: int
    api_requests_limit: int
    subscription_expires_at: Optional[datetime]


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8)
