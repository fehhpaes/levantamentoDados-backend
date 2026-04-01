"""
Ensemble Predictor combining multiple ML models.

Combines predictions from Poisson, ELO, XGBoost, LSTM, and Monte Carlo
for more robust and accurate predictions.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from .models.poisson import PoissonModel, PoissonPrediction
from .models.elo import ELOSystem, ELOPrediction
from .models.xgboost_model import XGBoostPredictor, XGBoostPrediction
from .models.lstm_model import LSTMPredictor, LSTMPrediction
from .models.monte_carlo import MonteCarloSimulator, MatchSimulationSummary

logger = logging.getLogger(__name__)


@dataclass
class EnsemblePrediction:
    """Combined prediction from all models."""
    home_team: str
    away_team: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_outcome: str
    predicted_home_goals: float
    predicted_away_goals: float
    over_2_5_prob: float
    btts_prob: float
    model_predictions: Dict[str, Dict]
    model_weights: Dict[str, float]
    confidence: float
    consensus_level: str  # "high", "medium", "low"
    value_bets: List[Dict]


class EnsemblePredictor:
    """
    Ensemble predictor combining multiple ML models.
    
    Features:
    - Weighted average of model predictions
    - Dynamic weight adjustment based on model confidence
    - Consensus analysis
    - Value bet identification across models
    """
    
    MODEL_NAMES = ["poisson", "elo", "xgboost", "lstm", "monte_carlo"]
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        use_dynamic_weights: bool = True,
        min_models: int = 2
    ):
        """
        Initialize ensemble predictor.
        
        Args:
            weights: Initial model weights (defaults to equal)
            use_dynamic_weights: Adjust weights based on confidence
            min_models: Minimum models required for prediction
        """
        self.weights = weights or {
            "poisson": 0.25,
            "elo": 0.20,
            "xgboost": 0.25,
            "lstm": 0.15,
            "monte_carlo": 0.15
        }
        self.use_dynamic_weights = use_dynamic_weights
        self.min_models = min_models
        
        # Initialize models
        self.poisson = PoissonModel()
        self.elo = ELOSystem()
        self.xgboost: Optional[XGBoostPredictor] = None
        self.lstm: Optional[LSTMPredictor] = None
        self.monte_carlo = MonteCarloSimulator(n_simulations=5000)
        
        # Track model availability
        self.model_status = {name: False for name in self.MODEL_NAMES}
        self.model_status["poisson"] = True
        self.model_status["elo"] = True
        self.model_status["monte_carlo"] = True
    
    def initialize_xgboost(
        self,
        matches: List[Dict],
        **kwargs
    ) -> Dict:
        """Initialize and train XGBoost model."""
        try:
            self.xgboost = XGBoostPredictor(**kwargs)
            metrics = self.xgboost.train(matches)
            self.model_status["xgboost"] = True
            logger.info("XGBoost model trained successfully")
            return {"status": "success", "metrics": metrics}
        except Exception as e:
            logger.error(f"Failed to train XGBoost: {e}")
            return {"status": "error", "message": str(e)}
    
    def initialize_lstm(
        self,
        matches: List[Dict],
        **kwargs
    ) -> Dict:
        """Initialize and train LSTM model."""
        try:
            self.lstm = LSTMPredictor(**kwargs)
            metrics = self.lstm.train(matches)
            self.model_status["lstm"] = True
            logger.info("LSTM model trained successfully")
            return {"status": "success", "metrics": metrics}
        except Exception as e:
            logger.error(f"Failed to train LSTM: {e}")
            return {"status": "error", "message": str(e)}
    
    def initialize_elo(
        self,
        matches: List[Dict],
        reset: bool = True
    ) -> Dict:
        """Process historical matches for ELO ratings."""
        try:
            result = self.elo.batch_process_matches(matches, reset_ratings=reset)
            logger.info(f"ELO ratings calculated for {result['total_teams']} teams")
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Failed to calculate ELO: {e}")
            return {"status": "error", "message": str(e)}
    
    def _calculate_dynamic_weights(
        self,
        predictions: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        Calculate dynamic weights based on model confidence.
        
        Higher confidence models get more weight.
        """
        weights = {}
        total_confidence = 0
        
        for model_name, pred in predictions.items():
            confidence = pred.get("confidence", 0.5)
            base_weight = self.weights.get(model_name, 0.1)
            
            # Adjust weight by confidence
            adjusted = base_weight * (0.5 + confidence)
            weights[model_name] = adjusted
            total_confidence += adjusted
        
        # Normalize
        if total_confidence > 0:
            weights = {k: v / total_confidence for k, v in weights.items()}
        
        return weights
    
    def _analyze_consensus(
        self,
        predictions: Dict[str, Dict]
    ) -> Tuple[str, str]:
        """
        Analyze consensus among models.
        
        Returns:
            Tuple of (consensus_outcome, consensus_level)
        """
        outcomes = []
        
        for pred in predictions.values():
            probs = pred.get("probabilities", {})
            if probs:
                max_prob = max(probs.values())
                outcome = [k for k, v in probs.items() if v == max_prob][0]
                outcomes.append(outcome)
        
        if not outcomes:
            return "uncertain", "low"
        
        # Count outcomes
        outcome_counts = {}
        for o in outcomes:
            outcome_counts[o] = outcome_counts.get(o, 0) + 1
        
        most_common = max(outcome_counts, key=outcome_counts.get)
        agreement = outcome_counts[most_common] / len(outcomes)
        
        if agreement >= 0.8:
            level = "high"
        elif agreement >= 0.6:
            level = "medium"
        else:
            level = "low"
        
        return most_common, level
    
    def predict(
        self,
        match: Dict,
        historical_matches: List[Dict],
        odds: Optional[Dict[str, float]] = None
    ) -> EnsemblePrediction:
        """
        Generate ensemble prediction for a match.
        
        Args:
            match: Match to predict
            historical_matches: Historical match data
            odds: Optional bookmaker odds for value bet detection
            
        Returns:
            EnsemblePrediction with combined probabilities
        """
        predictions = {}
        home_id = match["home_team_id"]
        away_id = match["away_team_id"]
        home_name = match.get("home_team_name", "Home")
        away_name = match.get("away_team_name", "Away")
        
        # 1. Poisson prediction
        try:
            # Calculate league averages
            league_avg = self.poisson.calculate_league_averages(
                historical_matches,
                match.get("league_id", 0)
            )
            
            # Calculate team strengths
            home_matches = [
                m for m in historical_matches
                if m["home_team_id"] == home_id or m["away_team_id"] == home_id
            ]
            away_matches = [
                m for m in historical_matches
                if m["home_team_id"] == away_id or m["away_team_id"] == away_id
            ]
            
            home_stats = self.poisson.calculate_team_strength(
                home_matches, home_id, league_avg
            )
            away_stats = self.poisson.calculate_team_strength(
                away_matches, away_id, league_avg
            )
            
            poisson_pred = self.poisson.predict_match(
                home_stats, away_stats, league_avg
            )
            
            predictions["poisson"] = {
                "probabilities": {
                    "home_win": poisson_pred.home_win_prob,
                    "draw": poisson_pred.draw_prob,
                    "away_win": poisson_pred.away_win_prob
                },
                "expected_goals": {
                    "home": poisson_pred.home_expected_goals,
                    "away": poisson_pred.away_expected_goals
                },
                "over_2_5": poisson_pred.over_2_5_prob,
                "btts": poisson_pred.btts_prob,
                "confidence": poisson_pred.confidence
            }
        except Exception as e:
            logger.warning(f"Poisson prediction failed: {e}")
        
        # 2. ELO prediction
        try:
            elo_pred = self.elo.predict_match(
                home_id, away_id, home_name, away_name
            )
            
            predictions["elo"] = {
                "probabilities": {
                    "home_win": elo_pred.home_win_prob,
                    "draw": elo_pred.draw_prob,
                    "away_win": elo_pred.away_win_prob
                },
                "expected_goals": {
                    "home": elo_pred.expected_home_score,
                    "away": elo_pred.expected_away_score
                },
                "ratings": {
                    "home": elo_pred.home_rating,
                    "away": elo_pred.away_rating
                },
                "confidence": elo_pred.confidence
            }
        except Exception as e:
            logger.warning(f"ELO prediction failed: {e}")
        
        # 3. XGBoost prediction
        if self.xgboost and self.model_status["xgboost"]:
            try:
                elo_ratings = {
                    t.team_id: t.rating 
                    for t in self.elo.ratings.values()
                }
                
                xgb_pred = self.xgboost.predict(
                    match, historical_matches, elo_ratings
                )
                
                predictions["xgboost"] = {
                    "probabilities": {
                        "home_win": xgb_pred.home_win_prob,
                        "draw": xgb_pred.draw_prob,
                        "away_win": xgb_pred.away_win_prob
                    },
                    "expected_goals": {
                        "home": xgb_pred.predicted_home_goals,
                        "away": xgb_pred.predicted_away_goals
                    },
                    "over_2_5": xgb_pred.over_2_5_prob,
                    "btts": xgb_pred.btts_prob,
                    "confidence": xgb_pred.confidence
                }
            except Exception as e:
                logger.warning(f"XGBoost prediction failed: {e}")
        
        # 4. LSTM prediction
        if self.lstm and self.model_status["lstm"]:
            try:
                lstm_pred = self.lstm.predict(match, historical_matches)
                
                predictions["lstm"] = {
                    "probabilities": {
                        "home_win": lstm_pred.home_win_prob,
                        "draw": lstm_pred.draw_prob,
                        "away_win": lstm_pred.away_win_prob
                    },
                    "trend": lstm_pred.trend_direction,
                    "confidence": lstm_pred.confidence
                }
            except Exception as e:
                logger.warning(f"LSTM prediction failed: {e}")
        
        # 5. Monte Carlo simulation
        try:
            # Use average expected goals from other models
            home_exp = np.mean([
                p.get("expected_goals", {}).get("home", 1.5)
                for p in predictions.values()
                if "expected_goals" in p
            ]) if predictions else 1.5
            
            away_exp = np.mean([
                p.get("expected_goals", {}).get("away", 1.2)
                for p in predictions.values()
                if "expected_goals" in p
            ]) if predictions else 1.2
            
            mc_result = self.monte_carlo.run_match_simulation(
                home_exp, away_exp, home_name, away_name
            )
            
            predictions["monte_carlo"] = {
                "probabilities": {
                    "home_win": mc_result.home_win_prob,
                    "draw": mc_result.draw_prob,
                    "away_win": mc_result.away_win_prob
                },
                "expected_goals": {
                    "home": mc_result.avg_home_goals,
                    "away": mc_result.avg_away_goals
                },
                "over_2_5": mc_result.over_under_probs["over_2_5"],
                "btts": mc_result.btts_prob,
                "score_distribution": mc_result.score_distribution,
                "confidence": 0.9  # MC always has high confidence
            }
        except Exception as e:
            logger.warning(f"Monte Carlo simulation failed: {e}")
        
        # Check minimum models
        if len(predictions) < self.min_models:
            raise ValueError(
                f"Only {len(predictions)} models available, "
                f"minimum {self.min_models} required"
            )
        
        # Calculate weights
        if self.use_dynamic_weights:
            weights = self._calculate_dynamic_weights(predictions)
        else:
            weights = {k: self.weights[k] for k in predictions.keys()}
            # Renormalize
            total = sum(weights.values())
            weights = {k: v / total for k, v in weights.items()}
        
        # Combine predictions
        home_win = sum(
            predictions[m]["probabilities"]["home_win"] * weights[m]
            for m in predictions
        )
        draw = sum(
            predictions[m]["probabilities"]["draw"] * weights[m]
            for m in predictions
        )
        away_win = sum(
            predictions[m]["probabilities"]["away_win"] * weights[m]
            for m in predictions
        )
        
        # Normalize
        total = home_win + draw + away_win
        home_win /= total
        draw /= total
        away_win /= total
        
        # Combined goals
        home_goals = np.mean([
            p.get("expected_goals", {}).get("home", 1.5)
            for p in predictions.values()
            if "expected_goals" in p
        ])
        away_goals = np.mean([
            p.get("expected_goals", {}).get("away", 1.2)
            for p in predictions.values()
            if "expected_goals" in p
        ])
        
        # Over/Under and BTTS
        over_2_5 = np.mean([
            p.get("over_2_5", 0.5)
            for p in predictions.values()
            if "over_2_5" in p
        ])
        btts = np.mean([
            p.get("btts", 0.5)
            for p in predictions.values()
            if "btts" in p
        ])
        
        # Predicted outcome
        probs = {"home_win": home_win, "draw": draw, "away_win": away_win}
        predicted_outcome = max(probs, key=probs.get)
        outcome_map = {"home_win": "Home Win", "draw": "Draw", "away_win": "Away Win"}
        
        # Consensus analysis
        _, consensus_level = self._analyze_consensus(predictions)
        
        # Confidence (average of model confidences weighted)
        confidence = sum(
            predictions[m].get("confidence", 0.5) * weights[m]
            for m in predictions
        )
        
        # Value bets
        value_bets = []
        if odds:
            all_odds_markets = {
                "home_win": odds.get("home_win") or odds.get("1"),
                "draw": odds.get("draw") or odds.get("X"),
                "away_win": odds.get("away_win") or odds.get("2"),
                "over_2_5": odds.get("over_2_5"),
                "under_2_5": odds.get("under_2_5"),
                "btts_yes": odds.get("btts_yes"),
                "btts_no": odds.get("btts_no")
            }
            
            ensemble_probs = {
                "home_win": home_win,
                "draw": draw,
                "away_win": away_win,
                "over_2_5": over_2_5,
                "under_2_5": 1 - over_2_5,
                "btts_yes": btts,
                "btts_no": 1 - btts
            }
            
            for market, prob in ensemble_probs.items():
                if all_odds_markets.get(market):
                    implied = 1 / all_odds_markets[market]
                    edge = prob - implied
                    
                    if edge >= 0.05:  # 5% minimum edge
                        value_bets.append({
                            "market": market,
                            "odds": all_odds_markets[market],
                            "ensemble_probability": round(prob, 4),
                            "implied_probability": round(implied, 4),
                            "edge": round(edge, 4),
                            "expected_value": round(prob * all_odds_markets[market] - 1, 4),
                            "models_agreeing": sum(
                                1 for p in predictions.values()
                                if p.get("probabilities", {}).get(market, 0) > implied
                            )
                        })
        
        return EnsemblePrediction(
            home_team=home_name,
            away_team=away_name,
            home_win_prob=round(home_win, 4),
            draw_prob=round(draw, 4),
            away_win_prob=round(away_win, 4),
            predicted_outcome=outcome_map[predicted_outcome],
            predicted_home_goals=round(home_goals, 2),
            predicted_away_goals=round(away_goals, 2),
            over_2_5_prob=round(over_2_5, 4),
            btts_prob=round(btts, 4),
            model_predictions=predictions,
            model_weights=weights,
            confidence=round(confidence, 4),
            consensus_level=consensus_level,
            value_bets=sorted(value_bets, key=lambda x: x["edge"], reverse=True)
        )
    
    def to_dict(self, prediction: EnsemblePrediction) -> Dict:
        """Convert ensemble prediction to dictionary."""
        return {
            "match": f"{prediction.home_team} vs {prediction.away_team}",
            "ensemble": {
                "probabilities": {
                    "home_win": prediction.home_win_prob,
                    "draw": prediction.draw_prob,
                    "away_win": prediction.away_win_prob
                },
                "predicted_outcome": prediction.predicted_outcome,
                "predicted_score": {
                    "home": prediction.predicted_home_goals,
                    "away": prediction.predicted_away_goals
                },
                "over_under": {
                    "over_2_5": prediction.over_2_5_prob,
                    "under_2_5": round(1 - prediction.over_2_5_prob, 4)
                },
                "btts": prediction.btts_prob,
                "confidence": prediction.confidence,
                "consensus": prediction.consensus_level
            },
            "model_weights": {
                k: round(v, 4) for k, v in prediction.model_weights.items()
            },
            "individual_predictions": prediction.model_predictions,
            "value_bets": prediction.value_bets
        }
    
    def get_model_status(self) -> Dict[str, bool]:
        """Get status of each model."""
        return self.model_status.copy()
    
    def get_model_weights(self) -> Dict[str, float]:
        """Get current model weights."""
        return self.weights.copy()
    
    def set_model_weights(self, weights: Dict[str, float]) -> None:
        """Set model weights (must sum to 1)."""
        total = sum(weights.values())
        self.weights = {k: v / total for k, v in weights.items()}
