"""
Backtesting Engine for Betting Strategies

Simulates historical performance of betting strategies
to evaluate their profitability and risk characteristics.
"""

import numpy as np
from typing import Dict, List, Optional, Callable, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    VALUE_BETTING = "value_betting"
    ARBITRAGE = "arbitrage"
    KELLY_CRITERION = "kelly_criterion"
    FIXED_STAKE = "fixed_stake"
    PERCENTAGE_STAKE = "percentage_stake"
    MARTINGALE = "martingale"
    FIBONACCI = "fibonacci"
    CUSTOM = "custom"


@dataclass
class Bet:
    """Individual bet record."""
    match_id: int
    match_name: str
    market: str
    selection: str
    odds: float
    stake: float
    predicted_probability: float
    result: Optional[str] = None  # "win", "loss", "void"
    profit: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    strategy_name: str
    period_start: datetime
    period_end: datetime
    total_bets: int
    winning_bets: int
    losing_bets: int
    void_bets: int
    win_rate: float
    total_staked: float
    total_profit: float
    roi: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    average_odds: float
    average_stake: float
    longest_winning_streak: int
    longest_losing_streak: int
    bets: List[Bet]
    equity_curve: List[Tuple[datetime, float]]
    monthly_returns: Dict[str, float]
    market_breakdown: Dict[str, Dict]


@dataclass
class StrategyConfig:
    """Configuration for a betting strategy."""
    name: str
    strategy_type: StrategyType
    min_edge: float = 0.05
    min_odds: float = 1.2
    max_odds: float = 10.0
    min_confidence: float = 0.5
    base_stake: float = 100
    stake_percentage: float = 0.02  # For percentage staking
    kelly_fraction: float = 0.25  # Fraction of Kelly to use
    max_stake: float = 500
    markets: List[str] = field(default_factory=lambda: ["1X2"])
    custom_filter: Optional[Callable[[Dict], bool]] = None


class BettingStrategy:
    """Base class for betting strategies."""
    
    def __init__(self, config: StrategyConfig):
        """Initialize strategy with configuration."""
        self.config = config
        self.bankroll = 10000
        self.current_bankroll = self.bankroll
        self.bets_history: List[Bet] = []
        
    def should_bet(
        self,
        prediction: Dict,
        odds: float
    ) -> bool:
        """
        Determine if we should place a bet.
        
        Args:
            prediction: Model prediction
            odds: Available odds
            
        Returns:
            True if bet should be placed
        """
        # Check odds range
        if odds < self.config.min_odds or odds > self.config.max_odds:
            return False
        
        # Check confidence
        confidence = prediction.get("confidence", 0)
        if confidence < self.config.min_confidence:
            return False
        
        # Calculate edge
        probability = prediction.get("probability", 0)
        implied_prob = 1 / odds
        edge = probability - implied_prob
        
        if edge < self.config.min_edge:
            return False
        
        # Apply custom filter if provided
        if self.config.custom_filter:
            if not self.config.custom_filter(prediction):
                return False
        
        return True
    
    def calculate_stake(
        self,
        prediction: Dict,
        odds: float
    ) -> float:
        """
        Calculate stake amount based on strategy.
        
        Args:
            prediction: Model prediction
            odds: Available odds
            
        Returns:
            Stake amount
        """
        if self.config.strategy_type == StrategyType.FIXED_STAKE:
            stake = self.config.base_stake
            
        elif self.config.strategy_type == StrategyType.PERCENTAGE_STAKE:
            stake = self.current_bankroll * self.config.stake_percentage
            
        elif self.config.strategy_type == StrategyType.KELLY_CRITERION:
            probability = prediction.get("probability", 0.5)
            kelly = (probability * odds - 1) / (odds - 1)
            stake = self.current_bankroll * kelly * self.config.kelly_fraction
            
        elif self.config.strategy_type == StrategyType.VALUE_BETTING:
            # Stake proportional to edge
            probability = prediction.get("probability", 0.5)
            implied_prob = 1 / odds
            edge = probability - implied_prob
            stake = self.config.base_stake * (1 + edge * 10)
            
        else:
            stake = self.config.base_stake
        
        # Apply limits
        stake = max(0, min(stake, self.config.max_stake))
        stake = min(stake, self.current_bankroll * 0.1)  # Max 10% of bankroll
        
        return round(stake, 2)
    
    def process_result(
        self,
        bet: Bet,
        result: str
    ) -> float:
        """
        Process bet result and update bankroll.
        
        Args:
            bet: The bet that was settled
            result: "win", "loss", or "void"
            
        Returns:
            Profit/loss amount
        """
        if result == "win":
            profit = bet.stake * (bet.odds - 1)
        elif result == "loss":
            profit = -bet.stake
        else:  # void
            profit = 0
        
        bet.result = result
        bet.profit = profit
        self.current_bankroll += profit
        
        return profit


class BacktestingEngine:
    """
    Engine for backtesting betting strategies.
    
    Features:
    - Historical simulation
    - Multiple strategy comparison
    - Risk metrics calculation
    - Equity curve analysis
    - Detailed reporting
    """
    
    def __init__(self, initial_bankroll: float = 10000):
        """
        Initialize backtesting engine.
        
        Args:
            initial_bankroll: Starting bankroll
        """
        self.initial_bankroll = initial_bankroll
        self.strategies: Dict[str, BettingStrategy] = {}
        self.results: Dict[str, BacktestResult] = {}
    
    def add_strategy(
        self,
        config: StrategyConfig
    ) -> None:
        """Add a strategy to the engine."""
        strategy = BettingStrategy(config)
        strategy.bankroll = self.initial_bankroll
        strategy.current_bankroll = self.initial_bankroll
        self.strategies[config.name] = strategy
        logger.info(f"Added strategy: {config.name}")
    
    def run_backtest(
        self,
        strategy_name: str,
        matches: List[Dict],
        predictions: Dict[int, Dict],
        odds_history: Dict[int, Dict]
    ) -> BacktestResult:
        """
        Run backtest for a strategy.
        
        Args:
            strategy_name: Name of strategy to test
            matches: Historical match data
            predictions: Predictions for each match (match_id -> prediction)
            odds_history: Historical odds (match_id -> odds)
            
        Returns:
            BacktestResult with detailed metrics
        """
        if strategy_name not in self.strategies:
            raise ValueError(f"Strategy {strategy_name} not found")
        
        strategy = self.strategies[strategy_name]
        strategy.current_bankroll = self.initial_bankroll
        strategy.bets_history = []
        
        # Sort matches by date
        sorted_matches = sorted(
            matches,
            key=lambda x: x.get("date", datetime.min)
        )
        
        bets = []
        equity_curve = [(sorted_matches[0].get("date", datetime.now()), self.initial_bankroll)]
        
        for match in sorted_matches:
            match_id = match.get("id")
            
            if match_id not in predictions or match_id not in odds_history:
                continue
            
            prediction = predictions[match_id]
            odds = odds_history[match_id]
            
            # Get best odds for predicted outcome
            predicted_market = prediction.get("best_market", "home_win")
            market_odds = odds.get(predicted_market, 0)
            
            if market_odds <= 1:
                continue
            
            # Check if we should bet
            if strategy.should_bet(prediction, market_odds):
                stake = strategy.calculate_stake(prediction, market_odds)
                
                if stake > 0:
                    bet = Bet(
                        match_id=match_id,
                        match_name=f"{match.get('home_team', '')} vs {match.get('away_team', '')}",
                        market=predicted_market,
                        selection=predicted_market,
                        odds=market_odds,
                        stake=stake,
                        predicted_probability=prediction.get("probability", 0.5),
                        timestamp=match.get("date", datetime.now())
                    )
                    
                    # Determine result based on actual outcome
                    actual_result = self._get_match_result(match)
                    if actual_result:
                        bet_result = "win" if actual_result == predicted_market else "loss"
                        strategy.process_result(bet, bet_result)
                        bets.append(bet)
                        
                        # Update equity curve
                        equity_curve.append((
                            bet.timestamp,
                            strategy.current_bankroll
                        ))
        
        # Calculate metrics
        result = self._calculate_metrics(strategy_name, bets, equity_curve)
        self.results[strategy_name] = result
        
        return result
    
    def _get_match_result(self, match: Dict) -> Optional[str]:
        """Determine match result market."""
        home_score = match.get("home_score")
        away_score = match.get("away_score")
        
        if home_score is None or away_score is None:
            return None
        
        if home_score > away_score:
            return "home_win"
        elif home_score < away_score:
            return "away_win"
        else:
            return "draw"
    
    def _calculate_metrics(
        self,
        strategy_name: str,
        bets: List[Bet],
        equity_curve: List[Tuple[datetime, float]]
    ) -> BacktestResult:
        """Calculate backtest metrics."""
        if not bets:
            return BacktestResult(
                strategy_name=strategy_name,
                period_start=datetime.now(),
                period_end=datetime.now(),
                total_bets=0,
                winning_bets=0,
                losing_bets=0,
                void_bets=0,
                win_rate=0,
                total_staked=0,
                total_profit=0,
                roi=0,
                max_drawdown=0,
                sharpe_ratio=0,
                profit_factor=0,
                average_odds=0,
                average_stake=0,
                longest_winning_streak=0,
                longest_losing_streak=0,
                bets=[],
                equity_curve=[],
                monthly_returns={},
                market_breakdown={}
            )
        
        # Basic stats
        winning_bets = [b for b in bets if b.result == "win"]
        losing_bets = [b for b in bets if b.result == "loss"]
        void_bets = [b for b in bets if b.result == "void"]
        
        total_staked = sum(b.stake for b in bets)
        total_profit = sum(b.profit or 0 for b in bets)
        
        # Streaks
        winning_streak = 0
        losing_streak = 0
        max_winning_streak = 0
        max_losing_streak = 0
        
        for bet in bets:
            if bet.result == "win":
                winning_streak += 1
                losing_streak = 0
                max_winning_streak = max(max_winning_streak, winning_streak)
            elif bet.result == "loss":
                losing_streak += 1
                winning_streak = 0
                max_losing_streak = max(max_losing_streak, losing_streak)
        
        # Drawdown
        peak = self.initial_bankroll
        max_drawdown = 0
        
        for _, equity in equity_curve:
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        # Sharpe Ratio (simplified)
        returns = [b.profit / b.stake for b in bets if b.stake > 0]
        if len(returns) > 1:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # Profit Factor
        gross_profit = sum(b.profit for b in bets if b.profit and b.profit > 0)
        gross_loss = abs(sum(b.profit for b in bets if b.profit and b.profit < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Monthly returns
        monthly_returns = defaultdict(float)
        for bet in bets:
            month_key = bet.timestamp.strftime("%Y-%m")
            monthly_returns[month_key] += bet.profit or 0
        
        # Market breakdown
        market_breakdown = defaultdict(lambda: {
            "bets": 0, "wins": 0, "profit": 0, "roi": 0
        })
        
        for bet in bets:
            market = bet.market
            market_breakdown[market]["bets"] += 1
            if bet.result == "win":
                market_breakdown[market]["wins"] += 1
            market_breakdown[market]["profit"] += bet.profit or 0
        
        for market, stats in market_breakdown.items():
            staked = sum(b.stake for b in bets if b.market == market)
            stats["roi"] = stats["profit"] / staked * 100 if staked > 0 else 0
        
        return BacktestResult(
            strategy_name=strategy_name,
            period_start=bets[0].timestamp if bets else datetime.now(),
            period_end=bets[-1].timestamp if bets else datetime.now(),
            total_bets=len(bets),
            winning_bets=len(winning_bets),
            losing_bets=len(losing_bets),
            void_bets=len(void_bets),
            win_rate=len(winning_bets) / len(bets) if bets else 0,
            total_staked=round(total_staked, 2),
            total_profit=round(total_profit, 2),
            roi=round(total_profit / total_staked * 100, 2) if total_staked > 0 else 0,
            max_drawdown=round(max_drawdown * 100, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            profit_factor=round(profit_factor, 2),
            average_odds=round(np.mean([b.odds for b in bets]), 2) if bets else 0,
            average_stake=round(np.mean([b.stake for b in bets]), 2) if bets else 0,
            longest_winning_streak=max_winning_streak,
            longest_losing_streak=max_losing_streak,
            bets=bets,
            equity_curve=equity_curve,
            monthly_returns=dict(monthly_returns),
            market_breakdown=dict(market_breakdown)
        )
    
    def compare_strategies(
        self,
        matches: List[Dict],
        predictions: Dict[int, Dict],
        odds_history: Dict[int, Dict]
    ) -> Dict[str, BacktestResult]:
        """
        Run backtest for all strategies and compare.
        
        Returns:
            Dict of strategy name -> BacktestResult
        """
        for name in self.strategies:
            self.run_backtest(name, matches, predictions, odds_history)
        
        return self.results
    
    def generate_report(
        self,
        strategy_name: str
    ) -> Dict[str, Any]:
        """
        Generate detailed backtest report.
        
        Args:
            strategy_name: Strategy to report on
            
        Returns:
            Detailed report dictionary
        """
        if strategy_name not in self.results:
            raise ValueError(f"No results for strategy {strategy_name}")
        
        result = self.results[strategy_name]
        
        return {
            "summary": {
                "strategy": result.strategy_name,
                "period": f"{result.period_start} to {result.period_end}",
                "total_bets": result.total_bets,
                "win_rate": f"{result.win_rate * 100:.1f}%",
                "roi": f"{result.roi:.1f}%",
                "total_profit": f"${result.total_profit:.2f}",
                "max_drawdown": f"{result.max_drawdown:.1f}%",
                "sharpe_ratio": result.sharpe_ratio,
                "profit_factor": result.profit_factor
            },
            "risk_metrics": {
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "longest_losing_streak": result.longest_losing_streak,
                "volatility": np.std([b.profit/b.stake for b in result.bets if b.stake > 0]) if result.bets else 0
            },
            "performance": {
                "winning_bets": result.winning_bets,
                "losing_bets": result.losing_bets,
                "longest_winning_streak": result.longest_winning_streak,
                "average_odds": result.average_odds,
                "average_stake": result.average_stake
            },
            "monthly_returns": result.monthly_returns,
            "market_breakdown": result.market_breakdown,
            "equity_curve": [
                {"date": str(d), "equity": e}
                for d, e in result.equity_curve
            ]
        }
    
    def optimize_strategy(
        self,
        strategy_name: str,
        matches: List[Dict],
        predictions: Dict[int, Dict],
        odds_history: Dict[int, Dict],
        param_grid: Dict[str, List[Any]]
    ) -> Tuple[Dict[str, Any], BacktestResult]:
        """
        Optimize strategy parameters using grid search.
        
        Args:
            strategy_name: Base strategy name
            matches: Historical matches
            predictions: Predictions
            odds_history: Historical odds
            param_grid: Parameter grid to search
            
        Returns:
            Tuple of (best_params, best_result)
        """
        if strategy_name not in self.strategies:
            raise ValueError(f"Strategy {strategy_name} not found")
        
        base_config = self.strategies[strategy_name].config
        best_params = {}
        best_result = None
        best_roi = float('-inf')
        
        # Generate all parameter combinations
        from itertools import product
        
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        for values in product(*param_values):
            # Create new config with parameters
            params = dict(zip(param_names, values))
            
            test_config = StrategyConfig(
                name=f"{strategy_name}_test",
                strategy_type=base_config.strategy_type,
                min_edge=params.get("min_edge", base_config.min_edge),
                min_odds=params.get("min_odds", base_config.min_odds),
                max_odds=params.get("max_odds", base_config.max_odds),
                min_confidence=params.get("min_confidence", base_config.min_confidence),
                base_stake=params.get("base_stake", base_config.base_stake),
                kelly_fraction=params.get("kelly_fraction", base_config.kelly_fraction)
            )
            
            self.add_strategy(test_config)
            result = self.run_backtest(
                f"{strategy_name}_test",
                matches,
                predictions,
                odds_history
            )
            
            if result.roi > best_roi:
                best_roi = result.roi
                best_params = params
                best_result = result
            
            # Clean up
            del self.strategies[f"{strategy_name}_test"]
            del self.results[f"{strategy_name}_test"]
        
        logger.info(f"Optimization complete. Best ROI: {best_roi:.2f}%")
        return best_params, best_result
