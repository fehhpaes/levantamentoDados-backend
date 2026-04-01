"""
XGBoost Advanced Model for Sports Predictions

Uses gradient boosting with extensive feature engineering
for accurate match outcome predictions.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import pickle
import json

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    xgb = None

logger = logging.getLogger(__name__)


@dataclass
class XGBoostPrediction:
    """Prediction result from XGBoost model."""
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
    feature_importance: Dict[str, float]
    confidence: float


class FeatureEngineering:
    """Feature engineering utilities for match prediction."""
    
    @staticmethod
    def calculate_form(
        results: List[str],
        window: int = 5
    ) -> float:
        """
        Calculate team form based on recent results.
        
        Args:
            results: List of results ('W', 'D', 'L')
            window: Number of recent matches to consider
            
        Returns:
            Form score between 0 and 1
        """
        if not results:
            return 0.5
        
        recent = results[-window:] if len(results) > window else results
        points = sum(3 if r == 'W' else 1 if r == 'D' else 0 for r in recent)
        max_points = len(recent) * 3
        
        return points / max_points if max_points > 0 else 0.5
    
    @staticmethod
    def calculate_goal_stats(
        matches: List[Dict],
        team_id: int,
        window: int = 10
    ) -> Dict[str, float]:
        """Calculate goal-related statistics."""
        recent = matches[-window:] if len(matches) > window else matches
        
        if not recent:
            return {
                "avg_scored": 1.5,
                "avg_conceded": 1.2,
                "clean_sheets_pct": 0.2,
                "failed_to_score_pct": 0.15,
                "over_2_5_pct": 0.5
            }
        
        scored = []
        conceded = []
        clean_sheets = 0
        failed_to_score = 0
        over_2_5 = 0
        
        for match in recent:
            if match["home_team_id"] == team_id:
                scored.append(match["home_score"])
                conceded.append(match["away_score"])
                if match["away_score"] == 0:
                    clean_sheets += 1
                if match["home_score"] == 0:
                    failed_to_score += 1
            else:
                scored.append(match["away_score"])
                conceded.append(match["home_score"])
                if match["home_score"] == 0:
                    clean_sheets += 1
                if match["away_score"] == 0:
                    failed_to_score += 1
            
            if sum([match["home_score"], match["away_score"]]) > 2:
                over_2_5 += 1
        
        n = len(recent)
        return {
            "avg_scored": np.mean(scored),
            "avg_conceded": np.mean(conceded),
            "std_scored": np.std(scored) if len(scored) > 1 else 0,
            "std_conceded": np.std(conceded) if len(conceded) > 1 else 0,
            "clean_sheets_pct": clean_sheets / n,
            "failed_to_score_pct": failed_to_score / n,
            "over_2_5_pct": over_2_5 / n
        }
    
    @staticmethod
    def calculate_head_to_head(
        matches: List[Dict],
        home_team_id: int,
        away_team_id: int,
        max_matches: int = 10
    ) -> Dict[str, float]:
        """Calculate head-to-head statistics."""
        h2h = [
            m for m in matches
            if (m["home_team_id"] == home_team_id and m["away_team_id"] == away_team_id) or
               (m["home_team_id"] == away_team_id and m["away_team_id"] == home_team_id)
        ][-max_matches:]
        
        if not h2h:
            return {
                "h2h_home_wins": 0.33,
                "h2h_draws": 0.33,
                "h2h_away_wins": 0.33,
                "h2h_avg_goals": 2.5,
                "h2h_matches": 0
            }
        
        home_wins = 0
        draws = 0
        away_wins = 0
        total_goals = 0
        
        for match in h2h:
            total_goals += match["home_score"] + match["away_score"]
            
            if match["home_team_id"] == home_team_id:
                if match["home_score"] > match["away_score"]:
                    home_wins += 1
                elif match["home_score"] == match["away_score"]:
                    draws += 1
                else:
                    away_wins += 1
            else:
                if match["away_score"] > match["home_score"]:
                    home_wins += 1
                elif match["home_score"] == match["away_score"]:
                    draws += 1
                else:
                    away_wins += 1
        
        n = len(h2h)
        return {
            "h2h_home_wins": home_wins / n,
            "h2h_draws": draws / n,
            "h2h_away_wins": away_wins / n,
            "h2h_avg_goals": total_goals / n,
            "h2h_matches": n
        }
    
    @staticmethod
    def calculate_home_away_split(
        matches: List[Dict],
        team_id: int,
        is_home: bool
    ) -> Dict[str, float]:
        """Calculate home/away specific statistics."""
        if is_home:
            relevant = [m for m in matches if m["home_team_id"] == team_id]
        else:
            relevant = [m for m in matches if m["away_team_id"] == team_id]
        
        if not relevant:
            return {
                "venue_win_pct": 0.5,
                "venue_avg_scored": 1.5,
                "venue_avg_conceded": 1.2
            }
        
        wins = 0
        scored = []
        conceded = []
        
        for match in relevant:
            if is_home:
                scored.append(match["home_score"])
                conceded.append(match["away_score"])
                if match["home_score"] > match["away_score"]:
                    wins += 1
            else:
                scored.append(match["away_score"])
                conceded.append(match["home_score"])
                if match["away_score"] > match["home_score"]:
                    wins += 1
        
        n = len(relevant)
        return {
            "venue_win_pct": wins / n,
            "venue_avg_scored": np.mean(scored),
            "venue_avg_conceded": np.mean(conceded)
        }


class XGBoostPredictor:
    """
    XGBoost model for match outcome prediction.
    
    Features:
    - Extensive feature engineering
    - Multi-output prediction (result, goals, BTTS)
    - Feature importance analysis
    - Model persistence
    - Cross-validation support
    """
    
    FEATURE_NAMES = [
        # Team form features
        "home_form", "away_form",
        "home_form_diff", "form_momentum_home", "form_momentum_away",
        
        # Goal statistics
        "home_avg_scored", "home_avg_conceded",
        "away_avg_scored", "away_avg_conceded",
        "home_std_scored", "away_std_scored",
        "home_clean_sheets_pct", "away_clean_sheets_pct",
        "home_failed_to_score_pct", "away_failed_to_score_pct",
        "home_over_2_5_pct", "away_over_2_5_pct",
        
        # Home/Away split
        "home_venue_win_pct", "home_venue_avg_scored",
        "away_venue_win_pct", "away_venue_avg_scored",
        
        # Head to head
        "h2h_home_wins", "h2h_draws", "h2h_away_wins",
        "h2h_avg_goals", "h2h_matches",
        
        # Strength indicators
        "attack_diff", "defense_diff",
        "overall_strength_diff",
        
        # ELO ratings (if available)
        "home_elo", "away_elo", "elo_diff",
        
        # Contextual features
        "days_since_last_home", "days_since_last_away",
        "is_derby", "league_position_diff"
    ]
    
    def __init__(
        self,
        params: Optional[Dict] = None,
        n_estimators: int = 200,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        random_state: int = 42
    ):
        """
        Initialize XGBoost predictor.
        
        Args:
            params: Custom XGBoost parameters
            n_estimators: Number of boosting rounds
            max_depth: Maximum tree depth
            learning_rate: Learning rate
            random_state: Random seed
        """
        if not XGB_AVAILABLE:
            logger.warning("XGBoost not available. Install with: pip install xgboost")
        
        self.params = params or {
            "objective": "multi:softprob",
            "num_class": 3,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "n_estimators": n_estimators,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": random_state,
            "use_label_encoder": False,
            "eval_metric": "mlogloss"
        }
        
        self.goals_params = {
            "objective": "reg:squarederror",
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "n_estimators": n_estimators,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": random_state
        }
        
        self.model_result: Optional[Any] = None
        self.model_home_goals: Optional[Any] = None
        self.model_away_goals: Optional[Any] = None
        self.model_btts: Optional[Any] = None
        self.feature_importance: Dict[str, float] = {}
        self.is_trained = False
        self.feature_engineering = FeatureEngineering()
    
    def prepare_features(
        self,
        match: Dict,
        historical_matches: List[Dict],
        elo_ratings: Optional[Dict[int, float]] = None
    ) -> np.ndarray:
        """
        Prepare feature vector for a match.
        
        Args:
            match: Match to predict
            historical_matches: Historical matches for statistics
            elo_ratings: Optional ELO ratings for teams
            
        Returns:
            Feature vector
        """
        home_id = match["home_team_id"]
        away_id = match["away_team_id"]
        
        # Get team matches
        home_matches = [
            m for m in historical_matches
            if m["home_team_id"] == home_id or m["away_team_id"] == home_id
        ]
        away_matches = [
            m for m in historical_matches
            if m["home_team_id"] == away_id or m["away_team_id"] == away_id
        ]
        
        # Calculate form
        home_results = []
        for m in home_matches[-10:]:
            if m["home_team_id"] == home_id:
                if m["home_score"] > m["away_score"]:
                    home_results.append("W")
                elif m["home_score"] == m["away_score"]:
                    home_results.append("D")
                else:
                    home_results.append("L")
            else:
                if m["away_score"] > m["home_score"]:
                    home_results.append("W")
                elif m["home_score"] == m["away_score"]:
                    home_results.append("D")
                else:
                    home_results.append("L")
        
        away_results = []
        for m in away_matches[-10:]:
            if m["home_team_id"] == away_id:
                if m["home_score"] > m["away_score"]:
                    away_results.append("W")
                elif m["home_score"] == m["away_score"]:
                    away_results.append("D")
                else:
                    away_results.append("L")
            else:
                if m["away_score"] > m["home_score"]:
                    away_results.append("W")
                elif m["home_score"] == m["away_score"]:
                    away_results.append("D")
                else:
                    away_results.append("L")
        
        home_form = self.feature_engineering.calculate_form(home_results)
        away_form = self.feature_engineering.calculate_form(away_results)
        home_form_recent = self.feature_engineering.calculate_form(home_results, 3)
        away_form_recent = self.feature_engineering.calculate_form(away_results, 3)
        
        # Goal statistics
        home_goal_stats = self.feature_engineering.calculate_goal_stats(
            home_matches, home_id
        )
        away_goal_stats = self.feature_engineering.calculate_goal_stats(
            away_matches, away_id
        )
        
        # Home/Away split
        home_venue_stats = self.feature_engineering.calculate_home_away_split(
            home_matches, home_id, True
        )
        away_venue_stats = self.feature_engineering.calculate_home_away_split(
            away_matches, away_id, False
        )
        
        # Head to head
        h2h_stats = self.feature_engineering.calculate_head_to_head(
            historical_matches, home_id, away_id
        )
        
        # ELO ratings
        home_elo = elo_ratings.get(home_id, 1500) if elo_ratings else 1500
        away_elo = elo_ratings.get(away_id, 1500) if elo_ratings else 1500
        
        # Build feature vector
        features = [
            # Team form
            home_form,
            away_form,
            home_form - away_form,
            home_form_recent - home_form,  # Form momentum
            away_form_recent - away_form,
            
            # Goal statistics
            home_goal_stats["avg_scored"],
            home_goal_stats["avg_conceded"],
            away_goal_stats["avg_scored"],
            away_goal_stats["avg_conceded"],
            home_goal_stats.get("std_scored", 0),
            away_goal_stats.get("std_scored", 0),
            home_goal_stats["clean_sheets_pct"],
            away_goal_stats["clean_sheets_pct"],
            home_goal_stats["failed_to_score_pct"],
            away_goal_stats["failed_to_score_pct"],
            home_goal_stats["over_2_5_pct"],
            away_goal_stats["over_2_5_pct"],
            
            # Home/Away split
            home_venue_stats["venue_win_pct"],
            home_venue_stats["venue_avg_scored"],
            away_venue_stats["venue_win_pct"],
            away_venue_stats["venue_avg_scored"],
            
            # Head to head
            h2h_stats["h2h_home_wins"],
            h2h_stats["h2h_draws"],
            h2h_stats["h2h_away_wins"],
            h2h_stats["h2h_avg_goals"],
            h2h_stats["h2h_matches"],
            
            # Strength indicators
            home_goal_stats["avg_scored"] - away_goal_stats["avg_conceded"],
            away_goal_stats["avg_scored"] - home_goal_stats["avg_conceded"],
            (home_goal_stats["avg_scored"] - home_goal_stats["avg_conceded"]) -
            (away_goal_stats["avg_scored"] - away_goal_stats["avg_conceded"]),
            
            # ELO
            home_elo,
            away_elo,
            home_elo - away_elo,
            
            # Contextual (simplified)
            0,  # days_since_last_home
            0,  # days_since_last_away
            0,  # is_derby
            0   # league_position_diff
        ]
        
        return np.array(features)
    
    def train(
        self,
        matches: List[Dict],
        validation_split: float = 0.2
    ) -> Dict[str, float]:
        """
        Train the XGBoost model.
        
        Args:
            matches: List of historical matches with results
            validation_split: Fraction of data for validation
            
        Returns:
            Training metrics
        """
        if not XGB_AVAILABLE:
            raise ImportError("XGBoost is required. Install with: pip install xgboost")
        
        # Sort by date
        sorted_matches = sorted(
            matches,
            key=lambda x: x.get("date", datetime.min)
        )
        
        # Prepare features and labels
        X = []
        y_result = []
        y_home_goals = []
        y_away_goals = []
        y_btts = []
        
        for i, match in enumerate(sorted_matches[20:], 20):
            historical = sorted_matches[:i]
            
            try:
                features = self.prepare_features(match, historical)
                X.append(features)
                
                # Result: 0=home_win, 1=draw, 2=away_win
                if match["home_score"] > match["away_score"]:
                    y_result.append(0)
                elif match["home_score"] == match["away_score"]:
                    y_result.append(1)
                else:
                    y_result.append(2)
                
                y_home_goals.append(match["home_score"])
                y_away_goals.append(match["away_score"])
                y_btts.append(1 if match["home_score"] > 0 and match["away_score"] > 0 else 0)
                
            except Exception as e:
                logger.warning(f"Error preparing features for match: {e}")
                continue
        
        if len(X) < 50:
            raise ValueError("Insufficient data for training (minimum 50 matches)")
        
        X = np.array(X)
        y_result = np.array(y_result)
        y_home_goals = np.array(y_home_goals)
        y_away_goals = np.array(y_away_goals)
        y_btts = np.array(y_btts)
        
        # Split data
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_result_train, y_result_val = y_result[:split_idx], y_result[split_idx:]
        y_home_train, y_home_val = y_home_goals[:split_idx], y_home_goals[split_idx:]
        y_away_train, y_away_val = y_away_goals[:split_idx], y_away_goals[split_idx:]
        y_btts_train, y_btts_val = y_btts[:split_idx], y_btts[split_idx:]
        
        # Train result classifier
        self.model_result = xgb.XGBClassifier(**self.params)
        self.model_result.fit(
            X_train, y_result_train,
            eval_set=[(X_val, y_result_val)],
            verbose=False
        )
        
        # Train goal regressors
        self.model_home_goals = xgb.XGBRegressor(**self.goals_params)
        self.model_home_goals.fit(X_train, y_home_train, verbose=False)
        
        self.model_away_goals = xgb.XGBRegressor(**self.goals_params)
        self.model_away_goals.fit(X_train, y_away_train, verbose=False)
        
        # Train BTTS classifier
        btts_params = self.params.copy()
        btts_params["objective"] = "binary:logistic"
        btts_params.pop("num_class", None)
        
        self.model_btts = xgb.XGBClassifier(**btts_params)
        self.model_btts.fit(X_train, y_btts_train, verbose=False)
        
        # Store feature importance
        importance = self.model_result.feature_importances_
        self.feature_importance = {
            name: float(imp) 
            for name, imp in zip(self.FEATURE_NAMES[:len(importance)], importance)
        }
        
        self.is_trained = True
        
        # Calculate metrics
        result_acc = np.mean(self.model_result.predict(X_val) == y_result_val)
        home_mae = np.mean(np.abs(self.model_home_goals.predict(X_val) - y_home_val))
        away_mae = np.mean(np.abs(self.model_away_goals.predict(X_val) - y_away_val))
        
        return {
            "result_accuracy": round(result_acc, 4),
            "home_goals_mae": round(home_mae, 4),
            "away_goals_mae": round(away_mae, 4),
            "training_samples": len(X_train),
            "validation_samples": len(X_val)
        }
    
    def predict(
        self,
        match: Dict,
        historical_matches: List[Dict],
        elo_ratings: Optional[Dict[int, float]] = None
    ) -> XGBoostPrediction:
        """
        Predict match outcome.
        
        Args:
            match: Match to predict
            historical_matches: Historical matches
            elo_ratings: Optional ELO ratings
            
        Returns:
            XGBoostPrediction with probabilities
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        features = self.prepare_features(match, historical_matches, elo_ratings)
        X = features.reshape(1, -1)
        
        # Get probabilities
        result_probs = self.model_result.predict_proba(X)[0]
        home_win_prob = result_probs[0]
        draw_prob = result_probs[1]
        away_win_prob = result_probs[2]
        
        # Get goal predictions
        home_goals = max(0, self.model_home_goals.predict(X)[0])
        away_goals = max(0, self.model_away_goals.predict(X)[0])
        
        # Get BTTS probability
        btts_prob = self.model_btts.predict_proba(X)[0][1]
        
        # Calculate over 2.5 probability (simplified)
        expected_total = home_goals + away_goals
        over_2_5_prob = min(0.95, max(0.05, (expected_total - 2) / 2 + 0.5))
        
        # Determine predicted outcome
        outcomes = ["Home Win", "Draw", "Away Win"]
        predicted_outcome = outcomes[np.argmax(result_probs)]
        
        # Confidence based on probability margin
        confidence = max(result_probs) - sorted(result_probs)[1]
        
        return XGBoostPrediction(
            home_team=match.get("home_team_name", "Home"),
            away_team=match.get("away_team_name", "Away"),
            home_win_prob=round(home_win_prob, 4),
            draw_prob=round(draw_prob, 4),
            away_win_prob=round(away_win_prob, 4),
            predicted_outcome=predicted_outcome,
            predicted_home_goals=round(home_goals, 2),
            predicted_away_goals=round(away_goals, 2),
            over_2_5_prob=round(over_2_5_prob, 4),
            btts_prob=round(btts_prob, 4),
            feature_importance=self.feature_importance,
            confidence=round(confidence, 4)
        )
    
    def save_model(self, path: str) -> None:
        """Save trained model to file."""
        if not self.is_trained:
            raise ValueError("Model must be trained before saving")
        
        model_data = {
            "model_result": self.model_result,
            "model_home_goals": self.model_home_goals,
            "model_away_goals": self.model_away_goals,
            "model_btts": self.model_btts,
            "feature_importance": self.feature_importance,
            "params": self.params
        }
        
        with open(path, "wb") as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {path}")
    
    def load_model(self, path: str) -> None:
        """Load trained model from file."""
        with open(path, "rb") as f:
            model_data = pickle.load(f)
        
        self.model_result = model_data["model_result"]
        self.model_home_goals = model_data["model_home_goals"]
        self.model_away_goals = model_data["model_away_goals"]
        self.model_btts = model_data["model_btts"]
        self.feature_importance = model_data["feature_importance"]
        self.params = model_data["params"]
        self.is_trained = True
        
        logger.info(f"Model loaded from {path}")
    
    def to_dict(self, prediction: XGBoostPrediction) -> Dict:
        """Convert prediction to dictionary format."""
        return {
            "home_team": prediction.home_team,
            "away_team": prediction.away_team,
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
                "under_2_5": 1 - prediction.over_2_5_prob
            },
            "btts": prediction.btts_prob,
            "confidence": prediction.confidence,
            "top_features": dict(
                sorted(
                    prediction.feature_importance.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            )
        }
