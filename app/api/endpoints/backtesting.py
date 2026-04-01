"""
Backtesting API Endpoints.

Provides endpoints for backtesting betting strategies against historical data.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date
from enum import Enum

from app.core.database import get_db
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User, UserRole
from app.services.backtesting import (
    BacktestingEngine,
    BettingStrategy,
    BacktestResult,
)


router = APIRouter()


# ========================
# Schemas
# ========================

class StrategyType(str, Enum):
    value_betting = "value_betting"
    kelly_criterion = "kelly_criterion"
    fixed_stake = "fixed_stake"
    martingale = "martingale"
    fibonacci = "fibonacci"
    dutching = "dutching"
    arbitrage = "arbitrage"


class MarketFilter(str, Enum):
    all = "all"
    match_winner = "1x2"
    over_under = "over_under"
    btts = "btts"
    asian_handicap = "asian_handicap"
    correct_score = "correct_score"


class BacktestRequest(BaseModel):
    strategy: StrategyType
    start_date: date
    end_date: date
    initial_bankroll: float = Field(default=1000.0, ge=100)
    markets: List[MarketFilter] = Field(default=[MarketFilter.all])
    min_odds: float = Field(default=1.5, ge=1.01)
    max_odds: float = Field(default=5.0, le=100.0)
    min_edge: float = Field(default=5.0, description="Minimum value edge %")
    min_confidence: float = Field(default=0.6, ge=0, le=1)
    leagues: Optional[List[int]] = None
    sports: Optional[List[str]] = None
    stake_percentage: float = Field(default=2.0, ge=0.1, le=100)
    max_stake_percentage: float = Field(default=10.0, ge=1, le=100)
    kelly_fraction: float = Field(default=0.25, ge=0.1, le=1.0)


class StrategyMetrics(BaseModel):
    total_bets: int
    winning_bets: int
    losing_bets: int
    void_bets: int
    win_rate: float
    average_odds: float
    total_stake: float
    total_returns: float
    profit_loss: float
    roi_percentage: float
    max_drawdown: float
    max_drawdown_percentage: float
    sharpe_ratio: float
    sortino_ratio: float
    longest_winning_streak: int
    longest_losing_streak: int
    average_win: float
    average_loss: float
    profit_factor: float


class MonthlyBreakdown(BaseModel):
    month: str
    bets: int
    wins: int
    profit_loss: float
    roi: float
    bankroll_end: float


class BetDetail(BaseModel):
    date: datetime
    match: str
    league: str
    market: str
    selection: str
    odds: float
    stake: float
    predicted_prob: float
    edge: float
    result: str
    profit_loss: float
    bankroll_after: float


class BacktestResponse(BaseModel):
    strategy: str
    period: str
    metrics: StrategyMetrics
    monthly_breakdown: List[MonthlyBreakdown]
    equity_curve: List[Dict[str, Any]]
    bet_distribution: Dict[str, int]
    top_performing_leagues: List[Dict[str, Any]]
    worst_performing_leagues: List[Dict[str, Any]]
    sample_bets: List[BetDetail]


class StrategyComparisonRequest(BaseModel):
    strategies: List[StrategyType]
    start_date: date
    end_date: date
    initial_bankroll: float = 1000.0
    common_filters: Dict[str, Any] = {}


class StrategyComparisonResponse(BaseModel):
    period: str
    comparison: Dict[str, StrategyMetrics]
    best_strategy: str
    equity_curves: Dict[str, List[Dict[str, Any]]]


# ========================
# Endpoints
# ========================

@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run a backtest with specified strategy and parameters.
    
    Analyzes historical betting performance using the specified strategy
    and returns detailed metrics, equity curves, and bet-by-bet breakdown.
    """
    # Initialize backtesting engine
    engine = BacktestingEngine(
        initial_bankroll=request.initial_bankroll,
        start_date=datetime.combine(request.start_date, datetime.min.time()),
        end_date=datetime.combine(request.end_date, datetime.max.time()),
    )
    
    # Configure strategy
    strategy = BettingStrategy(
        name=request.strategy.value,
        min_odds=request.min_odds,
        max_odds=request.max_odds,
        min_edge=request.min_edge,
        min_confidence=request.min_confidence,
        stake_percentage=request.stake_percentage,
        max_stake_percentage=request.max_stake_percentage,
        kelly_fraction=request.kelly_fraction if request.strategy == StrategyType.kelly_criterion else None,
    )
    
    engine.set_strategy(strategy)
    
    # In production, fetch historical predictions and results from database
    # For now, generate mock backtest results
    
    # Generate mock metrics
    metrics = StrategyMetrics(
        total_bets=250,
        winning_bets=140,
        losing_bets=105,
        void_bets=5,
        win_rate=0.56,
        average_odds=2.15,
        total_stake=12500.0,
        total_returns=14875.0,
        profit_loss=2375.0,
        roi_percentage=19.0,
        max_drawdown=450.0,
        max_drawdown_percentage=8.5,
        sharpe_ratio=1.85,
        sortino_ratio=2.12,
        longest_winning_streak=8,
        longest_losing_streak=5,
        average_win=85.0,
        average_loss=72.0,
        profit_factor=1.42,
    )
    
    # Monthly breakdown
    monthly_breakdown = [
        MonthlyBreakdown(
            month=f"{request.start_date.year}-{m:02d}",
            bets=20 + (m % 5),
            wins=12 + (m % 3),
            profit_loss=180 + (m * 25),
            roi=14.0 + (m % 8),
            bankroll_end=1000 + (m * 200),
        )
        for m in range(1, 7)
    ]
    
    # Equity curve (daily snapshots)
    equity_curve = []
    bankroll = request.initial_bankroll
    import random
    random.seed(42)
    
    current = request.start_date
    while current <= request.end_date:
        change = random.uniform(-50, 80)
        bankroll = max(bankroll + change, 100)
        equity_curve.append({
            "date": current.isoformat(),
            "bankroll": round(bankroll, 2),
            "daily_pnl": round(change, 2),
        })
        current = date(current.year, current.month, min(current.day + 1, 28))
        if current.day == 28:
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)
    
    # Sample bets
    sample_bets = [
        BetDetail(
            date=datetime.now(),
            match="Team A vs Team B",
            league="Premier League",
            market="1X2",
            selection="Home Win",
            odds=2.10,
            stake=50.0,
            predicted_prob=0.55,
            edge=10.5,
            result="won",
            profit_loss=55.0,
            bankroll_after=1055.0,
        ),
        BetDetail(
            date=datetime.now(),
            match="Team C vs Team D",
            league="La Liga",
            market="Over/Under",
            selection="Over 2.5",
            odds=1.90,
            stake=45.0,
            predicted_prob=0.58,
            edge=8.2,
            result="lost",
            profit_loss=-45.0,
            bankroll_after=1010.0,
        ),
    ]
    
    return BacktestResponse(
        strategy=request.strategy.value,
        period=f"{request.start_date} to {request.end_date}",
        metrics=metrics,
        monthly_breakdown=monthly_breakdown,
        equity_curve=equity_curve[:100],  # Limit to 100 points
        bet_distribution={
            "1X2": 120,
            "Over/Under": 80,
            "BTTS": 35,
            "Asian Handicap": 15,
        },
        top_performing_leagues=[
            {"league": "Premier League", "roi": 25.5, "bets": 45},
            {"league": "Bundesliga", "roi": 22.3, "bets": 38},
        ],
        worst_performing_leagues=[
            {"league": "Ligue 1", "roi": -5.2, "bets": 22},
            {"league": "Serie A", "roi": -2.1, "bets": 28},
        ],
        sample_bets=sample_bets,
    )


@router.post("/compare", response_model=StrategyComparisonResponse)
async def compare_strategies(
    request: StrategyComparisonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare multiple betting strategies over the same period."""
    comparison = {}
    equity_curves = {}
    
    for strategy in request.strategies:
        # Run backtest for each strategy
        metrics = StrategyMetrics(
            total_bets=200,
            winning_bets=int(200 * (0.5 + 0.05 * len(strategy.value))),
            losing_bets=200 - int(200 * (0.5 + 0.05 * len(strategy.value))),
            void_bets=0,
            win_rate=0.5 + 0.05 * (len(strategy.value) % 3),
            average_odds=2.0,
            total_stake=10000.0,
            total_returns=10000 * (1 + 0.1 * (len(strategy.value) % 4)),
            profit_loss=1000 * (len(strategy.value) % 4),
            roi_percentage=10.0 * (len(strategy.value) % 4),
            max_drawdown=300.0,
            max_drawdown_percentage=6.0,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            longest_winning_streak=6,
            longest_losing_streak=4,
            average_win=80.0,
            average_loss=65.0,
            profit_factor=1.3,
        )
        comparison[strategy.value] = metrics
        
        # Mock equity curve
        equity_curves[strategy.value] = [
            {"date": f"2024-{m:02d}-01", "bankroll": 1000 + m * 100}
            for m in range(1, 7)
        ]
    
    # Find best strategy by ROI
    best = max(comparison.items(), key=lambda x: x[1].roi_percentage)
    
    return StrategyComparisonResponse(
        period=f"{request.start_date} to {request.end_date}",
        comparison=comparison,
        best_strategy=best[0],
        equity_curves=equity_curves,
    )


@router.get("/strategies")
async def list_strategies():
    """List all available betting strategies with descriptions."""
    return [
        {
            "name": "value_betting",
            "display_name": "Value Betting",
            "description": "Bet when predicted probability exceeds implied odds probability by minimum edge",
            "parameters": ["min_edge", "min_confidence", "stake_percentage"],
            "risk_level": "medium",
        },
        {
            "name": "kelly_criterion",
            "display_name": "Kelly Criterion",
            "description": "Optimal stake sizing based on edge and odds to maximize long-term growth",
            "parameters": ["kelly_fraction", "min_edge"],
            "risk_level": "medium-high",
        },
        {
            "name": "fixed_stake",
            "display_name": "Fixed Stake",
            "description": "Bet a fixed percentage of initial bankroll on every bet",
            "parameters": ["stake_percentage"],
            "risk_level": "low",
        },
        {
            "name": "martingale",
            "display_name": "Martingale",
            "description": "Double stake after each loss to recover losses (high risk)",
            "parameters": ["initial_stake", "max_stake_percentage"],
            "risk_level": "very-high",
        },
        {
            "name": "fibonacci",
            "display_name": "Fibonacci",
            "description": "Increase stake following Fibonacci sequence after losses",
            "parameters": ["base_stake"],
            "risk_level": "high",
        },
        {
            "name": "dutching",
            "display_name": "Dutching",
            "description": "Spread stake across multiple selections to guarantee profit",
            "parameters": ["target_profit"],
            "risk_level": "low",
        },
        {
            "name": "arbitrage",
            "display_name": "Arbitrage",
            "description": "Exploit odds differences between bookmakers for guaranteed profit",
            "parameters": ["min_profit_percentage"],
            "risk_level": "very-low",
        },
    ]


@router.get("/history")
async def get_backtest_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get history of user's backtests."""
    # In production, fetch from database
    return {
        "user_id": current_user.id,
        "backtests": [
            {
                "id": 1,
                "strategy": "value_betting",
                "period": "2024-01-01 to 2024-06-30",
                "roi": 18.5,
                "created_at": datetime.now().isoformat(),
            },
            {
                "id": 2,
                "strategy": "kelly_criterion",
                "period": "2024-01-01 to 2024-06-30",
                "roi": 22.3,
                "created_at": datetime.now().isoformat(),
            },
        ],
        "total": 2,
    }
