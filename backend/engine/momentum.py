"""
PressureLab AI - Momentum Engine
Estimates team momentum over the course of a match based on event patterns.
Momentum is a normalized 0-1 score for each team at each minute.
"""

import pandas as pd
import numpy as np
from typing import Optional


# Event type momentum impact values
EVENT_MOMENTUM = {
    'Goal': 0.25,
    'Shot': 0.08,
    'Shot On Target': 0.10,
    'Pass': 0.01,
    'Successful Dribble': 0.05,
    'Pressure': 0.02,
    'Interception': 0.04,
    'Tackle': 0.03,
    'Clearance': 0.02,
    'Foul Won': 0.03,
    'Foul Committed': -0.03,
    'Card': -0.06,
    'Yellow Card': -0.04,
    'Red Card': -0.15,
    'Miscontrol': -0.02,
    'Error': -0.05,
    'Own Goal For': 0.20,
    'Substitution': 0.02,
}


class MomentumEngine:
    """Computes team momentum over the match timeline."""

    def __init__(self, decay_rate: float = 0.92, window_size: int = 5):
        """
        Args:
            decay_rate: How quickly momentum decays per minute (0-1)
            window_size: Rolling window size in minutes
        """
        self.decay_rate = decay_rate
        self.window_size = window_size

    def compute_momentum_timeline(
        self,
        events_df: pd.DataFrame,
        home_team: str,
        away_team: str,
        total_minutes: int = 95,
    ) -> list[dict]:
        """
        Compute minute-by-minute momentum for both teams.
        
        Returns:
            List of {minute, home_momentum, away_momentum}
        """
        timeline = []
        home_accumulated = 0.5
        away_accumulated = 0.5

        for minute in range(0, total_minutes + 1):
            # Get events in the rolling window
            window_start = max(0, minute - self.window_size)
            window_events = events_df[
                (events_df['minute'] >= window_start) & 
                (events_df['minute'] <= minute)
            ]

            # Calculate raw momentum contribution
            home_raw = self._calc_team_momentum(window_events, home_team)
            away_raw = self._calc_team_momentum(window_events, away_team)

            # Apply decay and accumulate
            home_accumulated = home_accumulated * self.decay_rate + home_raw * (1 - self.decay_rate)
            away_accumulated = away_accumulated * self.decay_rate + away_raw * (1 - self.decay_rate)

            # Normalize to 0-1 range ensuring they sum roughly to 1
            total = home_accumulated + away_accumulated
            if total > 0:
                home_norm = home_accumulated / total
                away_norm = away_accumulated / total
            else:
                home_norm = 0.5
                away_norm = 0.5

            timeline.append({
                'minute': minute,
                'home_momentum': round(float(home_norm), 3),
                'away_momentum': round(float(away_norm), 3),
            })

        return timeline

    def _calc_team_momentum(self, events_df: pd.DataFrame, team: str) -> float:
        """
        Calculate raw momentum for a team from events in a window.
        """
        team_events = events_df[events_df['team'] == team]
        momentum = 0.5  # Base momentum

        for _, event in team_events.iterrows():
            event_type = event.get('type', '')
            outcome = str(event.get('outcome', '')).lower() if pd.notna(event.get('outcome')) else ''
            
            # Get base momentum impact
            impact = EVENT_MOMENTUM.get(event_type, 0.01)
            
            # Adjust for outcome
            if event_type == 'Shot':
                if 'goal' in outcome:
                    impact = EVENT_MOMENTUM['Goal']
                elif 'saved' in outcome or 'on target' in outcome:
                    impact = EVENT_MOMENTUM.get('Shot On Target', 0.10)
                else:
                    impact = 0.03  # Off target
            elif event_type == 'Pass':
                if 'incomplete' in outcome:
                    impact = -0.01
            elif event_type == 'Dribble':
                if 'complete' in outcome:
                    impact = EVENT_MOMENTUM.get('Successful Dribble', 0.05)
                else:
                    impact = -0.03
            
            momentum += impact

        return max(0.0, min(1.0, momentum))
