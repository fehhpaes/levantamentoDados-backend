"""
Bankroll Management System

Provides tools for managing betting bankroll with
proper risk management and stake sizing strategies.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    CONSERVATIVE = "conservative"  # 1-2% per bet
    MODERATE = "moderate"          # 2-3% per bet
    AGGRESSIVE = "aggressive"      # 3-5% per bet
    VERY_AGGRESSIVE = "very_aggressive"  # 5-10% per bet


class StakingMethod(Enum):
    FLAT = "flat"
    PERCENTAGE = "percentage"
    KELLY = "kelly"
    HALF_KELLY = "half_kelly"
    QUARTER_KELLY = "quarter_kelly"
    FIBONACCI = "fibonacci"
    LABOUCHERE = "labouchere"


@dataclass
class BankrollTransaction:
    """Record of bankroll transaction."""
    transaction_type: str  # "deposit", "withdrawal", "bet", "win", "loss"
    amount: float
    balance_after: float
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class BetRecord:
    """Record of a placed bet."""
    bet_id: str
    match: str
    market: str
    odds: float
    stake: float
    potential_return: float
    status: str = "pending"  # pending, won, lost, void
    profit: float = 0
    placed_at: datetime = field(default_factory=datetime.now)
    settled_at: Optional[datetime] = None


@dataclass
class BankrollStatus:
    """Current bankroll status."""
    current_balance: float
    initial_balance: float
    total_profit: float
    roi: float
    total_bets: int
    pending_bets: int
    pending_exposure: float
    available_balance: float
    win_rate: float
    average_odds: float
    max_drawdown: float
    current_drawdown: float
    risk_level: RiskLevel
    recommended_stake: float


class BankrollManager:
    """
    Bankroll management system for sports betting.
    
    Features:
    - Multiple staking strategies
    - Risk level management
    - Drawdown tracking
    - Session management
    - Target setting
    - Loss limits
    """
    
    def __init__(
        self,
        initial_bankroll: float = 1000,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        staking_method: StakingMethod = StakingMethod.PERCENTAGE,
        target_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        session_loss_limit: Optional[float] = None
    ):
        """
        Initialize bankroll manager.
        
        Args:
            initial_bankroll: Starting bankroll amount
            risk_level: Risk level for stake sizing
            staking_method: Method for calculating stakes
            target_profit: Target profit to reach
            stop_loss: Stop loss limit (absolute or percentage)
            session_loss_limit: Daily/session loss limit
        """
        self.initial_bankroll = initial_bankroll
        self.current_bankroll = initial_bankroll
        self.risk_level = risk_level
        self.staking_method = staking_method
        self.target_profit = target_profit
        self.stop_loss = stop_loss
        self.session_loss_limit = session_loss_limit
        
        # History tracking
        self.transactions: List[BankrollTransaction] = []
        self.bets: List[BetRecord] = []
        self.peak_bankroll = initial_bankroll
        
        # Session tracking
        self.session_start_bankroll = initial_bankroll
        self.session_start_time = datetime.now()
        
        # Fibonacci sequence for Fibonacci staking
        self._fibonacci_sequence = [1, 1]
        self._fibonacci_index = 0
        
        # Risk parameters by level
        self._risk_params = {
            RiskLevel.CONSERVATIVE: {"min": 0.01, "max": 0.02, "kelly_mult": 0.25},
            RiskLevel.MODERATE: {"min": 0.02, "max": 0.03, "kelly_mult": 0.5},
            RiskLevel.AGGRESSIVE: {"min": 0.03, "max": 0.05, "kelly_mult": 0.75},
            RiskLevel.VERY_AGGRESSIVE: {"min": 0.05, "max": 0.10, "kelly_mult": 1.0}
        }
        
        # Log initial transaction
        self._log_transaction("deposit", initial_bankroll, "Initial bankroll")
    
    def _log_transaction(
        self,
        trans_type: str,
        amount: float,
        description: str = "",
        metadata: Dict = None
    ) -> None:
        """Log a bankroll transaction."""
        self.transactions.append(BankrollTransaction(
            transaction_type=trans_type,
            amount=amount,
            balance_after=self.current_bankroll,
            description=description,
            metadata=metadata or {}
        ))
    
    def deposit(self, amount: float) -> float:
        """
        Add funds to bankroll.
        
        Args:
            amount: Amount to deposit
            
        Returns:
            New balance
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        
        self.current_bankroll += amount
        self.peak_bankroll = max(self.peak_bankroll, self.current_bankroll)
        self._log_transaction("deposit", amount, "Deposit")
        
        logger.info(f"Deposited ${amount:.2f}. New balance: ${self.current_bankroll:.2f}")
        return self.current_bankroll
    
    def withdraw(self, amount: float) -> float:
        """
        Withdraw funds from bankroll.
        
        Args:
            amount: Amount to withdraw
            
        Returns:
            New balance
        """
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self.available_balance:
            raise ValueError(f"Insufficient funds. Available: ${self.available_balance:.2f}")
        
        self.current_bankroll -= amount
        self._log_transaction("withdrawal", -amount, "Withdrawal")
        
        logger.info(f"Withdrew ${amount:.2f}. New balance: ${self.current_bankroll:.2f}")
        return self.current_bankroll
    
    @property
    def available_balance(self) -> float:
        """Get available balance (excluding pending bets)."""
        pending_exposure = sum(
            b.stake for b in self.bets if b.status == "pending"
        )
        return max(0, self.current_bankroll - pending_exposure)
    
    @property
    def pending_exposure(self) -> float:
        """Get total pending bet exposure."""
        return sum(b.stake for b in self.bets if b.status == "pending")
    
    def calculate_stake(
        self,
        odds: float,
        probability: float,
        confidence: float = 1.0
    ) -> float:
        """
        Calculate recommended stake based on staking method.
        
        Args:
            odds: Decimal odds
            probability: Predicted probability
            confidence: Confidence multiplier (0-1)
            
        Returns:
            Recommended stake amount
        """
        risk_params = self._risk_params[self.risk_level]
        
        if self.staking_method == StakingMethod.FLAT:
            # Fixed percentage of initial bankroll
            base_stake = self.initial_bankroll * risk_params["min"]
            stake = base_stake * confidence
            
        elif self.staking_method == StakingMethod.PERCENTAGE:
            # Percentage of current bankroll
            base_pct = (risk_params["min"] + risk_params["max"]) / 2
            stake = self.current_bankroll * base_pct * confidence
            
        elif self.staking_method in [
            StakingMethod.KELLY,
            StakingMethod.HALF_KELLY,
            StakingMethod.QUARTER_KELLY
        ]:
            # Kelly Criterion
            kelly = self._calculate_kelly(probability, odds)
            
            if self.staking_method == StakingMethod.HALF_KELLY:
                kelly *= 0.5
            elif self.staking_method == StakingMethod.QUARTER_KELLY:
                kelly *= 0.25
            
            kelly *= risk_params["kelly_mult"]
            stake = self.current_bankroll * kelly * confidence
            
        elif self.staking_method == StakingMethod.FIBONACCI:
            # Fibonacci sequence staking
            stake = self._get_fibonacci_stake() * confidence
            
        else:
            # Default to percentage
            stake = self.current_bankroll * risk_params["min"] * confidence
        
        # Apply limits
        max_stake = self.current_bankroll * risk_params["max"]
        stake = min(stake, max_stake)
        stake = min(stake, self.available_balance * 0.9)  # Keep 10% reserve
        stake = max(stake, 1.0)  # Minimum $1 stake
        
        return round(stake, 2)
    
    def _calculate_kelly(
        self,
        probability: float,
        odds: float
    ) -> float:
        """Calculate Kelly criterion stake percentage."""
        # Kelly formula: f = (bp - q) / b
        # where b = decimal odds - 1, p = prob of winning, q = 1-p
        b = odds - 1
        p = probability
        q = 1 - p
        
        kelly = (b * p - q) / b
        return max(0, kelly)
    
    def _get_fibonacci_stake(self) -> float:
        """Get current Fibonacci sequence stake."""
        base_unit = self.initial_bankroll * 0.01
        
        while len(self._fibonacci_sequence) <= self._fibonacci_index:
            self._fibonacci_sequence.append(
                self._fibonacci_sequence[-1] + self._fibonacci_sequence[-2]
            )
        
        return base_unit * self._fibonacci_sequence[self._fibonacci_index]
    
    def place_bet(
        self,
        bet_id: str,
        match: str,
        market: str,
        odds: float,
        stake: Optional[float] = None,
        probability: float = 0.5,
        confidence: float = 1.0
    ) -> BetRecord:
        """
        Place a bet and update bankroll.
        
        Args:
            bet_id: Unique bet identifier
            match: Match description
            market: Betting market
            odds: Decimal odds
            stake: Stake amount (calculated if not provided)
            probability: Predicted probability
            confidence: Confidence level
            
        Returns:
            BetRecord
        """
        # Check limits
        if self._check_stop_loss():
            raise ValueError("Stop loss reached. Cannot place more bets.")
        
        if self._check_session_limit():
            raise ValueError("Session loss limit reached.")
        
        # Calculate stake if not provided
        if stake is None:
            stake = self.calculate_stake(odds, probability, confidence)
        
        # Validate stake
        if stake > self.available_balance:
            raise ValueError(f"Insufficient funds. Available: ${self.available_balance:.2f}")
        
        potential_return = stake * odds
        
        # Create bet record
        bet = BetRecord(
            bet_id=bet_id,
            match=match,
            market=market,
            odds=odds,
            stake=stake,
            potential_return=potential_return
        )
        
        self.bets.append(bet)
        self._log_transaction(
            "bet",
            -stake,
            f"Bet placed: {match} - {market}",
            {"bet_id": bet_id, "odds": odds}
        )
        
        logger.info(f"Bet placed: ${stake:.2f} on {match} @ {odds}")
        return bet
    
    def settle_bet(
        self,
        bet_id: str,
        result: str  # "won", "lost", "void"
    ) -> Tuple[float, float]:
        """
        Settle a bet and update bankroll.
        
        Args:
            bet_id: Bet identifier
            result: Bet result
            
        Returns:
            Tuple of (profit, new_balance)
        """
        bet = next((b for b in self.bets if b.bet_id == bet_id), None)
        if not bet:
            raise ValueError(f"Bet {bet_id} not found")
        
        if bet.status != "pending":
            raise ValueError(f"Bet {bet_id} already settled")
        
        bet.status = result
        bet.settled_at = datetime.now()
        
        if result == "won":
            profit = bet.potential_return - bet.stake
            self.current_bankroll += bet.potential_return
            bet.profit = profit
            
            # Reset Fibonacci on win
            if self.staking_method == StakingMethod.FIBONACCI:
                self._fibonacci_index = max(0, self._fibonacci_index - 2)
            
            self._log_transaction(
                "win",
                bet.potential_return,
                f"Won: {bet.match}",
                {"bet_id": bet_id}
            )
            
        elif result == "lost":
            profit = -bet.stake
            bet.profit = profit
            
            # Increase Fibonacci on loss
            if self.staking_method == StakingMethod.FIBONACCI:
                self._fibonacci_index += 1
            
            self._log_transaction(
                "loss",
                0,
                f"Lost: {bet.match}",
                {"bet_id": bet_id}
            )
            
        else:  # void
            profit = 0
            self.current_bankroll += bet.stake
            bet.profit = 0
            
            self._log_transaction(
                "void",
                bet.stake,
                f"Void: {bet.match}",
                {"bet_id": bet_id}
            )
        
        # Update peak
        self.peak_bankroll = max(self.peak_bankroll, self.current_bankroll)
        
        logger.info(f"Bet settled: {result}. Profit: ${profit:.2f}")
        return profit, self.current_bankroll
    
    def _check_stop_loss(self) -> bool:
        """Check if stop loss has been reached."""
        if self.stop_loss is None:
            return False
        
        # If stop_loss is a percentage (< 1), calculate absolute
        if self.stop_loss < 1:
            limit = self.initial_bankroll * (1 - self.stop_loss)
        else:
            limit = self.initial_bankroll - self.stop_loss
        
        return self.current_bankroll <= limit
    
    def _check_session_limit(self) -> bool:
        """Check if session loss limit has been reached."""
        if self.session_loss_limit is None:
            return False
        
        session_pl = self.current_bankroll - self.session_start_bankroll
        
        if self.session_loss_limit < 1:
            limit = -self.session_start_bankroll * self.session_loss_limit
        else:
            limit = -self.session_loss_limit
        
        return session_pl <= limit
    
    def new_session(self) -> None:
        """Start a new betting session."""
        self.session_start_bankroll = self.current_bankroll
        self.session_start_time = datetime.now()
        self._fibonacci_index = 0
        logger.info(f"New session started with ${self.current_bankroll:.2f}")
    
    def get_status(self) -> BankrollStatus:
        """Get current bankroll status."""
        settled_bets = [b for b in self.bets if b.status != "pending"]
        won_bets = [b for b in settled_bets if b.status == "won"]
        
        total_profit = self.current_bankroll - self.initial_bankroll
        roi = total_profit / self.initial_bankroll * 100 if self.initial_bankroll > 0 else 0
        
        win_rate = len(won_bets) / len(settled_bets) if settled_bets else 0
        avg_odds = np.mean([b.odds for b in self.bets]) if self.bets else 0
        
        # Calculate drawdown
        max_drawdown = (self.peak_bankroll - min(
            t.balance_after for t in self.transactions
        )) / self.peak_bankroll if self.peak_bankroll > 0 else 0
        
        current_drawdown = (self.peak_bankroll - self.current_bankroll) / self.peak_bankroll if self.peak_bankroll > 0 else 0
        
        # Calculate recommended stake
        recommended_stake = self.calculate_stake(2.0, 0.55, 1.0)
        
        return BankrollStatus(
            current_balance=round(self.current_bankroll, 2),
            initial_balance=round(self.initial_bankroll, 2),
            total_profit=round(total_profit, 2),
            roi=round(roi, 2),
            total_bets=len(self.bets),
            pending_bets=len([b for b in self.bets if b.status == "pending"]),
            pending_exposure=round(self.pending_exposure, 2),
            available_balance=round(self.available_balance, 2),
            win_rate=round(win_rate, 4),
            average_odds=round(avg_odds, 2),
            max_drawdown=round(max_drawdown * 100, 2),
            current_drawdown=round(current_drawdown * 100, 2),
            risk_level=self.risk_level,
            recommended_stake=recommended_stake
        )
    
    def get_performance_summary(
        self,
        period_days: Optional[int] = None
    ) -> Dict:
        """
        Get performance summary for period.
        
        Args:
            period_days: Number of days to analyze (None for all time)
            
        Returns:
            Performance summary dictionary
        """
        if period_days:
            cutoff = datetime.now() - timedelta(days=period_days)
            bets = [b for b in self.bets if b.placed_at >= cutoff]
        else:
            bets = self.bets
        
        settled = [b for b in bets if b.status != "pending"]
        won = [b for b in settled if b.status == "won"]
        lost = [b for b in settled if b.status == "lost"]
        
        total_staked = sum(b.stake for b in settled)
        total_profit = sum(b.profit for b in settled)
        
        # By market breakdown
        markets = {}
        for bet in settled:
            if bet.market not in markets:
                markets[bet.market] = {"bets": 0, "won": 0, "profit": 0}
            markets[bet.market]["bets"] += 1
            if bet.status == "won":
                markets[bet.market]["won"] += 1
            markets[bet.market]["profit"] += bet.profit
        
        # Daily breakdown
        daily = {}
        for bet in settled:
            day = bet.settled_at.strftime("%Y-%m-%d") if bet.settled_at else "Unknown"
            if day not in daily:
                daily[day] = {"bets": 0, "profit": 0}
            daily[day]["bets"] += 1
            daily[day]["profit"] += bet.profit
        
        return {
            "period": f"Last {period_days} days" if period_days else "All time",
            "total_bets": len(settled),
            "won": len(won),
            "lost": len(lost),
            "win_rate": len(won) / len(settled) * 100 if settled else 0,
            "total_staked": round(total_staked, 2),
            "total_profit": round(total_profit, 2),
            "roi": round(total_profit / total_staked * 100, 2) if total_staked > 0 else 0,
            "average_stake": round(total_staked / len(settled), 2) if settled else 0,
            "average_odds": round(np.mean([b.odds for b in settled]), 2) if settled else 0,
            "by_market": markets,
            "daily_breakdown": daily
        }
    
    def export_history(self) -> Dict:
        """Export complete bankroll history."""
        return {
            "initial_bankroll": self.initial_bankroll,
            "current_bankroll": self.current_bankroll,
            "risk_level": self.risk_level.value,
            "staking_method": self.staking_method.value,
            "transactions": [
                {
                    "type": t.transaction_type,
                    "amount": t.amount,
                    "balance_after": t.balance_after,
                    "timestamp": t.timestamp.isoformat(),
                    "description": t.description
                }
                for t in self.transactions
            ],
            "bets": [
                {
                    "bet_id": b.bet_id,
                    "match": b.match,
                    "market": b.market,
                    "odds": b.odds,
                    "stake": b.stake,
                    "status": b.status,
                    "profit": b.profit,
                    "placed_at": b.placed_at.isoformat()
                }
                for b in self.bets
            ]
        }


class KellyCriterion:
    """
    Kelly Criterion calculator for optimal stake sizing.
    
    The Kelly Criterion determines the optimal fraction of bankroll
    to bet to maximize long-term growth rate.
    """
    
    def __init__(self, fraction: float = 1.0):
        """
        Initialize Kelly calculator.
        
        Args:
            fraction: Fraction of Kelly to use (0.25 = quarter Kelly, etc.)
        """
        self.fraction = fraction
    
    def calculate(
        self,
        probability: float,
        odds: float,
    ) -> float:
        """
        Calculate Kelly stake percentage.
        
        Args:
            probability: Estimated probability of winning
            odds: Decimal odds offered
            
        Returns:
            Recommended stake as percentage of bankroll
        """
        if probability <= 0 or probability >= 1:
            return 0.0
        if odds <= 1:
            return 0.0
        
        # Kelly formula: f = (bp - q) / b
        # where b = odds - 1, p = probability, q = 1 - p
        b = odds - 1
        p = probability
        q = 1 - p
        
        kelly = (b * p - q) / b
        
        # Apply fraction and ensure non-negative
        result = max(0, kelly * self.fraction)
        
        return result * 100  # Return as percentage
    
    def calculate_with_edge(
        self,
        edge: float,
        odds: float,
    ) -> float:
        """
        Calculate Kelly stake given edge percentage.
        
        Args:
            edge: Expected edge as percentage (e.g., 5 for 5%)
            odds: Decimal odds offered
            
        Returns:
            Recommended stake as percentage of bankroll
        """
        # Convert edge to probability
        implied_prob = 1 / odds
        probability = implied_prob + (edge / 100)
        probability = min(0.99, max(0.01, probability))
        
        return self.calculate(probability, odds)
    
    @staticmethod
    def full_kelly(probability: float, odds: float) -> float:
        """Calculate full Kelly stake."""
        return KellyCriterion(1.0).calculate(probability, odds)
    
    @staticmethod
    def half_kelly(probability: float, odds: float) -> float:
        """Calculate half Kelly stake."""
        return KellyCriterion(0.5).calculate(probability, odds)
    
    @staticmethod
    def quarter_kelly(probability: float, odds: float) -> float:
        """Calculate quarter Kelly stake."""
        return KellyCriterion(0.25).calculate(probability, odds)
