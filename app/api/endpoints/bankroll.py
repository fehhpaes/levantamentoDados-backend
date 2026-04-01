"""
Bankroll Management API Endpoints.

Provides endpoints for managing betting bankroll, tracking bets,
and getting stake recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from app.core.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.services.bankroll import BankrollManager, KellyCriterion


router = APIRouter()


# ========================
# Schemas
# ========================

class StakingMethod(str, Enum):
    fixed_percentage = "fixed_percentage"
    kelly_criterion = "kelly_criterion"
    half_kelly = "half_kelly"
    quarter_kelly = "quarter_kelly"
    fixed_amount = "fixed_amount"
    unit_based = "unit_based"


class BetStatus(str, Enum):
    pending = "pending"
    won = "won"
    lost = "lost"
    void = "void"
    half_won = "half_won"
    half_lost = "half_lost"


class BankrollCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    initial_balance: float = Field(..., ge=0)
    currency: str = Field(default="BRL", max_length=3)
    staking_method: StakingMethod = StakingMethod.fixed_percentage
    default_stake_percentage: float = Field(default=2.0, ge=0.1, le=100)
    max_stake_percentage: float = Field(default=10.0, ge=1, le=100)
    kelly_fraction: float = Field(default=0.25, ge=0.1, le=1.0)
    stop_loss_percentage: Optional[float] = Field(default=20.0, ge=1, le=100)
    take_profit_percentage: Optional[float] = Field(default=50.0, ge=1, le=500)


class BankrollResponse(BaseModel):
    id: int
    user_id: int
    name: str
    initial_balance: float
    current_balance: float
    currency: str
    staking_method: StakingMethod
    total_bets: int
    winning_bets: int
    losing_bets: int
    profit_loss: float
    roi_percentage: float
    max_drawdown: float
    created_at: datetime
    updated_at: datetime


class BetCreate(BaseModel):
    bankroll_id: int
    match_id: Optional[int] = None
    match_description: str
    market: str
    selection: str
    odds: float = Field(..., ge=1.01)
    stake: Optional[float] = Field(default=None, ge=0.01)
    predicted_probability: Optional[float] = Field(default=None, ge=0, le=1)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    notes: Optional[str] = None


class BetResponse(BaseModel):
    id: int
    bankroll_id: int
    match_id: Optional[int]
    match_description: str
    market: str
    selection: str
    odds: float
    stake: float
    potential_return: float
    predicted_probability: Optional[float]
    edge: Optional[float]
    status: BetStatus
    result_odds: Optional[float]
    profit_loss: Optional[float]
    placed_at: datetime
    settled_at: Optional[datetime]


class BetSettle(BaseModel):
    status: BetStatus
    result_odds: Optional[float] = None
    notes: Optional[str] = None


class StakeRecommendation(BaseModel):
    recommended_stake: float
    stake_percentage: float
    method_used: str
    edge: float
    kelly_stake: float
    max_allowed_stake: float
    risk_level: str
    expected_value: float
    reasoning: str


class BankrollStats(BaseModel):
    total_bankrolls: int
    total_balance: float
    total_profit_loss: float
    overall_roi: float
    total_bets: int
    win_rate: float
    best_performing_bankroll: Optional[str]
    worst_performing_bankroll: Optional[str]


class DailyPnL(BaseModel):
    date: str
    bets: int
    wins: int
    losses: int
    profit_loss: float
    balance: float


# ========================
# Endpoints
# ========================

@router.post("/", response_model=BankrollResponse, status_code=201)
async def create_bankroll(
    bankroll: BankrollCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new bankroll for tracking bets."""
    # In production, save to database
    return BankrollResponse(
        id=1,
        user_id=current_user.id,
        name=bankroll.name,
        initial_balance=bankroll.initial_balance,
        current_balance=bankroll.initial_balance,
        currency=bankroll.currency,
        staking_method=bankroll.staking_method,
        total_bets=0,
        winning_bets=0,
        losing_bets=0,
        profit_loss=0.0,
        roi_percentage=0.0,
        max_drawdown=0.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.get("/", response_model=List[BankrollResponse])
async def list_bankrolls(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all bankrolls for the current user."""
    # In production, fetch from database
    return [
        BankrollResponse(
            id=1,
            user_id=current_user.id,
            name="Main Bankroll",
            initial_balance=1000.0,
            current_balance=1250.0,
            currency="BRL",
            staking_method=StakingMethod.kelly_criterion,
            total_bets=50,
            winning_bets=28,
            losing_bets=20,
            profit_loss=250.0,
            roi_percentage=25.0,
            max_drawdown=150.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        BankrollResponse(
            id=2,
            user_id=current_user.id,
            name="Value Bets Only",
            initial_balance=500.0,
            current_balance=620.0,
            currency="BRL",
            staking_method=StakingMethod.fixed_percentage,
            total_bets=25,
            winning_bets=15,
            losing_bets=10,
            profit_loss=120.0,
            roi_percentage=24.0,
            max_drawdown=80.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]


@router.get("/{bankroll_id}", response_model=BankrollResponse)
async def get_bankroll(
    bankroll_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details of a specific bankroll."""
    # In production, fetch from database
    return BankrollResponse(
        id=bankroll_id,
        user_id=current_user.id,
        name="Main Bankroll",
        initial_balance=1000.0,
        current_balance=1250.0,
        currency="BRL",
        staking_method=StakingMethod.kelly_criterion,
        total_bets=50,
        winning_bets=28,
        losing_bets=20,
        profit_loss=250.0,
        roi_percentage=25.0,
        max_drawdown=150.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.delete("/{bankroll_id}", status_code=204)
async def delete_bankroll(
    bankroll_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a bankroll (must have no pending bets)."""
    # In production, delete from database
    return None


@router.post("/{bankroll_id}/bets", response_model=BetResponse, status_code=201)
async def place_bet(
    bankroll_id: int,
    bet: BetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a new bet in the bankroll."""
    # Calculate stake if not provided
    stake = bet.stake or 20.0  # Default stake
    
    # Calculate edge if probability provided
    edge = None
    if bet.predicted_probability and bet.odds:
        implied_prob = 1 / bet.odds
        edge = (bet.predicted_probability - implied_prob) * 100
    
    return BetResponse(
        id=1,
        bankroll_id=bankroll_id,
        match_id=bet.match_id,
        match_description=bet.match_description,
        market=bet.market,
        selection=bet.selection,
        odds=bet.odds,
        stake=stake,
        potential_return=stake * bet.odds,
        predicted_probability=bet.predicted_probability,
        edge=edge,
        status=BetStatus.pending,
        result_odds=None,
        profit_loss=None,
        placed_at=datetime.utcnow(),
        settled_at=None,
    )


@router.get("/{bankroll_id}/bets", response_model=List[BetResponse])
async def list_bets(
    bankroll_id: int,
    status: Optional[BetStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List bets for a bankroll with optional filters."""
    # In production, fetch from database with filters
    return [
        BetResponse(
            id=1,
            bankroll_id=bankroll_id,
            match_id=101,
            match_description="Flamengo vs Palmeiras",
            market="1X2",
            selection="Home Win",
            odds=2.10,
            stake=25.0,
            potential_return=52.50,
            predicted_probability=0.55,
            edge=10.5,
            status=BetStatus.won,
            result_odds=2.10,
            profit_loss=27.50,
            placed_at=datetime.utcnow(),
            settled_at=datetime.utcnow(),
        ),
        BetResponse(
            id=2,
            bankroll_id=bankroll_id,
            match_id=102,
            match_description="Corinthians vs São Paulo",
            market="Over/Under",
            selection="Over 2.5",
            odds=1.85,
            stake=30.0,
            potential_return=55.50,
            predicted_probability=0.60,
            edge=8.9,
            status=BetStatus.pending,
            result_odds=None,
            profit_loss=None,
            placed_at=datetime.utcnow(),
            settled_at=None,
        ),
    ]


@router.patch("/{bankroll_id}/bets/{bet_id}", response_model=BetResponse)
async def settle_bet(
    bankroll_id: int,
    bet_id: int,
    settlement: BetSettle,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Settle a pending bet with the result."""
    # Calculate profit/loss based on status
    stake = 25.0  # Would come from database
    odds = 2.10  # Would come from database
    
    profit_loss = 0.0
    if settlement.status == BetStatus.won:
        profit_loss = stake * (odds - 1)
    elif settlement.status == BetStatus.lost:
        profit_loss = -stake
    elif settlement.status == BetStatus.half_won:
        profit_loss = stake * (odds - 1) / 2
    elif settlement.status == BetStatus.half_lost:
        profit_loss = -stake / 2
    
    return BetResponse(
        id=bet_id,
        bankroll_id=bankroll_id,
        match_id=101,
        match_description="Flamengo vs Palmeiras",
        market="1X2",
        selection="Home Win",
        odds=odds,
        stake=stake,
        potential_return=stake * odds,
        predicted_probability=0.55,
        edge=10.5,
        status=settlement.status,
        result_odds=settlement.result_odds,
        profit_loss=profit_loss,
        placed_at=datetime.utcnow(),
        settled_at=datetime.utcnow(),
    )


@router.post("/stake-recommendation", response_model=StakeRecommendation)
async def get_stake_recommendation(
    bankroll_id: int,
    odds: float = Query(..., ge=1.01),
    predicted_probability: float = Query(..., ge=0, le=1),
    confidence: float = Query(0.7, ge=0, le=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get stake recommendation based on bankroll settings and bet parameters.
    
    Uses Kelly Criterion and confidence to determine optimal stake size.
    """
    # Get bankroll settings (mock for now)
    current_balance = 1000.0
    staking_method = StakingMethod.kelly_criterion
    kelly_fraction = 0.25
    max_stake_percentage = 10.0
    
    # Calculate edge
    implied_prob = 1 / odds
    edge = predicted_probability - implied_prob
    edge_percentage = edge * 100
    
    # Kelly calculation
    kelly = KellyCriterion()
    kelly_stake_pct = kelly.calculate(
        probability=predicted_probability,
        odds=odds,
    )
    
    # Apply fraction and confidence
    adjusted_kelly = kelly_stake_pct * kelly_fraction * confidence
    
    # Cap at max stake
    final_stake_pct = min(adjusted_kelly, max_stake_percentage)
    recommended_stake = current_balance * (final_stake_pct / 100)
    
    # Determine risk level
    if final_stake_pct <= 2:
        risk_level = "low"
    elif final_stake_pct <= 5:
        risk_level = "medium"
    else:
        risk_level = "high"
    
    # Expected value
    ev = (predicted_probability * (odds - 1)) - ((1 - predicted_probability) * 1)
    
    return StakeRecommendation(
        recommended_stake=round(recommended_stake, 2),
        stake_percentage=round(final_stake_pct, 2),
        method_used=staking_method.value,
        edge=round(edge_percentage, 2),
        kelly_stake=round(kelly_stake_pct, 2),
        max_allowed_stake=current_balance * (max_stake_percentage / 100),
        risk_level=risk_level,
        expected_value=round(ev * 100, 2),
        reasoning=f"Based on {edge_percentage:.1f}% edge and {confidence*100:.0f}% confidence, "
                  f"fractional Kelly ({kelly_fraction}) suggests {final_stake_pct:.1f}% stake.",
    )


@router.get("/stats", response_model=BankrollStats)
async def get_overall_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get overall statistics across all bankrolls."""
    return BankrollStats(
        total_bankrolls=2,
        total_balance=1870.0,
        total_profit_loss=370.0,
        overall_roi=24.7,
        total_bets=75,
        win_rate=0.573,
        best_performing_bankroll="Main Bankroll",
        worst_performing_bankroll=None,
    )


@router.get("/{bankroll_id}/daily-pnl", response_model=List[DailyPnL])
async def get_daily_pnl(
    bankroll_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily profit/loss breakdown for a bankroll."""
    # Mock data
    return [
        DailyPnL(
            date="2024-01-15",
            bets=3,
            wins=2,
            losses=1,
            profit_loss=45.0,
            balance=1045.0,
        ),
        DailyPnL(
            date="2024-01-16",
            bets=2,
            wins=1,
            losses=1,
            profit_loss=-10.0,
            balance=1035.0,
        ),
        DailyPnL(
            date="2024-01-17",
            bets=4,
            wins=3,
            losses=1,
            profit_loss=85.0,
            balance=1120.0,
        ),
    ]


@router.post("/{bankroll_id}/deposit")
async def deposit(
    bankroll_id: int,
    amount: float = Query(..., gt=0),
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add funds to a bankroll."""
    return {
        "bankroll_id": bankroll_id,
        "transaction_type": "deposit",
        "amount": amount,
        "new_balance": 1250.0 + amount,
        "notes": notes,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/{bankroll_id}/withdraw")
async def withdraw(
    bankroll_id: int,
    amount: float = Query(..., gt=0),
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Withdraw funds from a bankroll."""
    current_balance = 1250.0  # Would come from database
    
    if amount > current_balance:
        raise HTTPException(
            status_code=400,
            detail="Insufficient balance for withdrawal"
        )
    
    return {
        "bankroll_id": bankroll_id,
        "transaction_type": "withdraw",
        "amount": amount,
        "new_balance": current_balance - amount,
        "notes": notes,
        "timestamp": datetime.utcnow().isoformat(),
    }
