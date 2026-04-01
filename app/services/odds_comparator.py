"""
Advanced Odds Comparator

Compares odds across multiple bookmakers to find the best
prices and identify arbitrage opportunities.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class OddsFormat(Enum):
    DECIMAL = "decimal"
    AMERICAN = "american"
    FRACTIONAL = "fractional"
    PROBABILITY = "probability"


@dataclass
class BookmakerOdds:
    """Odds from a single bookmaker."""
    bookmaker: str
    market: str
    selection: str
    odds: float
    timestamp: datetime = field(default_factory=datetime.now)
    is_live: bool = False
    metadata: Dict = field(default_factory=dict)


@dataclass
class OddsComparison:
    """Comparison result for a market selection."""
    match: str
    market: str
    selection: str
    best_odds: float
    best_bookmaker: str
    worst_odds: float
    worst_bookmaker: str
    average_odds: float
    odds_range: float
    all_odds: List[BookmakerOdds]
    implied_probability: float
    overround: float
    edge_vs_average: float


@dataclass
class ArbitrageOpportunity:
    """Detected arbitrage opportunity."""
    match: str
    market: str
    profit_percentage: float
    total_stake: float
    selections: List[Dict]
    is_guaranteed: bool
    detected_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None


@dataclass
class ValueBetOpportunity:
    """Value bet opportunity from odds comparison."""
    match: str
    market: str
    selection: str
    bookmaker: str
    odds: float
    fair_odds: float
    edge: float
    expected_value: float
    confidence: float
    model_probability: float


class OddsConverter:
    """Convert between different odds formats."""
    
    @staticmethod
    def decimal_to_american(decimal_odds: float) -> int:
        """Convert decimal to American odds."""
        if decimal_odds >= 2.0:
            return int((decimal_odds - 1) * 100)
        else:
            return int(-100 / (decimal_odds - 1))
    
    @staticmethod
    def american_to_decimal(american_odds: int) -> float:
        """Convert American to decimal odds."""
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
    
    @staticmethod
    def decimal_to_fractional(decimal_odds: float) -> str:
        """Convert decimal to fractional odds."""
        from fractions import Fraction
        frac = Fraction(decimal_odds - 1).limit_denominator(100)
        return f"{frac.numerator}/{frac.denominator}"
    
    @staticmethod
    def decimal_to_probability(decimal_odds: float) -> float:
        """Convert decimal odds to implied probability."""
        return 1 / decimal_odds
    
    @staticmethod
    def probability_to_decimal(probability: float) -> float:
        """Convert probability to decimal odds."""
        return 1 / probability if probability > 0 else float('inf')


class OddsComparator:
    """
    Advanced odds comparison system.
    
    Features:
    - Multi-bookmaker comparison
    - Best odds identification
    - Arbitrage detection
    - Value bet finding
    - Historical odds tracking
    - Odds movement alerts
    """
    
    def __init__(
        self,
        min_arbitrage_profit: float = 0.5,
        min_value_edge: float = 0.03,
        track_history: bool = True
    ):
        """
        Initialize odds comparator.
        
        Args:
            min_arbitrage_profit: Minimum % profit for arbitrage alerts
            min_value_edge: Minimum edge for value bet alerts
            track_history: Whether to track historical odds
        """
        self.min_arbitrage_profit = min_arbitrage_profit
        self.min_value_edge = min_value_edge
        self.track_history = track_history
        
        # Odds storage
        self.current_odds: Dict[str, Dict[str, List[BookmakerOdds]]] = defaultdict(
            lambda: defaultdict(list)
        )  # match_id -> market -> list of odds
        
        self.historical_odds: List[BookmakerOdds] = []
        self.converter = OddsConverter()
        
        # Bookmaker rankings (for tiebreaking)
        self.bookmaker_rankings = {
            "pinnacle": 1,
            "bet365": 2,
            "betfair": 3,
            "william_hill": 4,
            "unibet": 5
        }
    
    def add_odds(
        self,
        match_id: str,
        bookmaker: str,
        market: str,
        selection: str,
        odds: float,
        is_live: bool = False,
        metadata: Dict = None
    ) -> None:
        """
        Add odds from a bookmaker.
        
        Args:
            match_id: Match identifier
            bookmaker: Bookmaker name
            market: Market type (e.g., "1X2", "Over/Under 2.5")
            selection: Selection (e.g., "Home", "Over")
            odds: Decimal odds
            is_live: Whether odds are for live betting
            metadata: Additional metadata
        """
        odds_entry = BookmakerOdds(
            bookmaker=bookmaker,
            market=market,
            selection=selection,
            odds=odds,
            is_live=is_live,
            metadata=metadata or {}
        )
        
        # Update or add odds
        key = f"{market}_{selection}"
        existing = [
            o for o in self.current_odds[match_id][key]
            if o.bookmaker != bookmaker
        ]
        existing.append(odds_entry)
        self.current_odds[match_id][key] = existing
        
        # Track history
        if self.track_history:
            self.historical_odds.append(odds_entry)
    
    def add_bulk_odds(
        self,
        match_id: str,
        odds_data: List[Dict]
    ) -> None:
        """
        Add multiple odds at once.
        
        Args:
            match_id: Match identifier
            odds_data: List of odds dictionaries
        """
        for data in odds_data:
            self.add_odds(
                match_id=match_id,
                bookmaker=data["bookmaker"],
                market=data["market"],
                selection=data["selection"],
                odds=data["odds"],
                is_live=data.get("is_live", False),
                metadata=data.get("metadata")
            )
    
    def get_best_odds(
        self,
        match_id: str,
        market: str,
        selection: str
    ) -> Optional[BookmakerOdds]:
        """
        Get best available odds for a selection.
        
        Args:
            match_id: Match identifier
            market: Market type
            selection: Selection
            
        Returns:
            BookmakerOdds with highest odds
        """
        key = f"{market}_{selection}"
        odds_list = self.current_odds.get(match_id, {}).get(key, [])
        
        if not odds_list:
            return None
        
        return max(odds_list, key=lambda x: x.odds)
    
    def compare_odds(
        self,
        match_id: str,
        match_name: str,
        market: str = None
    ) -> List[OddsComparison]:
        """
        Compare odds across bookmakers for a match.
        
        Args:
            match_id: Match identifier
            match_name: Match display name
            market: Specific market to compare (None for all)
            
        Returns:
            List of OddsComparison for each selection
        """
        comparisons = []
        match_odds = self.current_odds.get(match_id, {})
        
        for key, odds_list in match_odds.items():
            if not odds_list:
                continue
            
            market_name = odds_list[0].market
            if market and market_name != market:
                continue
            
            selection = odds_list[0].selection
            
            best = max(odds_list, key=lambda x: x.odds)
            worst = min(odds_list, key=lambda x: x.odds)
            avg = np.mean([o.odds for o in odds_list])
            
            # Calculate overround
            implied_prob = 1 / best.odds
            
            comparisons.append(OddsComparison(
                match=match_name,
                market=market_name,
                selection=selection,
                best_odds=best.odds,
                best_bookmaker=best.bookmaker,
                worst_odds=worst.odds,
                worst_bookmaker=worst.bookmaker,
                average_odds=round(avg, 3),
                odds_range=round(best.odds - worst.odds, 3),
                all_odds=odds_list,
                implied_probability=round(implied_prob, 4),
                overround=0,  # Calculated per market
                edge_vs_average=round((best.odds - avg) / avg * 100, 2)
            ))
        
        return comparisons
    
    def calculate_overround(
        self,
        match_id: str,
        market: str
    ) -> float:
        """
        Calculate bookmaker overround for a market.
        
        Args:
            match_id: Match identifier
            market: Market type
            
        Returns:
            Overround percentage (0% = fair, >0% = bookmaker margin)
        """
        match_odds = self.current_odds.get(match_id, {})
        
        # Get all selections for this market
        market_selections = {}
        for key, odds_list in match_odds.items():
            if not odds_list or odds_list[0].market != market:
                continue
            selection = odds_list[0].selection
            # Use best odds for fairest calculation
            best = max(odds_list, key=lambda x: x.odds)
            market_selections[selection] = best.odds
        
        if not market_selections:
            return 0
        
        # Sum of implied probabilities
        total_prob = sum(1 / odds for odds in market_selections.values())
        overround = (total_prob - 1) * 100
        
        return round(overround, 2)
    
    def detect_arbitrage(
        self,
        match_id: str,
        match_name: str,
        stake: float = 1000
    ) -> List[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunities across bookmakers.
        
        Args:
            match_id: Match identifier
            match_name: Match display name
            stake: Total stake amount
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        match_odds = self.current_odds.get(match_id, {})
        
        # Group by market
        markets = defaultdict(dict)
        for key, odds_list in match_odds.items():
            if not odds_list:
                continue
            market = odds_list[0].market
            selection = odds_list[0].selection
            best = max(odds_list, key=lambda x: x.odds)
            markets[market][selection] = best
        
        # Check each market for arbitrage
        for market, selections in markets.items():
            if len(selections) < 2:
                continue
            
            # Calculate total implied probability using best odds
            total_implied = sum(1 / o.odds for o in selections.values())
            
            if total_implied < 1:
                # Arbitrage exists!
                profit_pct = (1 - total_implied) * 100
                
                if profit_pct >= self.min_arbitrage_profit:
                    # Calculate stakes for each selection
                    bet_selections = []
                    for sel_name, odds_entry in selections.items():
                        sel_stake = stake / odds_entry.odds / total_implied
                        bet_selections.append({
                            "selection": sel_name,
                            "bookmaker": odds_entry.bookmaker,
                            "odds": odds_entry.odds,
                            "stake": round(sel_stake, 2),
                            "potential_return": round(sel_stake * odds_entry.odds, 2)
                        })
                    
                    opportunities.append(ArbitrageOpportunity(
                        match=match_name,
                        market=market,
                        profit_percentage=round(profit_pct, 3),
                        total_stake=stake,
                        selections=bet_selections,
                        is_guaranteed=True
                    ))
        
        return sorted(opportunities, key=lambda x: x.profit_percentage, reverse=True)
    
    def find_value_bets(
        self,
        match_id: str,
        match_name: str,
        model_probabilities: Dict[str, float]
    ) -> List[ValueBetOpportunity]:
        """
        Find value bets by comparing odds to model probabilities.
        
        Args:
            match_id: Match identifier
            match_name: Match display name
            model_probabilities: Model-predicted probabilities
            
        Returns:
            List of value bet opportunities
        """
        value_bets = []
        match_odds = self.current_odds.get(match_id, {})
        
        for key, odds_list in match_odds.items():
            if not odds_list:
                continue
            
            selection = odds_list[0].selection
            market = odds_list[0].market
            
            # Map selection to probability key
            prob_key = self._map_selection_to_probability(selection, market)
            if prob_key not in model_probabilities:
                continue
            
            model_prob = model_probabilities[prob_key]
            fair_odds = 1 / model_prob if model_prob > 0 else float('inf')
            
            # Find best odds
            best = max(odds_list, key=lambda x: x.odds)
            
            # Calculate edge
            implied_prob = 1 / best.odds
            edge = model_prob - implied_prob
            
            if edge >= self.min_value_edge:
                ev = model_prob * best.odds - 1
                
                # Confidence based on edge magnitude
                confidence = min(1.0, edge / 0.15)  # Max confidence at 15% edge
                
                value_bets.append(ValueBetOpportunity(
                    match=match_name,
                    market=market,
                    selection=selection,
                    bookmaker=best.bookmaker,
                    odds=best.odds,
                    fair_odds=round(fair_odds, 3),
                    edge=round(edge, 4),
                    expected_value=round(ev, 4),
                    confidence=round(confidence, 2),
                    model_probability=round(model_prob, 4)
                ))
        
        return sorted(value_bets, key=lambda x: x.edge, reverse=True)
    
    def _map_selection_to_probability(
        self,
        selection: str,
        market: str
    ) -> str:
        """Map selection name to probability dictionary key."""
        selection_map = {
            "1": "home_win",
            "home": "home_win",
            "home_win": "home_win",
            "x": "draw",
            "draw": "draw",
            "2": "away_win",
            "away": "away_win",
            "away_win": "away_win",
            "over": "over_2_5",
            "over_2.5": "over_2_5",
            "under": "under_2_5",
            "under_2.5": "under_2_5",
            "btts_yes": "btts",
            "btts_no": "btts_no"
        }
        
        return selection_map.get(selection.lower(), selection.lower())
    
    def get_odds_movement(
        self,
        match_id: str,
        market: str,
        selection: str,
        hours: int = 24
    ) -> List[Dict]:
        """
        Get odds movement for a selection.
        
        Args:
            match_id: Match identifier
            market: Market type
            selection: Selection
            hours: Hours of history to analyze
            
        Returns:
            List of odds changes over time
        """
        if not self.track_history:
            return []
        
        cutoff = datetime.now() - timedelta(hours=hours)
        
        relevant = [
            o for o in self.historical_odds
            if o.market == market 
            and o.selection == selection
            and o.timestamp >= cutoff
        ]
        
        # Group by bookmaker and sort by time
        by_bookmaker = defaultdict(list)
        for o in relevant:
            by_bookmaker[o.bookmaker].append({
                "timestamp": o.timestamp.isoformat(),
                "odds": o.odds
            })
        
        movement = []
        for bookmaker, history in by_bookmaker.items():
            sorted_history = sorted(history, key=lambda x: x["timestamp"])
            if len(sorted_history) >= 2:
                opening = sorted_history[0]["odds"]
                current = sorted_history[-1]["odds"]
                change = (current - opening) / opening * 100
                
                movement.append({
                    "bookmaker": bookmaker,
                    "opening_odds": opening,
                    "current_odds": current,
                    "change_percent": round(change, 2),
                    "direction": "drifting" if change > 0 else "shortening",
                    "history": sorted_history
                })
        
        return movement
    
    def get_sharp_bookmaker_odds(
        self,
        match_id: str,
        market: str = None,
        sharp_bookmakers: List[str] = None
    ) -> Dict[str, float]:
        """
        Get odds from sharp bookmakers (Pinnacle, Betfair, etc.).
        
        Sharp bookmaker odds are considered closest to true probabilities.
        
        Args:
            match_id: Match identifier
            market: Specific market (None for all)
            sharp_bookmakers: List of sharp bookmaker names
            
        Returns:
            Dictionary of selection -> fair odds
        """
        if sharp_bookmakers is None:
            sharp_bookmakers = ["pinnacle", "betfair_exchange", "sbobet"]
        
        match_odds = self.current_odds.get(match_id, {})
        fair_odds = {}
        
        for key, odds_list in match_odds.items():
            if not odds_list:
                continue
            
            if market and odds_list[0].market != market:
                continue
            
            selection = odds_list[0].selection
            
            # Get sharp bookmaker odds
            sharp_odds = [
                o.odds for o in odds_list
                if o.bookmaker.lower() in [b.lower() for b in sharp_bookmakers]
            ]
            
            if sharp_odds:
                # Use average of sharp odds as fair odds
                fair_odds[selection] = round(np.mean(sharp_odds), 3)
            else:
                # Fallback to average of all odds
                fair_odds[selection] = round(np.mean([o.odds for o in odds_list]), 3)
        
        return fair_odds
    
    def export_comparison(
        self,
        match_id: str,
        match_name: str
    ) -> Dict:
        """Export complete odds comparison for a match."""
        comparisons = self.compare_odds(match_id, match_name)
        arbitrage = self.detect_arbitrage(match_id, match_name)
        
        # Group by market
        markets = defaultdict(list)
        for comp in comparisons:
            markets[comp.market].append({
                "selection": comp.selection,
                "best_odds": comp.best_odds,
                "best_bookmaker": comp.best_bookmaker,
                "worst_odds": comp.worst_odds,
                "average_odds": comp.average_odds,
                "edge_vs_average": comp.edge_vs_average,
                "all_bookmakers": [
                    {"bookmaker": o.bookmaker, "odds": o.odds}
                    for o in comp.all_odds
                ]
            })
        
        return {
            "match": match_name,
            "timestamp": datetime.now().isoformat(),
            "markets": dict(markets),
            "arbitrage_opportunities": [
                {
                    "market": a.market,
                    "profit_percent": a.profit_percentage,
                    "selections": a.selections
                }
                for a in arbitrage
            ],
            "overround_by_market": {
                market: self.calculate_overround(match_id, market)
                for market in markets.keys()
            }
        }
