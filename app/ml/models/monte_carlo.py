"""
Monte Carlo Simulation for Sports Predictions

Uses Monte Carlo methods to simulate thousands of match outcomes
and tournament progressions for probability estimation.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    """Result of a single match simulation."""
    home_score: int
    away_score: int
    outcome: str  # "H", "D", "A"


@dataclass
class MatchSimulationSummary:
    """Summary of Monte Carlo simulations for a match."""
    home_team: str
    away_team: str
    n_simulations: int
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    avg_home_goals: float
    avg_away_goals: float
    std_home_goals: float
    std_away_goals: float
    score_distribution: Dict[str, float]
    over_under_probs: Dict[str, float]
    btts_prob: float
    confidence_interval: Dict[str, Tuple[float, float]]


@dataclass
class TournamentSimulation:
    """Result of tournament Monte Carlo simulation."""
    team_probabilities: Dict[str, Dict[str, float]]
    most_likely_winner: str
    winner_probability: float
    final_standings: List[Dict]
    n_simulations: int


@dataclass
class SeasonSimulation:
    """Result of season Monte Carlo simulation."""
    title_probabilities: Dict[str, float]
    relegation_probabilities: Dict[str, float]
    top4_probabilities: Dict[str, float]
    expected_points: Dict[str, float]
    points_distribution: Dict[str, Dict[int, float]]
    n_simulations: int


class GoalDistribution:
    """
    Goal distribution models for Monte Carlo simulation.
    """
    
    @staticmethod
    def poisson(expected_goals: float) -> int:
        """Generate goals using Poisson distribution."""
        return np.random.poisson(expected_goals)
    
    @staticmethod
    def negative_binomial(expected_goals: float, variance_factor: float = 1.5) -> int:
        """
        Generate goals using Negative Binomial distribution.
        
        Better for high-scoring sports or when variance > mean.
        """
        if expected_goals <= 0:
            return 0
        
        # Calculate parameters
        p = expected_goals / (expected_goals * variance_factor)
        r = expected_goals * p / (1 - p)
        
        if r <= 0:
            return np.random.poisson(expected_goals)
        
        return int(np.random.negative_binomial(r, p))
    
    @staticmethod
    def zero_inflated_poisson(
        expected_goals: float,
        zero_inflation: float = 0.1
    ) -> int:
        """
        Generate goals with zero-inflated Poisson.
        
        Accounts for teams that often fail to score.
        """
        if np.random.random() < zero_inflation:
            return 0
        return np.random.poisson(expected_goals / (1 - zero_inflation))


class MonteCarloSimulator:
    """
    Monte Carlo simulation engine for sports predictions.
    
    Features:
    - Match outcome simulation
    - Score distribution analysis
    - Tournament progression simulation
    - Season-long simulation
    - Parallel processing support
    """
    
    def __init__(
        self,
        n_simulations: int = 10000,
        distribution: str = "poisson",
        random_seed: Optional[int] = None,
        use_parallel: bool = True,
        n_workers: Optional[int] = None
    ):
        """
        Initialize Monte Carlo simulator.
        
        Args:
            n_simulations: Number of simulations to run
            distribution: Goal distribution ("poisson", "negative_binomial", "zip")
            random_seed: Random seed for reproducibility
            use_parallel: Whether to use parallel processing
            n_workers: Number of parallel workers
        """
        self.n_simulations = n_simulations
        self.distribution = distribution
        self.random_seed = random_seed
        self.use_parallel = use_parallel
        self.n_workers = n_workers or max(1, multiprocessing.cpu_count() - 1)
        
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # Select distribution function
        self.goal_func = {
            "poisson": GoalDistribution.poisson,
            "negative_binomial": GoalDistribution.negative_binomial,
            "zip": GoalDistribution.zero_inflated_poisson
        }.get(distribution, GoalDistribution.poisson)
    
    def simulate_match(
        self,
        home_expected: float,
        away_expected: float
    ) -> SimulationResult:
        """
        Simulate a single match.
        
        Args:
            home_expected: Expected goals for home team
            away_expected: Expected goals for away team
            
        Returns:
            SimulationResult with scores and outcome
        """
        home_score = self.goal_func(home_expected)
        away_score = self.goal_func(away_expected)
        
        if home_score > away_score:
            outcome = "H"
        elif home_score < away_score:
            outcome = "A"
        else:
            outcome = "D"
        
        return SimulationResult(
            home_score=home_score,
            away_score=away_score,
            outcome=outcome
        )
    
    def simulate_match_batch(
        self,
        home_expected: float,
        away_expected: float,
        n_sims: int
    ) -> List[SimulationResult]:
        """Simulate multiple matches (for parallel processing)."""
        return [
            self.simulate_match(home_expected, away_expected)
            for _ in range(n_sims)
        ]
    
    def run_match_simulation(
        self,
        home_expected: float,
        away_expected: float,
        home_team: str = "Home",
        away_team: str = "Away"
    ) -> MatchSimulationSummary:
        """
        Run Monte Carlo simulation for a match.
        
        Args:
            home_expected: Expected goals for home team
            away_expected: Expected goals for away team
            home_team: Home team name
            away_team: Away team name
            
        Returns:
            MatchSimulationSummary with probabilities
        """
        results = []
        
        if self.use_parallel and self.n_simulations > 1000:
            # Split work across workers
            batch_size = self.n_simulations // self.n_workers
            
            with ThreadPoolExecutor(max_workers=self.n_workers) as executor:
                futures = [
                    executor.submit(
                        self.simulate_match_batch,
                        home_expected,
                        away_expected,
                        batch_size
                    )
                    for _ in range(self.n_workers)
                ]
                
                for future in futures:
                    results.extend(future.result())
        else:
            results = [
                self.simulate_match(home_expected, away_expected)
                for _ in range(self.n_simulations)
            ]
        
        # Analyze results
        home_wins = sum(1 for r in results if r.outcome == "H")
        draws = sum(1 for r in results if r.outcome == "D")
        away_wins = sum(1 for r in results if r.outcome == "A")
        
        home_goals = [r.home_score for r in results]
        away_goals = [r.away_score for r in results]
        
        # Score distribution
        score_counts = {}
        for r in results:
            score = f"{r.home_score}-{r.away_score}"
            score_counts[score] = score_counts.get(score, 0) + 1
        
        score_distribution = {
            k: v / self.n_simulations
            for k, v in sorted(
                score_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:15]  # Top 15 scores
        }
        
        # Over/Under calculations
        total_goals = [r.home_score + r.away_score for r in results]
        over_under = {
            "over_0_5": sum(1 for g in total_goals if g > 0) / self.n_simulations,
            "over_1_5": sum(1 for g in total_goals if g > 1) / self.n_simulations,
            "over_2_5": sum(1 for g in total_goals if g > 2) / self.n_simulations,
            "over_3_5": sum(1 for g in total_goals if g > 3) / self.n_simulations,
            "over_4_5": sum(1 for g in total_goals if g > 4) / self.n_simulations,
        }
        
        # BTTS
        btts = sum(
            1 for r in results if r.home_score > 0 and r.away_score > 0
        ) / self.n_simulations
        
        # Confidence intervals (95%)
        n = self.n_simulations
        home_win_prob = home_wins / n
        
        def wilson_interval(p: float, n: int, z: float = 1.96) -> Tuple[float, float]:
            """Wilson score interval for confidence."""
            denominator = 1 + z**2 / n
            center = (p + z**2 / (2 * n)) / denominator
            margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denominator
            return (max(0, center - margin), min(1, center + margin))
        
        return MatchSimulationSummary(
            home_team=home_team,
            away_team=away_team,
            n_simulations=self.n_simulations,
            home_win_prob=round(home_wins / n, 4),
            draw_prob=round(draws / n, 4),
            away_win_prob=round(away_wins / n, 4),
            avg_home_goals=round(np.mean(home_goals), 2),
            avg_away_goals=round(np.mean(away_goals), 2),
            std_home_goals=round(np.std(home_goals), 2),
            std_away_goals=round(np.std(away_goals), 2),
            score_distribution=score_distribution,
            over_under_probs=over_under,
            btts_prob=round(btts, 4),
            confidence_interval={
                "home_win": wilson_interval(home_wins / n, n),
                "draw": wilson_interval(draws / n, n),
                "away_win": wilson_interval(away_wins / n, n)
            }
        )
    
    def simulate_knockout_round(
        self,
        matchups: List[Tuple[Dict, Dict, float, float]],
        two_legs: bool = False
    ) -> List[Dict]:
        """
        Simulate a knockout round.
        
        Args:
            matchups: List of (team1, team2, team1_expected, team2_expected)
            two_legs: Whether matches are two-legged
            
        Returns:
            List of winners
        """
        winners = []
        
        for team1, team2, exp1, exp2 in matchups:
            if two_legs:
                # First leg
                result1 = self.simulate_match(exp1, exp2)
                # Second leg (reverse home/away)
                result2 = self.simulate_match(exp2 * 0.9, exp1 * 0.9)  # Slight home adjustment
                
                agg1 = result1.home_score + result2.away_score
                agg2 = result1.away_score + result2.home_score
                
                if agg1 > agg2:
                    winners.append(team1)
                elif agg2 > agg1:
                    winners.append(team2)
                else:
                    # Away goals rule (simplified)
                    if result2.away_score > result1.away_score:
                        winners.append(team1)
                    elif result1.away_score > result2.away_score:
                        winners.append(team2)
                    else:
                        # Random (penalty shootout)
                        winners.append(team1 if np.random.random() > 0.5 else team2)
            else:
                result = self.simulate_match(exp1, exp2)
                if result.outcome == "H":
                    winners.append(team1)
                elif result.outcome == "A":
                    winners.append(team2)
                else:
                    # Extra time + penalties (simplified)
                    winners.append(team1 if np.random.random() > 0.5 else team2)
        
        return winners
    
    def simulate_tournament(
        self,
        teams: List[Dict],
        expected_goals: Dict[int, Tuple[float, float]],
        format: str = "knockout"
    ) -> TournamentSimulation:
        """
        Simulate a tournament multiple times.
        
        Args:
            teams: List of team dictionaries with id, name
            expected_goals: Dict mapping team_id to (attack, defense) strengths
            format: Tournament format ("knockout", "group_knockout")
            
        Returns:
            TournamentSimulation with probabilities
        """
        winner_counts = {t["name"]: 0 for t in teams}
        final_counts = {t["name"]: 0 for t in teams}
        semi_counts = {t["name"]: 0 for t in teams}
        
        for _ in range(self.n_simulations):
            remaining = teams.copy()
            
            # Simulate rounds until we have a winner
            while len(remaining) > 1:
                matchups = []
                for i in range(0, len(remaining), 2):
                    if i + 1 < len(remaining):
                        t1, t2 = remaining[i], remaining[i + 1]
                        atk1, def1 = expected_goals.get(t1["id"], (1.5, 1.2))
                        atk2, def2 = expected_goals.get(t2["id"], (1.5, 1.2))
                        
                        exp1 = atk1 * def2 / 1.5
                        exp2 = atk2 * def1 / 1.5
                        
                        matchups.append((t1, t2, exp1, exp2))
                    else:
                        # Bye
                        matchups.append((remaining[i], remaining[i], 0, 0))
                
                # Track semi-finalists
                if len(remaining) == 4:
                    for t in remaining:
                        semi_counts[t["name"]] += 1
                
                # Track finalists
                if len(remaining) == 2:
                    for t in remaining:
                        final_counts[t["name"]] += 1
                
                remaining = self.simulate_knockout_round(matchups)
            
            if remaining:
                winner_counts[remaining[0]["name"]] += 1
        
        # Calculate probabilities
        n = self.n_simulations
        team_probs = {
            name: {
                "winner": winner_counts[name] / n,
                "finalist": final_counts[name] / n,
                "semi_finalist": semi_counts[name] / n
            }
            for name in winner_counts
        }
        
        most_likely = max(winner_counts, key=winner_counts.get)
        
        return TournamentSimulation(
            team_probabilities=team_probs,
            most_likely_winner=most_likely,
            winner_probability=winner_counts[most_likely] / n,
            final_standings=sorted(
                [{"team": k, "wins": v} for k, v in winner_counts.items()],
                key=lambda x: x["wins"],
                reverse=True
            ),
            n_simulations=self.n_simulations
        )
    
    def simulate_league_season(
        self,
        teams: List[Dict],
        fixtures: List[Dict],
        expected_goals_func: Callable[[int, int], Tuple[float, float]],
        points_system: Tuple[int, int, int] = (3, 1, 0)
    ) -> SeasonSimulation:
        """
        Simulate a league season multiple times.
        
        Args:
            teams: List of team dictionaries
            fixtures: Remaining fixtures
            expected_goals_func: Function(home_id, away_id) -> (home_exp, away_exp)
            points_system: Points for (win, draw, loss)
            
        Returns:
            SeasonSimulation with probabilities
        """
        team_names = {t["id"]: t["name"] for t in teams}
        
        title_counts = {t["name"]: 0 for t in teams}
        top4_counts = {t["name"]: 0 for t in teams}
        relegation_counts = {t["name"]: 0 for t in teams}
        points_totals = {t["name"]: [] for t in teams}
        
        for _ in range(self.n_simulations):
            # Initialize points (could add current standings)
            points = {t["id"]: t.get("current_points", 0) for t in teams}
            
            # Simulate remaining fixtures
            for fixture in fixtures:
                home_id = fixture["home_team_id"]
                away_id = fixture["away_team_id"]
                
                home_exp, away_exp = expected_goals_func(home_id, away_id)
                result = self.simulate_match(home_exp, away_exp)
                
                if result.outcome == "H":
                    points[home_id] += points_system[0]
                    points[away_id] += points_system[2]
                elif result.outcome == "D":
                    points[home_id] += points_system[1]
                    points[away_id] += points_system[1]
                else:
                    points[home_id] += points_system[2]
                    points[away_id] += points_system[0]
            
            # Sort by points
            final_standings = sorted(
                points.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Record results
            for i, (team_id, pts) in enumerate(final_standings):
                name = team_names[team_id]
                points_totals[name].append(pts)
                
                if i == 0:
                    title_counts[name] += 1
                if i < 4:
                    top4_counts[name] += 1
                if i >= len(teams) - 3:
                    relegation_counts[name] += 1
        
        # Calculate probabilities
        n = self.n_simulations
        
        # Points distribution
        points_dist = {}
        for name, pts_list in points_totals.items():
            pts_counts = {}
            for pts in pts_list:
                pts_counts[pts] = pts_counts.get(pts, 0) + 1
            points_dist[name] = {
                pts: count / n for pts, count in pts_counts.items()
            }
        
        return SeasonSimulation(
            title_probabilities={name: count / n for name, count in title_counts.items()},
            relegation_probabilities={name: count / n for name, count in relegation_counts.items()},
            top4_probabilities={name: count / n for name, count in top4_counts.items()},
            expected_points={
                name: round(np.mean(pts_list), 1)
                for name, pts_list in points_totals.items()
            },
            points_distribution=points_dist,
            n_simulations=self.n_simulations
        )
    
    def calculate_value_bet(
        self,
        simulation: MatchSimulationSummary,
        odds: Dict[str, float],
        min_edge: float = 0.05,
        kelly_fraction: float = 0.25
    ) -> Dict[str, any]:
        """
        Identify value bets from simulation results.
        
        Args:
            simulation: Match simulation results
            odds: Bookmaker odds
            min_edge: Minimum edge required
            kelly_fraction: Kelly criterion fraction to use
            
        Returns:
            Value bet opportunities
        """
        value_bets = []
        
        markets = {
            "home_win": simulation.home_win_prob,
            "draw": simulation.draw_prob,
            "away_win": simulation.away_win_prob,
            "over_2_5": simulation.over_under_probs["over_2_5"],
            "under_2_5": 1 - simulation.over_under_probs["over_2_5"],
            "btts_yes": simulation.btts_prob,
            "btts_no": 1 - simulation.btts_prob
        }
        
        for market, sim_prob in markets.items():
            if market in odds:
                implied_prob = 1 / odds[market]
                edge = sim_prob - implied_prob
                
                if edge >= min_edge:
                    # Kelly criterion
                    kelly = (sim_prob * odds[market] - 1) / (odds[market] - 1)
                    recommended_stake = kelly * kelly_fraction
                    
                    # Use confidence interval for risk assessment
                    ci_key = market.replace("_win", "_win").replace("_yes", "").replace("_no", "")
                    if ci_key in simulation.confidence_interval:
                        ci = simulation.confidence_interval[ci_key]
                        lower_edge = ci[0] - implied_prob
                    else:
                        lower_edge = edge * 0.7
                    
                    value_bets.append({
                        "market": market,
                        "odds": odds[market],
                        "simulation_probability": round(sim_prob, 4),
                        "implied_probability": round(implied_prob, 4),
                        "edge": round(edge, 4),
                        "lower_bound_edge": round(lower_edge, 4),
                        "kelly_stake": round(recommended_stake, 4),
                        "expected_value": round(sim_prob * odds[market] - 1, 4),
                        "simulations": simulation.n_simulations
                    })
        
        return {
            "match": f"{simulation.home_team} vs {simulation.away_team}",
            "value_bets": sorted(value_bets, key=lambda x: x["edge"], reverse=True),
            "has_value": len(value_bets) > 0
        }
    
    def to_dict(self, summary: MatchSimulationSummary) -> Dict:
        """Convert simulation summary to dictionary."""
        return {
            "match": f"{summary.home_team} vs {summary.away_team}",
            "simulations": summary.n_simulations,
            "probabilities": {
                "home_win": summary.home_win_prob,
                "draw": summary.draw_prob,
                "away_win": summary.away_win_prob
            },
            "expected_goals": {
                "home": summary.avg_home_goals,
                "away": summary.avg_away_goals
            },
            "goal_variance": {
                "home": summary.std_home_goals,
                "away": summary.std_away_goals
            },
            "over_under": summary.over_under_probs,
            "btts": summary.btts_prob,
            "most_likely_scores": list(summary.score_distribution.items())[:5],
            "confidence_intervals": {
                k: {"lower": round(v[0], 4), "upper": round(v[1], 4)}
                for k, v in summary.confidence_interval.items()
            }
        }
