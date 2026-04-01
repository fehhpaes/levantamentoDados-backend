"""
LSTM Neural Network Model for Sports Predictions

Uses Long Short-Term Memory networks to capture temporal patterns
in team performance for match outcome predictions.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import logging
import pickle

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, Model
    from tensorflow.keras.layers import (
        LSTM, Dense, Dropout, Input, 
        Bidirectional, Attention, Concatenate
    )
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    tf = None

logger = logging.getLogger(__name__)


@dataclass
class LSTMPrediction:
    """Prediction result from LSTM model."""
    home_team: str
    away_team: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_outcome: str
    sequence_confidence: float
    trend_direction: str  # improving, declining, stable
    confidence: float


class TimeSeriesFeatures:
    """
    Time series feature preparation for LSTM.
    
    Creates sequences of team performance metrics over time.
    """
    
    def __init__(
        self,
        sequence_length: int = 10,
        features_per_match: int = 12
    ):
        """
        Initialize time series feature generator.
        
        Args:
            sequence_length: Number of past matches to include
            features_per_match: Number of features extracted per match
        """
        self.sequence_length = sequence_length
        self.features_per_match = features_per_match
    
    def extract_match_features(
        self,
        match: Dict,
        team_id: int
    ) -> List[float]:
        """
        Extract features from a single match for a team.
        
        Returns features representing team performance in the match.
        """
        is_home = match["home_team_id"] == team_id
        
        if is_home:
            goals_scored = match.get("home_score", 0)
            goals_conceded = match.get("away_score", 0)
        else:
            goals_scored = match.get("away_score", 0)
            goals_conceded = match.get("home_score", 0)
        
        # Determine result
        if goals_scored > goals_conceded:
            result = 1.0  # Win
            points = 3
        elif goals_scored == goals_conceded:
            result = 0.5  # Draw
            points = 1
        else:
            result = 0.0  # Loss
            points = 0
        
        return [
            goals_scored,
            goals_conceded,
            goals_scored - goals_conceded,  # Goal difference
            result,
            points,
            1.0 if is_home else 0.0,  # Home/Away indicator
            1.0 if goals_conceded == 0 else 0.0,  # Clean sheet
            1.0 if goals_scored == 0 else 0.0,  # Failed to score
            1.0 if goals_scored + goals_conceded > 2.5 else 0.0,  # Over 2.5
            1.0 if goals_scored > 0 and goals_conceded > 0 else 0.0,  # BTTS
            min(goals_scored, 4) / 4,  # Normalized goals scored
            min(goals_conceded, 4) / 4  # Normalized goals conceded
        ]
    
    def create_team_sequence(
        self,
        matches: List[Dict],
        team_id: int
    ) -> np.ndarray:
        """
        Create a sequence of features from team's recent matches.
        
        Args:
            matches: List of team's matches (sorted by date)
            team_id: Team identifier
            
        Returns:
            Array of shape (sequence_length, features_per_match)
        """
        # Filter matches for this team
        team_matches = [
            m for m in matches
            if m["home_team_id"] == team_id or m["away_team_id"] == team_id
        ]
        
        # Sort by date (most recent last)
        team_matches = sorted(
            team_matches,
            key=lambda x: x.get("date", datetime.min)
        )
        
        # Take last N matches
        recent_matches = team_matches[-self.sequence_length:]
        
        # Extract features for each match
        sequence = []
        for match in recent_matches:
            features = self.extract_match_features(match, team_id)
            sequence.append(features)
        
        # Pad if not enough matches
        while len(sequence) < self.sequence_length:
            # Pad with neutral values
            sequence.insert(0, [0.5] * self.features_per_match)
        
        return np.array(sequence)
    
    def create_match_input(
        self,
        match: Dict,
        historical_matches: List[Dict]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create input sequences for both teams in a match.
        
        Args:
            match: Match to predict
            historical_matches: Historical match data
            
        Returns:
            Tuple of (home_sequence, away_sequence)
        """
        home_seq = self.create_team_sequence(
            historical_matches,
            match["home_team_id"]
        )
        away_seq = self.create_team_sequence(
            historical_matches,
            match["away_team_id"]
        )
        
        return home_seq, away_seq


class LSTMPredictor:
    """
    LSTM-based predictor for match outcomes.
    
    Features:
    - Bidirectional LSTM for pattern recognition
    - Attention mechanism for important matches
    - Dual-input architecture (home + away sequences)
    - Trend detection
    """
    
    def __init__(
        self,
        sequence_length: int = 10,
        features_per_match: int = 12,
        lstm_units: int = 64,
        dropout: float = 0.3,
        learning_rate: float = 0.001
    ):
        """
        Initialize LSTM predictor.
        
        Args:
            sequence_length: Number of past matches per team
            features_per_match: Features extracted per match
            lstm_units: Number of LSTM units
            dropout: Dropout rate
            learning_rate: Learning rate for optimizer
        """
        if not TF_AVAILABLE:
            logger.warning("TensorFlow not available. Install with: pip install tensorflow")
        
        self.sequence_length = sequence_length
        self.features_per_match = features_per_match
        self.lstm_units = lstm_units
        self.dropout = dropout
        self.learning_rate = learning_rate
        
        self.model: Optional[Any] = None
        self.is_trained = False
        self.feature_generator = TimeSeriesFeatures(
            sequence_length=sequence_length,
            features_per_match=features_per_match
        )
        self.training_history: Dict = {}
    
    def build_model(self) -> None:
        """Build the LSTM model architecture."""
        if not TF_AVAILABLE:
            raise ImportError("TensorFlow required. Install with: pip install tensorflow")
        
        # Input for home team sequence
        home_input = Input(
            shape=(self.sequence_length, self.features_per_match),
            name="home_sequence"
        )
        
        # Input for away team sequence
        away_input = Input(
            shape=(self.sequence_length, self.features_per_match),
            name="away_sequence"
        )
        
        # Shared LSTM layer
        lstm_layer = Bidirectional(
            LSTM(
                self.lstm_units,
                return_sequences=True,
                dropout=self.dropout,
                recurrent_dropout=self.dropout / 2
            )
        )
        
        # Process home sequence
        home_lstm = lstm_layer(home_input)
        home_lstm = LSTM(
            self.lstm_units // 2,
            dropout=self.dropout
        )(home_lstm)
        
        # Process away sequence
        away_lstm = lstm_layer(away_input)
        away_lstm = LSTM(
            self.lstm_units // 2,
            dropout=self.dropout
        )(away_lstm)
        
        # Concatenate both team representations
        merged = Concatenate()([home_lstm, away_lstm])
        
        # Dense layers
        x = Dense(64, activation="relu")(merged)
        x = Dropout(self.dropout)(x)
        x = Dense(32, activation="relu")(x)
        x = Dropout(self.dropout / 2)(x)
        
        # Output layer (3 classes: home_win, draw, away_win)
        output = Dense(3, activation="softmax", name="outcome")(x)
        
        # Create model
        self.model = Model(
            inputs=[home_input, away_input],
            outputs=output
        )
        
        # Compile
        self.model.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss="categorical_crossentropy",
            metrics=["accuracy"]
        )
        
        logger.info("LSTM model built successfully")
    
    def prepare_training_data(
        self,
        matches: List[Dict]
    ) -> Tuple[List[np.ndarray], np.ndarray]:
        """
        Prepare training data from historical matches.
        
        Args:
            matches: List of matches with results
            
        Returns:
            Tuple of ([home_sequences, away_sequences], labels)
        """
        # Sort by date
        sorted_matches = sorted(
            matches,
            key=lambda x: x.get("date", datetime.min)
        )
        
        home_sequences = []
        away_sequences = []
        labels = []
        
        # Need at least sequence_length matches before we can start
        min_history = self.sequence_length + 5
        
        for i in range(min_history, len(sorted_matches)):
            match = sorted_matches[i]
            historical = sorted_matches[:i]
            
            try:
                home_seq, away_seq = self.feature_generator.create_match_input(
                    match, historical
                )
                
                home_sequences.append(home_seq)
                away_sequences.append(away_seq)
                
                # Create label
                if match["home_score"] > match["away_score"]:
                    labels.append([1, 0, 0])  # Home win
                elif match["home_score"] == match["away_score"]:
                    labels.append([0, 1, 0])  # Draw
                else:
                    labels.append([0, 0, 1])  # Away win
                    
            except Exception as e:
                logger.warning(f"Error preparing data for match: {e}")
                continue
        
        return (
            [np.array(home_sequences), np.array(away_sequences)],
            np.array(labels)
        )
    
    def train(
        self,
        matches: List[Dict],
        validation_split: float = 0.2,
        epochs: int = 100,
        batch_size: int = 32
    ) -> Dict[str, float]:
        """
        Train the LSTM model.
        
        Args:
            matches: Historical matches with results
            validation_split: Fraction for validation
            epochs: Training epochs
            batch_size: Batch size
            
        Returns:
            Training metrics
        """
        if not TF_AVAILABLE:
            raise ImportError("TensorFlow required. Install with: pip install tensorflow")
        
        if self.model is None:
            self.build_model()
        
        # Prepare data
        X, y = self.prepare_training_data(matches)
        
        if len(y) < 100:
            raise ValueError("Insufficient data (minimum 100 matches required)")
        
        # Callbacks
        callbacks = [
            EarlyStopping(
                monitor="val_loss",
                patience=10,
                restore_best_weights=True
            ),
            ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=5,
                min_lr=1e-6
            )
        ]
        
        # Train
        history = self.model.fit(
            X, y,
            validation_split=validation_split,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=1
        )
        
        self.is_trained = True
        self.training_history = {
            "loss": history.history["loss"],
            "val_loss": history.history["val_loss"],
            "accuracy": history.history["accuracy"],
            "val_accuracy": history.history["val_accuracy"]
        }
        
        # Return final metrics
        return {
            "final_loss": float(history.history["loss"][-1]),
            "final_val_loss": float(history.history["val_loss"][-1]),
            "final_accuracy": float(history.history["accuracy"][-1]),
            "final_val_accuracy": float(history.history["val_accuracy"][-1]),
            "epochs_trained": len(history.history["loss"]),
            "training_samples": int(len(y) * (1 - validation_split))
        }
    
    def predict(
        self,
        match: Dict,
        historical_matches: List[Dict]
    ) -> LSTMPrediction:
        """
        Predict match outcome.
        
        Args:
            match: Match to predict
            historical_matches: Historical data
            
        Returns:
            LSTMPrediction with probabilities
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        # Create input sequences
        home_seq, away_seq = self.feature_generator.create_match_input(
            match, historical_matches
        )
        
        # Reshape for prediction
        home_seq = home_seq.reshape(1, self.sequence_length, self.features_per_match)
        away_seq = away_seq.reshape(1, self.sequence_length, self.features_per_match)
        
        # Predict
        probs = self.model.predict([home_seq, away_seq], verbose=0)[0]
        
        home_win_prob = float(probs[0])
        draw_prob = float(probs[1])
        away_win_prob = float(probs[2])
        
        # Determine outcome
        outcomes = ["Home Win", "Draw", "Away Win"]
        predicted_outcome = outcomes[np.argmax(probs)]
        
        # Analyze trend from sequences
        home_trend = self._analyze_trend(home_seq[0])
        away_trend = self._analyze_trend(away_seq[0])
        
        if home_trend > 0.1:
            trend_direction = "home_improving"
        elif away_trend > 0.1:
            trend_direction = "away_improving"
        elif home_trend < -0.1:
            trend_direction = "home_declining"
        elif away_trend < -0.1:
            trend_direction = "away_declining"
        else:
            trend_direction = "stable"
        
        # Confidence based on probability margin
        confidence = float(np.max(probs) - np.sort(probs)[-2])
        
        # Sequence confidence (how consistent the pattern is)
        sequence_confidence = self._calculate_sequence_confidence(home_seq[0], away_seq[0])
        
        return LSTMPrediction(
            home_team=match.get("home_team_name", "Home"),
            away_team=match.get("away_team_name", "Away"),
            home_win_prob=round(home_win_prob, 4),
            draw_prob=round(draw_prob, 4),
            away_win_prob=round(away_win_prob, 4),
            predicted_outcome=predicted_outcome,
            sequence_confidence=round(sequence_confidence, 4),
            trend_direction=trend_direction,
            confidence=round(confidence, 4)
        )
    
    def _analyze_trend(self, sequence: np.ndarray) -> float:
        """
        Analyze performance trend from sequence.
        
        Returns positive value for improving, negative for declining.
        """
        # Use points (index 4) and goal difference (index 2)
        points = sequence[:, 4]
        goal_diff = sequence[:, 2]
        
        # Simple linear regression slope
        x = np.arange(len(points))
        
        # Weighted towards recent matches
        weights = np.exp(np.linspace(0, 1, len(points)))
        
        # Calculate weighted trend
        points_trend = np.polyfit(x, points, 1, w=weights)[0]
        gd_trend = np.polyfit(x, goal_diff, 1, w=weights)[0]
        
        return (points_trend + gd_trend * 0.3) / 2
    
    def _calculate_sequence_confidence(
        self,
        home_seq: np.ndarray,
        away_seq: np.ndarray
    ) -> float:
        """
        Calculate confidence based on sequence consistency.
        
        Low variance in performance = higher confidence.
        """
        home_results = home_seq[:, 3]  # Result column
        away_results = away_seq[:, 3]
        
        home_variance = np.var(home_results)
        away_variance = np.var(away_results)
        
        # Lower variance = higher confidence
        confidence = 1 - (home_variance + away_variance) / 2
        
        return max(0.1, min(1.0, confidence))
    
    def save_model(self, path: str) -> None:
        """Save trained model to file."""
        if not self.is_trained:
            raise ValueError("Model must be trained before saving")
        
        self.model.save(f"{path}.keras")
        
        # Save additional attributes
        attrs = {
            "sequence_length": self.sequence_length,
            "features_per_match": self.features_per_match,
            "lstm_units": self.lstm_units,
            "training_history": self.training_history
        }
        with open(f"{path}_attrs.pkl", "wb") as f:
            pickle.dump(attrs, f)
        
        logger.info(f"Model saved to {path}")
    
    def load_model(self, path: str) -> None:
        """Load trained model from file."""
        if not TF_AVAILABLE:
            raise ImportError("TensorFlow required")
        
        self.model = tf.keras.models.load_model(f"{path}.keras")
        
        with open(f"{path}_attrs.pkl", "rb") as f:
            attrs = pickle.load(f)
        
        self.sequence_length = attrs["sequence_length"]
        self.features_per_match = attrs["features_per_match"]
        self.lstm_units = attrs["lstm_units"]
        self.training_history = attrs["training_history"]
        self.is_trained = True
        
        # Reinitialize feature generator
        self.feature_generator = TimeSeriesFeatures(
            sequence_length=self.sequence_length,
            features_per_match=self.features_per_match
        )
        
        logger.info(f"Model loaded from {path}")
    
    def to_dict(self, prediction: LSTMPrediction) -> Dict:
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
            "trend_analysis": {
                "direction": prediction.trend_direction,
                "sequence_confidence": prediction.sequence_confidence
            },
            "confidence": prediction.confidence
        }
