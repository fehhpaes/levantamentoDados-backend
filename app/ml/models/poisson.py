"""
Poisson Distribution Model for Goal/Score Predictions

This model uses the Poisson distribution to predict the probability
of different scorelines in sports matches, particularly football.
"""

import numpy as np
from scipy.stats import poisson
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class TeamStats:
    """Statistics for a team's attack and defense."""
    team_id: int
    team_name: str
    goals_scored: float
    goals_conceded: float
    matches_played: int
    attack_strength: float = 0.0
    defense_strength: float = 0.0
    home_attack: float = 0.0
    home_defense: float = 0.0
    away_attack: float = 0.0
    away_defense: float = 0.0


@dataclass
class PoissonPrediction:
    """Prediction result from Poisson model."""
    home_team: str
    away_team: str
    home_expected_goals: float
    away_expected_goals: float
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    over_2_5_prob: float
    under_2_5_prob: float
    btts_prob: float  # Both teams to score
    score_matrix: np.ndarray
    most_likely_scores: List[Tuple[int, int, float]]
    confidence: float


class PoissonModel:
    """
    Poisson Distribution Model for predicting match outcomes.
    
    Uses historical data to calculate attack and defense strengths,
    then applies Poisson distribution to predict goal probabilities.
    """
    
    def __init__(
        self,
        max_goals: int = 10,
        time_decay: float = 0.95,
        home_advantage: float = 1.2,
        min_matches: int = 5
    ):
        """
        Initialize the Poisson model.
        
        Args:
            max_goals: Maximum goals to consider in predictions
            time_decay: Weight decay for older matches (per month)
            home_advantage: Multiplier for home team attack strength
            min_matches: Minimum matches required for reliable prediction
        """
        self.max_goals = max_goals
        self.time_decay = time_decay
        self.home_advantage = home_advantage
        self.min_matches = min_matches
        self.league_avg_goals: Dict[int, float] = {}
        self.team_stats: Dict[int, TeamStats] = {}
        
    def calculate_league_averages(
        self,
        matches: List[Dict],
        league_id: int
    ) -> Dict[str, float]:
        """
        Calculate league average goals for home and away teams.
        
        Args:
            matches: List of historical matches
            league_id: League identifier
            
        Returns:
            Dictionary with home_avg and away_avg goals
        """
        if not matches:
            return {"home_avg": 1.5, "away_avg": 1.2}
        
        home_goals = []
        away_goals = []
        
        for match in matches:
            if match.get("home_score") is not None and match.get("away_score") is not None:
                home_goals.append(match["home_score"])
                away_goals.append(match["away_score"])
        
        if not home_goals:
            return {"home_avg": 1.5, "away_avg": 1.2}
            
        avg = {
            "home_avg": np.mean(home_goals),
            "away_avg": np.mean(away_goals),
            "total_avg": np.mean(home_goals) + np.mean(away_goals)
        }
        
        self.league_avg_goals[league_id] = avg["total_avg"] / 2
        return avg
    
    def calculate_team_strength(
        self,
        matches: List[Dict],
        team_id: int,
        league_avg: Dict[str, float],
        reference_date: Optional[datetime] = None
    ) -> TeamStats:
        """
        Calculate attack and defense strength for a team.
        
        Uses time-weighted averages to give more importance to recent matches.
        
        Args:
            matches: Team's historical matches
            team_id: Team identifier
            league_avg: League average goals
            reference_date: Date to calculate time decay from
            
        Returns:
            TeamStats with calculated strengths
        """
        if reference_date is None:
            reference_date = datetime.now()
            
        home_scored = []
        home_conceded = []
        away_scored = []
        away_conceded = []
        weights = []
        
        team_name = ""
        
        for match in matches:
            match_date = match.get("date")
            if isinstance(match_date, str):
                match_date = datetime.fromisoformat(match_date)
            
            # Calculate time decay weight
            if match_date:
                months_ago = (reference_date - match_date).days / 30
                weight = self.time_decay ** months_ago
            else:
                weight = 0.5
            
            if match.get("home_team_id") == team_id:
                team_name = match.get("home_team_name", "Unknown")
                if match.get("home_score") is not None:
                    home_scored.append((match["home_score"], weight))
                    home_conceded.append((match["away_score"], weight))
            elif match.get("away_team_id") == team_id:
                team_name = match.get("away_team_name", "Unknown")
                if match.get("away_score") is not None:
                    away_scored.append((match["away_score"], weight))
                    away_conceded.append((match["home_score"], weight))
        
        # Calculate weighted averages
        def weighted_avg(data: List[Tuple[float, float]]) -> float:
            if not data:
                return 0.0
            total_weight = sum(w for _, w in data)
            if total_weight == 0:
                return 0.0
            return sum(v * w for v, w in data) / total_weight
        
        home_avg_scored = weighted_avg(home_scored) if home_scored else league_avg["home_avg"]
        home_avg_conceded = weighted_avg(home_conceded) if home_conceded else league_avg["away_avg"]
        away_avg_scored = weighted_avg(away_scored) if away_scored else league_avg["away_avg"]
        away_avg_conceded = weighted_avg(away_conceded) if away_conceded else league_avg["home_avg"]
        
        # Calculate attack and defense strengths relative to league average
        stats = TeamStats(
            team_id=team_id,
            team_name=team_name,
            goals_scored=home_avg_scored + away_avg_scored,
            goals_conceded=home_avg_conceded + away_avg_conceded,
            matches_played=len(home_scored) + len(away_scored),
            attack_strength=(home_avg_scored / league_avg["home_avg"] + 
                           away_avg_scored / league_avg["away_avg"]) / 2 if league_avg["home_avg"] > 0 else 1.0,
            defense_strength=(home_avg_conceded / league_avg["away_avg"] + 
                            away_avg_conceded / league_avg["home_avg"]) / 2 if league_avg["away_avg"] > 0 else 1.0,
            home_attack=home_avg_scored / league_avg["home_avg"] if league_avg["home_avg"] > 0 else 1.0,
            home_defense=home_avg_conceded / league_avg["away_avg"] if league_avg["away_avg"] > 0 else 1.0,
            away_attack=away_avg_scored / league_avg["away_avg"] if league_avg["away_avg"] > 0 else 1.0,
            away_defense=away_avg_conceded / league_avg["home_avg"] if league_avg["home_avg"] > 0 else 1.0
        )
        
        self.team_stats[team_id] = stats
        return stats
    
    def predict_match(
        self,
        home_team_stats: TeamStats,
        away_team_stats: TeamStats,
        league_avg: Dict[str, float],
        neutral_venue: bool = False
    ) -> PoissonPrediction:
        """
        Predict match outcome using Poisson distribution.
        
        Args:
            home_team_stats: Home team statistics
            away_team_stats: Away team statistics
            league_avg: League average goals
            neutral_venue: Whether match is at neutral venue
            
        Returns:
            PoissonPrediction with probabilities
        """
        # Calculate expected goals
        home_advantage = 1.0 if neutral_venue else self.home_advantage
        
        home_expected = (
            home_team_stats.home_attack * 
            away_team_stats.away_defense * 
            league_avg["home_avg"] * 
            home_advantage
        )
        
        away_expected = (
            away_team_stats.away_attack * 
            home_team_stats.home_defense * 
            league_avg["away_avg"]
        )
        
        # Ensure reasonable bounds
        home_expected = max(0.1, min(5.0, home_expected))
        away_expected = max(0.1, min(5.0, away_expected))
        
        # Generate score probability matrix
        score_matrix = np.zeros((self.max_goals + 1, self.max_goals + 1))
        
        for i in range(self.max_goals + 1):
            for j in range(self.max_goals + 1):
                score_matrix[i, j] = (
                    poisson.pmf(i, home_expected) * 
                    poisson.pmf(j, away_expected)
                )
        
        # Calculate outcome probabilities
        home_win_prob = np.sum(np.tril(score_matrix, -1))
        draw_prob = np.sum(np.diag(score_matrix))
        away_win_prob = np.sum(np.triu(score_matrix, 1))
        
        # Over/Under probabilities
        over_2_5_prob = 0.0
        for i in range(self.max_goals + 1):
            for j in range(self.max_goals + 1):
                if i + j > 2:
                    over_2_5_prob += score_matrix[i, j]
        under_2_5_prob = 1 - over_2_5_prob
        
        # Both teams to score
        btts_prob = 0.0
        for i in range(1, self.max_goals + 1):
            for j in range(1, self.max_goals + 1):
                btts_prob += score_matrix[i, j]
        
        # Find most likely scores
        flat_indices = np.argsort(score_matrix.flatten())[::-1]
        most_likely = []
        for idx in flat_indices[:5]:
            i, j = divmod(idx, self.max_goals + 1)
            most_likely.append((i, j, score_matrix[i, j]))
        
        # Calculate confidence based on data quality
        total_matches = home_team_stats.matches_played + away_team_stats.matches_played
        confidence = min(1.0, total_matches / (2 * self.min_matches))
        
        return PoissonPrediction(
            home_team=home_team_stats.team_name,
            away_team=away_team_stats.team_name,
            home_expected_goals=round(home_expected, 2),
            away_expected_goals=round(away_expected, 2),
            home_win_prob=round(home_win_prob, 4),
            draw_prob=round(draw_prob, 4),
            away_win_prob=round(away_win_prob, 4),
            over_2_5_prob=round(over_2_5_prob, 4),
            under_2_5_prob=round(under_2_5_prob, 4),
            btts_prob=round(btts_prob, 4),
            score_matrix=score_matrix,
            most_likely_scores=most_likely,
            confidence=round(confidence, 2)
        )
    
    def calculate_value_bet(
        self,
        prediction: PoissonPrediction,
        odds: Dict[str, float],
        min_edge: float = 0.05
    ) -> Dict[str, any]:
        """
        Identify value bets by comparing model probabilities with bookmaker odds.
        
        Args:
            prediction: Model prediction
            odds: Bookmaker odds (1X2, over/under, btts)
            min_edge: Minimum edge required (5% default)
            
        Returns:
            Dictionary with value bet opportunities
        """
        value_bets = []
        
        # Convert odds to implied probabilities
        markets = {
            "home_win": ("home_win", prediction.home_win_prob),
            "draw": ("draw", prediction.draw_prob),
            "away_win": ("away_win", prediction.away_win_prob),
            "over_2_5": ("over_2_5", prediction.over_2_5_prob),
            "under_2_5": ("under_2_5", prediction.under_2_5_prob),
            "btts_yes": ("btts_yes", prediction.btts_prob),
            "btts_no": ("btts_no", 1 - prediction.btts_prob)
        }
        
        for market_key, (name, model_prob) in markets.items():
            if market_key in odds:
                implied_prob = 1 / odds[market_key]
                edge = model_prob - implied_prob
                
                if edge >= min_edge:
                    expected_value = (model_prob * odds[market_key]) - 1
                    kelly = edge / (odds[market_key] - 1) if odds[market_key] > 1 else 0
                    
                    value_bets.append({
                        "market": name,
                        "odds": odds[market_key],
                        "model_probability": round(model_prob, 4),
                        "implied_probability": round(implied_prob, 4),
                        "edge": round(edge, 4),
                        "expected_value": round(expected_value, 4),
                        "kelly_fraction": round(min(kelly, 0.25), 4),  # Cap at 25%
                        "confidence": prediction.confidence
                    })
        
        return {
            "match": f"{prediction.home_team} vs {prediction.away_team}",
            "value_bets": sorted(value_bets, key=lambda x: x["edge"], reverse=True),
            "has_value": len(value_bets) > 0
        }
    
    def to_dict(self, prediction: PoissonPrediction) -> Dict:
        """Convert prediction to dictionary format."""
        return {
            "home_team": prediction.home_team,
            "away_team": prediction.away_team,
            "expected_goals": {
                "home": prediction.home_expected_goals,
                "away": prediction.away_expected_goals
            },
            "probabilities": {
                "home_win": prediction.home_win_prob,
                "draw": prediction.draw_prob,
                "away_win": prediction.away_win_prob
            },
            "over_under": {
                "over_2_5": prediction.over_2_5_prob,
                "under_2_5": prediction.under_2_5_prob
            },
            "btts": prediction.btts_prob,
            "most_likely_scores": [
                {"home": s[0], "away": s[1], "probability": round(s[2], 4)}
                for s in prediction.most_likely_scores
            ],
            "confidence": prediction.confidence
        }
