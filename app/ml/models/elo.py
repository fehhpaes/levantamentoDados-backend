"""
ELO Rating System for Sports Teams

Implements the ELO rating system adapted for sports predictions,
with adjustments for margin of victory, home advantage, and league strength.
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MatchResult(Enum):
    HOME_WIN = 1.0
    DRAW = 0.5
    AWAY_WIN = 0.0


@dataclass
class ELORating:
    """Team ELO rating data."""
    team_id: int
    team_name: str
    rating: float
    peak_rating: float
    lowest_rating: float
    matches_played: int
    last_updated: datetime
    history: List[Tuple[datetime, float]] = field(default_factory=list)


@dataclass
class ELOPrediction:
    """Prediction result from ELO model."""
    home_team: str
    away_team: str
    home_rating: float
    away_rating: float
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    expected_home_score: float
    expected_away_score: float
    rating_diff: float
    confidence: float


class ELOSystem:
    """
    ELO Rating System adapted for sports predictions.
    
    Features:
    - K-factor adjustment based on match importance
    - Margin of victory multiplier
    - Home advantage adjustment
    - League strength multiplier
    - Historical rating tracking
    """
    
    DEFAULT_RATING = 1500
    
    def __init__(
        self,
        k_factor: float = 32,
        home_advantage: float = 100,
        draw_margin: float = 0.1,
        mov_multiplier: float = 1.0,
        league_multipliers: Optional[Dict[int, float]] = None
    ):
        """
        Initialize ELO system.
        
        Args:
            k_factor: Base K-factor for rating changes
            home_advantage: Rating points added for home team
            draw_margin: Probability margin for predicting draws
            mov_multiplier: Margin of victory impact multiplier
            league_multipliers: Multipliers for different league strengths
        """
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.draw_margin = draw_margin
        self.mov_multiplier = mov_multiplier
        self.league_multipliers = league_multipliers or {}
        self.ratings: Dict[int, ELORating] = {}
        
    def get_rating(self, team_id: int, team_name: str = "Unknown") -> ELORating:
        """Get or create rating for a team."""
        if team_id not in self.ratings:
            now = datetime.now()
            self.ratings[team_id] = ELORating(
                team_id=team_id,
                team_name=team_name,
                rating=self.DEFAULT_RATING,
                peak_rating=self.DEFAULT_RATING,
                lowest_rating=self.DEFAULT_RATING,
                matches_played=0,
                last_updated=now,
                history=[(now, self.DEFAULT_RATING)]
            )
        return self.ratings[team_id]
    
    def expected_score(
        self,
        rating_a: float,
        rating_b: float,
        home_advantage: bool = True
    ) -> float:
        """
        Calculate expected score for team A against team B.
        
        Args:
            rating_a: Team A's ELO rating
            rating_b: Team B's ELO rating
            home_advantage: Whether team A has home advantage
            
        Returns:
            Expected score between 0 and 1
        """
        if home_advantage:
            rating_a += self.home_advantage
            
        return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))
    
    def calculate_k_factor(
        self,
        base_k: float,
        rating: float,
        match_importance: float = 1.0,
        matches_played: int = 0
    ) -> float:
        """
        Calculate adjusted K-factor based on various factors.
        
        Args:
            base_k: Base K-factor
            rating: Current team rating
            match_importance: Importance multiplier (playoffs, finals, etc.)
            matches_played: Number of matches played
            
        Returns:
            Adjusted K-factor
        """
        # Higher K for new teams (provisional period)
        if matches_played < 20:
            k = base_k * 1.5
        elif matches_played < 50:
            k = base_k * 1.2
        else:
            k = base_k
        
        # Lower K for very high rated teams (more stable)
        if rating > 2000:
            k *= 0.8
        elif rating > 1800:
            k *= 0.9
            
        # Apply match importance
        k *= match_importance
        
        return k
    
    def margin_of_victory_multiplier(
        self,
        goal_diff: int,
        elo_diff: float
    ) -> float:
        """
        Calculate margin of victory multiplier.
        
        Larger victories result in larger rating changes,
        but diminishing returns for very large margins.
        
        Args:
            goal_diff: Absolute goal difference
            elo_diff: ELO rating difference (winner - loser)
            
        Returns:
            Multiplier for K-factor
        """
        if goal_diff <= 1:
            return 1.0
        
        # Autocorrelation adjustment
        # Prevents excessive changes when favorite wins big
        if elo_diff > 0:
            autocorr = 2.2 / ((elo_diff * 0.001) + 2.2)
        else:
            autocorr = 1.0
            
        return math.log(goal_diff + 1) * self.mov_multiplier * autocorr
    
    def update_ratings(
        self,
        home_team_id: int,
        away_team_id: int,
        home_score: int,
        away_score: int,
        match_date: Optional[datetime] = None,
        match_importance: float = 1.0,
        league_id: Optional[int] = None,
        home_team_name: str = "Home",
        away_team_name: str = "Away"
    ) -> Tuple[float, float]:
        """
        Update ratings after a match.
        
        Args:
            home_team_id: Home team identifier
            away_team_id: Away team identifier
            home_score: Home team score
            away_score: Away team score
            match_date: Date of match
            match_importance: Match importance multiplier
            league_id: League identifier for strength multiplier
            home_team_name: Home team name
            away_team_name: Away team name
            
        Returns:
            Tuple of (home_rating_change, away_rating_change)
        """
        if match_date is None:
            match_date = datetime.now()
            
        # Get current ratings
        home_rating = self.get_rating(home_team_id, home_team_name)
        away_rating = self.get_rating(away_team_id, away_team_name)
        
        # Calculate expected scores
        home_expected = self.expected_score(home_rating.rating, away_rating.rating, True)
        away_expected = 1 - home_expected
        
        # Determine actual result
        if home_score > away_score:
            home_actual = 1.0
            away_actual = 0.0
        elif home_score < away_score:
            home_actual = 0.0
            away_actual = 1.0
        else:
            home_actual = 0.5
            away_actual = 0.5
        
        # Calculate K-factors
        home_k = self.calculate_k_factor(
            self.k_factor, 
            home_rating.rating, 
            match_importance,
            home_rating.matches_played
        )
        away_k = self.calculate_k_factor(
            self.k_factor, 
            away_rating.rating, 
            match_importance,
            away_rating.matches_played
        )
        
        # Apply league multiplier
        if league_id and league_id in self.league_multipliers:
            league_mult = self.league_multipliers[league_id]
            home_k *= league_mult
            away_k *= league_mult
        
        # Calculate margin of victory multiplier
        goal_diff = abs(home_score - away_score)
        if home_score > away_score:
            elo_diff = home_rating.rating - away_rating.rating
        else:
            elo_diff = away_rating.rating - home_rating.rating
        mov_mult = self.margin_of_victory_multiplier(goal_diff, elo_diff)
        
        # Calculate rating changes
        home_change = home_k * mov_mult * (home_actual - home_expected)
        away_change = away_k * mov_mult * (away_actual - away_expected)
        
        # Update ratings
        new_home_rating = home_rating.rating + home_change
        new_away_rating = away_rating.rating + away_change
        
        # Update home team
        home_rating.rating = new_home_rating
        home_rating.matches_played += 1
        home_rating.last_updated = match_date
        home_rating.peak_rating = max(home_rating.peak_rating, new_home_rating)
        home_rating.lowest_rating = min(home_rating.lowest_rating, new_home_rating)
        home_rating.history.append((match_date, new_home_rating))
        
        # Update away team
        away_rating.rating = new_away_rating
        away_rating.matches_played += 1
        away_rating.last_updated = match_date
        away_rating.peak_rating = max(away_rating.peak_rating, new_away_rating)
        away_rating.lowest_rating = min(away_rating.lowest_rating, new_away_rating)
        away_rating.history.append((match_date, new_away_rating))
        
        return home_change, away_change
    
    def predict_match(
        self,
        home_team_id: int,
        away_team_id: int,
        home_team_name: str = "Home",
        away_team_name: str = "Away"
    ) -> ELOPrediction:
        """
        Predict match outcome using ELO ratings.
        
        Args:
            home_team_id: Home team identifier
            away_team_id: Away team identifier
            home_team_name: Home team name
            away_team_name: Away team name
            
        Returns:
            ELOPrediction with probabilities
        """
        home_rating = self.get_rating(home_team_id, home_team_name)
        away_rating = self.get_rating(away_team_id, away_team_name)
        
        # Calculate win probability for home team
        home_win_base = self.expected_score(home_rating.rating, away_rating.rating, True)
        
        # Adjust for draws (football-style)
        # Higher draw probability when teams are evenly matched
        rating_diff = abs(home_rating.rating - away_rating.rating + self.home_advantage)
        draw_adjustment = self.draw_margin * math.exp(-rating_diff / 400)
        
        # Distribute probabilities
        if home_win_base > 0.5:
            home_win_prob = home_win_base - draw_adjustment / 2
            away_win_prob = (1 - home_win_base) - draw_adjustment / 2
        else:
            home_win_prob = home_win_base - draw_adjustment / 2
            away_win_prob = (1 - home_win_base) - draw_adjustment / 2
        
        draw_prob = 1 - home_win_prob - away_win_prob
        
        # Ensure valid probabilities
        home_win_prob = max(0.01, min(0.98, home_win_prob))
        away_win_prob = max(0.01, min(0.98, away_win_prob))
        draw_prob = max(0.01, 1 - home_win_prob - away_win_prob)
        
        # Normalize
        total = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total
        
        # Estimate expected goals based on rating difference
        rating_diff_normalized = (home_rating.rating + self.home_advantage - away_rating.rating) / 400
        expected_home = 1.5 + rating_diff_normalized * 0.5
        expected_away = 1.2 - rating_diff_normalized * 0.4
        expected_home = max(0.5, min(4.0, expected_home))
        expected_away = max(0.3, min(3.5, expected_away))
        
        # Calculate confidence based on matches played
        min_matches = min(home_rating.matches_played, away_rating.matches_played)
        confidence = min(1.0, min_matches / 20)
        
        return ELOPrediction(
            home_team=home_team_name,
            away_team=away_team_name,
            home_rating=round(home_rating.rating, 1),
            away_rating=round(away_rating.rating, 1),
            home_win_prob=round(home_win_prob, 4),
            draw_prob=round(draw_prob, 4),
            away_win_prob=round(away_win_prob, 4),
            expected_home_score=round(expected_home, 2),
            expected_away_score=round(expected_away, 2),
            rating_diff=round(home_rating.rating - away_rating.rating, 1),
            confidence=round(confidence, 2)
        )
    
    def get_rankings(
        self,
        league_id: Optional[int] = None,
        top_n: Optional[int] = None
    ) -> List[Dict]:
        """
        Get team rankings based on ELO ratings.
        
        Args:
            league_id: Filter by league (not implemented yet)
            top_n: Return only top N teams
            
        Returns:
            List of team rankings
        """
        rankings = sorted(
            self.ratings.values(),
            key=lambda x: x.rating,
            reverse=True
        )
        
        if top_n:
            rankings = rankings[:top_n]
        
        return [
            {
                "rank": i + 1,
                "team_id": r.team_id,
                "team_name": r.team_name,
                "rating": round(r.rating, 1),
                "peak_rating": round(r.peak_rating, 1),
                "matches_played": r.matches_played,
                "last_updated": r.last_updated.isoformat()
            }
            for i, r in enumerate(rankings)
        ]
    
    def batch_process_matches(
        self,
        matches: List[Dict],
        reset_ratings: bool = False
    ) -> Dict[str, any]:
        """
        Process a batch of historical matches to build ratings.
        
        Args:
            matches: List of matches sorted by date
            reset_ratings: Whether to reset all ratings before processing
            
        Returns:
            Summary of processing results
        """
        if reset_ratings:
            self.ratings = {}
        
        processed = 0
        errors = 0
        
        # Sort by date
        sorted_matches = sorted(
            matches,
            key=lambda x: x.get("date", datetime.min)
        )
        
        for match in sorted_matches:
            try:
                self.update_ratings(
                    home_team_id=match["home_team_id"],
                    away_team_id=match["away_team_id"],
                    home_score=match["home_score"],
                    away_score=match["away_score"],
                    match_date=match.get("date"),
                    match_importance=match.get("importance", 1.0),
                    league_id=match.get("league_id"),
                    home_team_name=match.get("home_team_name", "Home"),
                    away_team_name=match.get("away_team_name", "Away")
                )
                processed += 1
            except Exception as e:
                logger.error(f"Error processing match: {e}")
                errors += 1
        
        return {
            "processed": processed,
            "errors": errors,
            "total_teams": len(self.ratings),
            "top_teams": self.get_rankings(top_n=10)
        }
    
    def to_dict(self, prediction: ELOPrediction) -> Dict:
        """Convert prediction to dictionary format."""
        return {
            "home_team": prediction.home_team,
            "away_team": prediction.away_team,
            "ratings": {
                "home": prediction.home_rating,
                "away": prediction.away_rating,
                "difference": prediction.rating_diff
            },
            "probabilities": {
                "home_win": prediction.home_win_prob,
                "draw": prediction.draw_prob,
                "away_win": prediction.away_win_prob
            },
            "expected_score": {
                "home": prediction.expected_home_score,
                "away": prediction.expected_away_score
            },
            "confidence": prediction.confidence
        }
    
    def export_ratings(self) -> List[Dict]:
        """Export all ratings as list of dictionaries."""
        return [
            {
                "team_id": r.team_id,
                "team_name": r.team_name,
                "rating": round(r.rating, 1),
                "peak_rating": round(r.peak_rating, 1),
                "lowest_rating": round(r.lowest_rating, 1),
                "matches_played": r.matches_played,
                "last_updated": r.last_updated.isoformat(),
                "rating_history": [
                    {"date": h[0].isoformat(), "rating": round(h[1], 1)}
                    for h in r.history[-10:]  # Last 10 entries
                ]
            }
            for r in self.ratings.values()
        ]
