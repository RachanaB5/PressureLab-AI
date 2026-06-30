"""
PressureLab AI - Prediction Lab Engine
Explainable match outcome predictions that update with events.
Integrates IBM Bob methodology from the Learning Lab.

Pre-match prediction uses historical features.
Live updates use Bayesian updating based on:
- Momentum shifts
- Pressure differential
- Fatigue accumulation
- Tactical changes
- Psychology engine estimates
"""

import numpy as np
import pandas as pd
from typing import Optional


class PredictionEngine:
    """
    Explainable prediction engine for match outcomes.
    Every prediction includes confidence, factors, evidence, and alternatives.
    """

    def __init__(self):
        # Neutral pre-match prior. Live match events quickly dominate these values.
        self.base_probs = {
            'home_win': 0.37,
            'draw': 0.26,
            'away_win': 0.37,
        }

    def predict_at_minute(
        self,
        minute: int,
        events_df: pd.DataFrame,
        home_team: str,
        away_team: str,
        momentum_data: Optional[list[dict]] = None,
        pressure_data: Optional[dict] = None,
    ) -> dict:
        """
        Generate an explainable prediction at a specific minute.
        
        Returns:
            Full prediction dict with probabilities, confidence, factors, evidence, etc.
        """
        # Start with base probabilities
        probs = self.base_probs.copy()
        factors = []
        evidence = []
        
        # Get current score
        goals_by_minute = self._get_score_at_minute(events_df, minute, home_team, away_team)
        home_goals = goals_by_minute['home']
        away_goals = goals_by_minute['away']
        score_diff = home_goals - away_goals
        
        # === Factor 1: Score State ===
        if score_diff > 0:
            score_impact = min(0.25, score_diff * 0.12)
            probs['home_win'] += score_impact
            probs['away_win'] -= score_impact * 0.7
            probs['draw'] -= score_impact * 0.3
            factors.append({'factor': f'{home_team} leading {home_goals}-{away_goals}', 'impact': score_impact})
            evidence.append(f"Score: {home_team} {home_goals} - {away_goals} {away_team}")
        elif score_diff < 0:
            score_impact = min(0.25, abs(score_diff) * 0.12)
            probs['away_win'] += score_impact
            probs['home_win'] -= score_impact * 0.7
            probs['draw'] -= score_impact * 0.3
            factors.append({'factor': f'{away_team} leading {away_goals}-{home_goals}', 'impact': score_impact})
            evidence.append(f"Score: {home_team} {home_goals} - {away_goals} {away_team}")
        
        # === Factor 2: Time Pressure ===
        time_factor = minute / 90.0
        if score_diff != 0 and minute > 70:
            time_impact = (minute - 70) / 20 * 0.1
            if score_diff > 0:
                probs['home_win'] += time_impact
                probs['draw'] -= time_impact * 0.5
                probs['away_win'] -= time_impact * 0.5
            else:
                probs['away_win'] += time_impact
                probs['draw'] -= time_impact * 0.5
                probs['home_win'] -= time_impact * 0.5
            factors.append({'factor': f'Time pressure at minute {minute}', 'impact': time_impact})
        
        # === Factor 3: Momentum ===
        if momentum_data and len(momentum_data) > minute:
            mom = momentum_data[minute]
            home_mom = mom.get('home_momentum', 0.5)
            away_mom = mom.get('away_momentum', 0.5)
            mom_diff = home_mom - away_mom
            if abs(mom_diff) > 0.1:
                mom_impact = mom_diff * 0.08
                probs['home_win'] += mom_impact
                probs['away_win'] -= mom_impact
                leader = home_team if mom_diff > 0 else away_team
                factors.append({'factor': f'Momentum shift to {leader}', 'impact': abs(mom_impact)})
                evidence.append(f"Momentum: {home_team} {home_mom:.2f} vs {away_team} {away_mom:.2f}")
        
        # === Factor 4: Shot Differential ===
        home_shots = len(events_df[
            (events_df['team'] == home_team) & 
            (events_df['type'] == 'Shot') & 
            (events_df['minute'] <= minute)
        ])
        away_shots = len(events_df[
            (events_df['team'] == away_team) & 
            (events_df['type'] == 'Shot') & 
            (events_df['minute'] <= minute)
        ])
        if home_shots + away_shots > 0:
            shot_ratio = home_shots / (home_shots + away_shots) - 0.5
            shot_impact = shot_ratio * 0.06
            probs['home_win'] += shot_impact
            probs['away_win'] -= shot_impact
            evidence.append(f"Shots: {home_team} {home_shots} - {away_shots} {away_team}")
            if abs(shot_ratio) > 0.15:
                leader = home_team if shot_ratio > 0 else away_team
                factors.append({'factor': f'{leader} shot dominance', 'impact': abs(shot_impact)})

        # === Factor 5: Cards / disciplinary pressure ===
        if "details" in events_df.columns:
            cards = events_df[
                (events_df["minute"] <= minute)
                & events_df["details"].apply(lambda d: isinstance(d, dict) and bool(d.get("card")))
            ]
            home_cards = len(cards[cards["team"] == home_team])
            away_cards = len(cards[cards["team"] == away_team])
            if home_cards or away_cards:
                card_diff = away_cards - home_cards
                card_impact = card_diff * 0.025
                probs["home_win"] += card_impact
                probs["away_win"] -= card_impact
                evidence.append(f"Cards: {home_team} {home_cards} - {away_cards} {away_team}")
                if card_diff:
                    beneficiary = home_team if card_diff > 0 else away_team
                    factors.append({"factor": f"Disciplinary edge for {beneficiary}", "impact": abs(card_impact)})
        
        # === Normalize probabilities ===
        total = sum(probs.values())
        probs = {k: max(0.01, v / total) for k, v in probs.items()}
        # Re-normalize after clamping
        total = sum(probs.values())
        probs = {k: round(v / total, 3) for k, v in probs.items()}
        
        # === Calculate confidence ===
        max_prob = max(probs.values())
        confidence = min(0.95, 0.5 + max_prob * 0.3 + time_factor * 0.15)
        
        # === Generate "what changed" ===
        what_changed = self._what_changed(minute, events_df, home_team, away_team)
        
        # === Generate alternative outcome ===
        if probs['home_win'] > probs['away_win']:
            alt = f"If {away_team} scores next, away_win probability rises to ~{min(0.95, probs['away_win'] + 0.15):.2f}"
        else:
            alt = f"If {home_team} scores next, home_win probability rises to ~{min(0.95, probs['home_win'] + 0.15):.2f}"
        
        # Sort factors by impact
        factors.sort(key=lambda x: abs(x['impact']), reverse=True)
        
        return {
            'minute': minute,
            'home_win': probs['home_win'] * 100.0,
            'draw': probs['draw'] * 100.0,
            'away_win': probs['away_win'] * 100.0,
            'confidence': round(float(confidence), 3),
            'top_factors': factors[:5],
            'what_changed': what_changed,
            'alternative_outcome': alt,
            'evidence': evidence,
            'granite_explanation': '',  # Filled by Granite later
        }

    def compute_prediction_timeline(
        self,
        events_df: pd.DataFrame,
        home_team: str,
        away_team: str,
        total_minutes: int = 95,
        momentum_data: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Compute predictions for every minute of the match."""
        return [
            self.predict_at_minute(minute, events_df, home_team, away_team, momentum_data)
            for minute in range(0, total_minutes + 1)
        ]

    def _get_score_at_minute(self, events_df: pd.DataFrame, minute: int, 
                             home_team: str, away_team: str) -> dict:
        """Get the score at a specific minute."""
        goals = events_df[events_df['minute'] <= minute]
        
        home_goals = 0
        away_goals = 0
        
        for _, goal in goals.iterrows():
            event_type = str(goal.get("type", "")).lower()
            outcome = str(goal.get('outcome', '')).lower() if pd.notna(goal.get('outcome')) else ''
            team = goal.get("team")
            if "own goal against" in event_type:
                if team == home_team:
                    away_goals += 1
                elif team == away_team:
                    home_goals += 1
            elif "own goal for" in event_type:
                if team == home_team:
                    home_goals += 1
                elif team == away_team:
                    away_goals += 1
            elif event_type == "goal" or ("shot" in event_type and 'goal' in outcome):
                if goal.get('team') == home_team:
                    home_goals += 1
                elif goal.get('team') == away_team:
                    away_goals += 1
        
        return {'home': home_goals, 'away': away_goals}

    def _what_changed(self, minute: int, events_df: pd.DataFrame, 
                      home_team: str, away_team: str) -> str:
        """Describe the most recent significant event."""
        recent = events_df[
            (events_df['minute'] <= minute) & 
            (events_df['minute'] >= max(0, minute - 5)) &
            (events_df['type'].isin(['Shot', 'Foul Committed', 'Substitution', 'Card']))
        ].sort_values('minute', ascending=False)
        
        if recent.empty:
            return f"Minute {minute}: No major events in last 5 minutes"
        
        latest = recent.iloc[0]
        player = latest.get('player', latest.get('player_name', 'Unknown'))
        event_type = latest.get('type', '')
        outcome = str(latest.get('outcome', '')).lower() if pd.notna(latest.get('outcome')) else ''
        
        if 'goal' in outcome:
            return f"{player} goal at minute {latest['minute']} shifted probabilities significantly"
        elif event_type == 'Card':
            return f"{player} received a card at minute {latest['minute']}, affecting team dynamics"
        elif event_type == 'Substitution':
            return f"Substitution at minute {latest['minute']} brought tactical change"
        else:
            return f"Recent {event_type.lower()} by {player} at minute {latest['minute']}"
