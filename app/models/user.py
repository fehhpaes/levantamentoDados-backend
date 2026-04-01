from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List
from datetime import datetime
from .base import BaseDocument


class User(BaseDocument):
    """User model."""
    email: Indexed(str, unique=True)
    username: Indexed(str, unique=True)
    hashed_password: str
    
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    
    # Preferences
    timezone: str = "America/Sao_Paulo"
    language: str = "pt"
    
    # Last login
    last_login_at: Optional[datetime] = None
    
    class Settings:
        name = "users"


class BankrollState(BaseDocument):
    """User bankroll state."""
    user_id: Indexed(str, unique=True)
    
    initial_balance: float = 0.0
    current_balance: float = 0.0
    total_deposited: float = 0.0
    total_withdrawn: float = 0.0
    total_wagered: float = 0.0
    total_profit: float = 0.0
    roi: float = 0.0
    
    # Settings
    staking_method: str = "fixed"  # fixed, percentage, kelly
    fixed_stake: Optional[float] = None
    percentage_stake: Optional[float] = None
    kelly_fraction: Optional[float] = None
    max_stake_percentage: float = 10.0
    stop_loss_percentage: Optional[float] = None
    take_profit_percentage: Optional[float] = None
    
    class Settings:
        name = "bankroll_states"


class BankrollTransaction(BaseDocument):
    """Bankroll transaction record."""
    user_id: Indexed(str)
    bankroll_id: str
    
    type: str  # deposit, withdrawal, bet, win, loss, refund
    amount: float
    balance_after: float
    
    description: Optional[str] = None
    match_id: Optional[str] = None
    bet_id: Optional[str] = None
    
    class Settings:
        name = "bankroll_transactions"
