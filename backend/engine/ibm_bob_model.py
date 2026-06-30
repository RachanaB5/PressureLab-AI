"""
PressureLab AI - IBM Bob ML Model
A real scikit-learn model trained to predict match outcomes based on match state features.
Uses the IBM Bob learning track philosophy (explainable prediction).
"""

import os
import pickle
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from sklearn.ensemble import GradientBoostingClassifier

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "prediction_model.pkl")

class IBMBobModel:
    """
    ML Prediction model for match outcomes (Home Win, Draw, Away Win).
    """
    def __init__(self):
        self.model = None
        self.feature_names = [
            'minute', 'home_goals', 'away_goals', 
            'home_shots', 'away_shots', 'home_momentum', 
            'away_momentum', 'goal_difference', 'time_remaining_pct'
        ]
        self.classes = ['away_win', 'draw', 'home_win'] # 0, 1, 2
        self._load_or_train()

    def _load_or_train(self):
        """Loads the model from disk if it exists, otherwise trains a new one."""
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, 'rb') as f:
                    self.model = pickle.load(f)
                logger.info(f"Loaded IBM Bob model from {MODEL_PATH}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}. Retraining...")
                self._train_model()
        else:
            logger.info("Model not found. Training IBM Bob model...")
            self._train_model()

    def _train_model(self):
        """Train on StatsBomb historical snapshots when available, else synthetic data."""
        X_train, y_train = self._build_training_data_from_statsbomb()
        if len(X_train) < 500:
            logger.info("StatsBomb training data insufficient — supplementing with synthetic samples")
            sx, sy = self._generate_synthetic_training_data(5000)
            X_train.extend(sx)
            y_train.extend(sy)
        X = pd.DataFrame(X_train, columns=self.feature_names)
        
        # Train model
        self.model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42)
        self.model.fit(X, y_train)
        
        # Save model
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(self.model, f)
            
        logger.info(f"Trained and saved IBM Bob model to {MODEL_PATH} ({len(X_train)} samples)")

    def _build_training_data_from_statsbomb(self) -> tuple[list, list]:
        """Extract minute-by-minute match states from StatsBomb Open Data."""
        X_train, y_train = [], []
        try:
            from statsbombpy import sb
            competitions = [(43, 3), (11, 1), (16, 1), (55, 43)]
            for comp_id, season_id in competitions:
                try:
                    matches = sb.matches(competition_id=comp_id, season_id=season_id)
                except Exception:
                    continue
                for _, mrow in matches.head(20).iterrows():
                    try:
                        events = sb.events(match_id=int(mrow["match_id"]))
                        home = str(mrow.get("home_team", "Home"))
                        away = str(mrow.get("away_team", "Away"))
                        final_home = int(mrow.get("home_score", 0))
                        final_away = int(mrow.get("away_score", 0))
                        if final_home > final_away:
                            final_outcome = 2
                        elif final_home < final_away:
                            final_outcome = 0
                        else:
                            final_outcome = 1

                        for minute in range(0, 91, 5):
                            subset = events[events["minute"] <= minute]
                            if subset.empty:
                                continue
                            home_goals = len(subset[
                                (subset["type"] == "Shot") &
                                (subset["team"] == home) &
                                (subset["shot_outcome"].astype(str).str.contains("Goal", case=False, na=False))
                            ])
                            away_goals = len(subset[
                                (subset["type"] == "Shot") &
                                (subset["team"] == away) &
                                (subset["shot_outcome"].astype(str).str.contains("Goal", case=False, na=False))
                            ])
                            home_shots = len(subset[(subset["type"] == "Shot") & (subset["team"] == home)])
                            away_shots = len(subset[(subset["type"] == "Shot") & (subset["team"] == away)])
                            home_ev = len(subset[subset["team"] == home])
                            away_ev = len(subset[subset["team"] == away])
                            total = home_ev + away_ev
                            home_momentum = home_ev / total if total else 0.5
                            away_momentum = 1.0 - home_momentum
                            time_remaining_pct = (95 - minute) / 95.0
                            X_train.append([
                                minute, home_goals, away_goals,
                                home_shots, away_shots, home_momentum,
                                away_momentum, home_goals - away_goals, time_remaining_pct,
                            ])
                            if minute >= 85:
                                y_train.append(final_outcome)
                            else:
                                score = (home_goals - away_goals) * 1.5 + (home_momentum - away_momentum)
                                if score > 0.5:
                                    y_train.append(2)
                                elif score < -0.5:
                                    y_train.append(0)
                                else:
                                    y_train.append(1)
                    except Exception:
                        continue
            logger.info("Built %d training samples from StatsBomb Open Data", len(X_train))
        except ImportError:
            logger.info("statsbombpy not installed — skipping StatsBomb training data")
        return X_train, y_train

    def _generate_synthetic_training_data(self, n: int) -> tuple[list, list]:
        X_train, y_train = [], []
        np.random.seed(42)
        for _ in range(n):
            minute = np.random.randint(0, 95)
            time_remaining_pct = (95 - minute) / 95.0
            max_goals = int((minute / 95.0) * 4) + 1
            home_goals = np.random.randint(0, max_goals + 1)
            away_goals = np.random.randint(0, max_goals + 1)
            home_shots = home_goals + np.random.randint(0, 10)
            away_shots = away_goals + np.random.randint(0, 10)
            home_momentum = np.random.beta(2, 2)
            away_momentum = 1.0 - home_momentum
            goal_diff = home_goals - away_goals
            X_train.append([
                minute, home_goals, away_goals,
                home_shots, away_shots, home_momentum,
                away_momentum, goal_diff, time_remaining_pct,
            ])
            if time_remaining_pct < 0.1:
                outcome = 2 if goal_diff > 0 else (0 if goal_diff < 0 else 1)
            else:
                score = goal_diff * 1.5 + (home_momentum - away_momentum) + (home_shots - away_shots) * 0.1
                score += np.random.normal(0, 1.5)
                outcome = 2 if score > 0.8 else (0 if score < -0.8 else 1)
            y_train.append(outcome)
        return X_train, y_train

    def counterfactual(self, features_dict: Dict[str, float], change: Dict[str, float]) -> Dict[str, Any]:
        """Compute counterfactual prediction after hypothetical state change."""
        safe = dict(features_dict)
        for k, v in change.items():
            if k in ("home_goals", "away_goals", "home_shots", "away_shots"):
                safe[k] = max(0, safe.get(k, 0) + v)
            elif k in ("home_momentum", "away_momentum"):
                safe[k] = float(np.clip(safe.get(k, 0.5) + v, 0.05, 0.95))
            else:
                safe[k] = safe.get(k, 0) + v
        base = self.predict(features_dict)
        alt = self.predict(safe)
        deltas = {
            k: round(alt[k] - base[k], 1)
            for k in ("home_win", "draw", "away_win")
        }
        return {"base": base, "counterfactual": alt, "deltas": deltas, "changes_applied": change}

    def predict(self, features_dict: Dict[str, float]) -> Dict[str, Any]:
        """
        Predict match outcome probabilities.
        
        Args:
            features_dict: Dict containing all feature values
            
        Returns:
            Dict with probabilities for home_win, draw, away_win and confidence
        """
        if not self.model:
            return {"home_win": 0.33, "draw": 0.34, "away_win": 0.33, "confidence": 0.0}
            
        # Ensure correct order
        X = np.array([[features_dict.get(f, 0.0) for f in self.feature_names]])
        
        probas = self.model.predict_proba(X)[0]
        
        # Classes: 0: away_win, 1: draw, 2: home_win
        away_prob = float(probas[0])
        draw_prob = float(probas[1])
        home_prob = float(probas[2])
        
        # Calculate confidence based on how decisive the model is
        max_prob = max(away_prob, draw_prob, home_prob)
        confidence = float((max_prob - 0.33) / 0.67) # Normalize relative to random guess
        
        from engine.probability_utils import normalize_outcome_probs
        normed = normalize_outcome_probs(home_prob * 100, draw_prob * 100, away_prob * 100)
        return {**normed, "confidence": confidence}

    def get_feature_importance(self) -> List[Dict[str, Any]]:
        """
        Returns feature importances for SHAP-style explanation.
        """
        if not self.model:
            return []
            
        importances = self.model.feature_importances_
        
        # Map to feature names and sort
        feat_imp = [
            {"feature": name, "importance": float(imp)} 
            for name, imp in zip(self.feature_names, importances)
        ]
        feat_imp.sort(key=lambda x: x["importance"], reverse=True)
        
        return feat_imp

# Singleton instance
ibm_bob = IBMBobModel()
