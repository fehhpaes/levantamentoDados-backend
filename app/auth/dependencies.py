"""
FastAPI Authentication Dependencies
"""

from typing import Optional, List
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader

from .models import User, UserRole
from .jwt import verify_token
from .service import AuthService

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    api_key: str = Security(api_key_header)
) -> User:
    """
    Get current authenticated user.
    
    Supports both JWT tokens and API keys.
    
    Args:
        credentials: Bearer token credentials
        api_key: API key from header
        
    Returns:
        Authenticated User
        
    Raises:
        HTTPException: If authentication fails
    """
    auth_service = AuthService()
    
    # Try API key first
    if api_key:
        user = await auth_service.get_user_by_api_key(api_key)
        if user:
            # Check rate limit
            if not await auth_service.check_api_rate_limit(str(user.id)):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="API rate limit exceeded"
                )
            await auth_service.increment_api_usage(str(user.id))
            return user
    
    # Try JWT token
    if credentials:
        payload = verify_token(credentials.credentials)
        
        if payload:
            user_id = payload.get("sub")
            if user_id:
                user = await auth_service.get_user_by_id(user_id)
                if user and user.is_active:
                    return user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user.
    
    Args:
        current_user: Authenticated user
        
    Returns:
        Active User
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    if current_user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is banned"
        )
    
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current verified user.
    
    Args:
        current_user: Active user
        
    Returns:
        Verified User
        
    Raises:
        HTTPException: If user is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )
    
    return current_user


def require_role(allowed_roles: List[UserRole]):
    """
    Dependency factory to require specific roles.
    
    Args:
        allowed_roles: List of allowed roles
        
    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    
    return role_checker


def require_subscription(allowed_plans: List[str]):
    """
    Dependency factory to require specific subscription plans.
    
    Args:
        allowed_plans: List of allowed subscription plans
        
    Returns:
        Dependency function
    """
    from .models import SubscriptionPlan
    from datetime import datetime
    
    async def subscription_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        # Check if subscription is valid
        if current_user.subscription_plan.value not in allowed_plans:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription plan does not allow this feature"
            )
        
        # Check if subscription has expired
        if current_user.subscription_expires_at:
            if current_user.subscription_expires_at < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Subscription has expired"
                )
        
        return current_user
    
    return subscription_checker


# Pre-defined role dependencies
require_admin = require_role([UserRole.ADMIN])
require_moderator = require_role([UserRole.ADMIN, UserRole.MODERATOR])
require_premium = require_role([UserRole.ADMIN, UserRole.MODERATOR, UserRole.PREMIUM])


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    api_key: str = Security(api_key_header)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    
    For endpoints that work differently for authenticated users.
    """
    try:
        return await get_current_user(credentials, api_key)
    except HTTPException:
        return None
