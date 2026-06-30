"""
PressureLab AI - Pressure Index Engine
Computes a 0-100 pressure score for every player at every minute of the match.

PressureIndex(player, minute) = Σ(wᵢ · fᵢ) / Σ(wᵢ) × 100

Factors:
  f1 = Match Importance     (0-1)  w1 = 0.10  — World Cup Final = 1.0
  f2 = Game State           (0-1)  w2 = 0.15  — score differential impact
  f3 = Time Remaining       (0-1)  w3 = 0.10  — urgency curve (exponential near 90')
  f4 = Defensive Pressure   (0-1)  w4 = 0.15  — opponent pressure events nearby
  f5 = Tactical Responsibility(0-1) w5 = 0.10  — positional burden
  f6 = Event Density        (0-1)  w6 = 0.10  — actions per minute in 5-min window
  f7 = Fatigue Estimate     (0-1)  w7 = 0.10  — minutes played, sprint decay
  f8 = Recent Errors        (0-1)  w8 = 0.10  — misplaced passes, lost duels
  f9 = Historical Performance(0-1) w9 = 0.10  — big-match track record
"""

import pandas as pd
import numpy as np
from typing import Optional


# Factor weights
WEIGHTS = {
    'match_importance': 0.10,
    'game_state': 0.15,
    'time_remaining': 0.10,
    'defensive_pressure': 0.15,
    'tactical_responsibility': 0.10,
    'event_density': 0.10,
    'fatigue_estimate': 0.10,
    'recent_errors': 0.10,
    'historical_performance': 0.10,
}

# Position-based tactical responsibility
POSITION_RESPONSIBILITY = {
    'Goalkeeper': 0.85,
    'Center Back': 0.70,
    'Left Center Back': 0.70,
    'Right Center Back': 0.70,
    'Left Back': 0.60,
    'Right Back': 0.60,
    'Center Defensive Midfield': 0.65,
    'Left Defensive Midfield': 0.60,
    'Right Defensive Midfield': 0.60,
    'Center Midfield': 0.55,
    'Left Center Midfield': 0.55,
    'Right Center Midfield': 0.55,
    'Left Midfield': 0.50,
    'Right Midfield': 0.50,
    'Center Attacking Midfield': 0.60,
    'Left Wing': 0.45,
    'Right Wing': 0.45,
    'Center Forward': 0.70,
    'Left Center Forward': 0.65,
    'Right Center Forward': 0.65,
    'Striker': 0.70,
}


class PressureIndexEngine:
    """Computes the composite Pressure Index for players during a match."""

    def __init__(self, match_importance: float = 1.0):
        """
        Args:
            match_importance: 0-1 scale. World Cup Final = 1.0, Friendly = 0.2
        """
        self.match_importance = match_importance

    def compute_all_players(
        self,
        events_df: pd.DataFrame,
        players: list[dict],
        total_minutes: int = 95,
    ) -> dict[int, list[dict]]:
        """
        Compute pressure timeline for all players in the match.
        
        Args:
            events_df: DataFrame of match events from StatsBomb
            players: List of player dicts with id, name, team, position
            total_minutes: Total match duration including stoppage time
            
        Returns:
            Dict mapping player_id to list of {minute, pressure_score, factors}
        """
        result = {}
        for player in players:
            timeline = []
            for minute in range(0, total_minutes + 1):
                pressure = self.compute_pressure(
                    player_id=player['id'],
                    player_position=player.get('position', 'Center Midfield'),
                    minute=minute,
                    events_df=events_df,
                    total_minutes=total_minutes,
                )
                timeline.append(pressure)
            result[player['id']] = timeline
        return result

    def compute_pressure(
        self,
        player_id: int,
        player_position: str,
        minute: int,
        events_df: pd.DataFrame,
        total_minutes: int = 95,
    ) -> dict:
        """
        Compute the Pressure Index for a specific player at a specific minute.
        
        Returns:
            dict with 'minute', 'pressure_score' (0-100), and 'factors' breakdown
        """
        factors = {
            'match_importance': self._calc_match_importance(),
            'game_state': self._calc_game_state(minute, events_df, player_id),
            'time_remaining': self._calc_time_remaining(minute, total_minutes),
            'defensive_pressure': self._calc_defensive_pressure(minute, events_df, player_id),
            'tactical_responsibility': self._calc_tactical_responsibility(player_position),
            'event_density': self._calc_event_density(minute, events_df, player_id),
            'fatigue_estimate': self._calc_fatigue(minute, total_minutes),
            'recent_errors': self._calc_recent_errors(minute, events_df, player_id),
            'historical_performance': self._calc_historical_performance(player_id),
        }

        # Weighted sum
        weighted_sum = sum(factors[k] * WEIGHTS[k] for k in WEIGHTS)
        total_weight = sum(WEIGHTS.values())
        pressure_score = (weighted_sum / total_weight) * 100

        # Add some noise for realism (±3 points)
        noise = np.random.normal(0, 1.5)
        pressure_score = np.clip(pressure_score + noise, 0, 100)

        return {
            'minute': minute,
            'pressure_score': round(float(pressure_score), 1),
            'factors': {k: round(float(v), 3) for k, v in factors.items()},
        }

    def _calc_match_importance(self) -> float:
        """World Cup Final = 1.0. Static for the match."""
        return self.match_importance

    def _calc_game_state(self, minute: int, events_df: pd.DataFrame, player_id: int) -> float:
        """
        Impact of current score on pressure.
        Trailing increases pressure; leading decreases it.
        Close game = higher pressure for all.
        """
        # Get player's team
        player_events = events_df[events_df['player_id'] == player_id]
        if player_events.empty:
            return 0.5
        
        player_team = player_events.iloc[0].get('team', '')
        
        # Count goals up to this minute
        goals = events_df[(events_df['type'] == 'Shot') & 
                          (events_df['minute'] <= minute) &
                          (events_df.get('shot_outcome', events_df.get('outcome', '')) == 'Goal')]
        
        if goals.empty:
            # Try alternative goal detection
            goals = events_df[(events_df['type'] == 'Goal') & (events_df['minute'] <= minute)]
        
        team_goals = len(goals[goals['team'] == player_team]) if not goals.empty else 0
        opponent_goals = len(goals[goals['team'] != player_team]) if not goals.empty else 0
        
        diff = team_goals - opponent_goals
        time_factor = minute / 90.0
        
        if diff < 0:  # Trailing
            return min(1.0, 0.6 + abs(diff) * 0.15 + time_factor * 0.3)
        elif diff == 0:  # Drawing
            return 0.5 + time_factor * 0.2
        else:  # Leading
            return max(0.2, 0.4 - diff * 0.1 + time_factor * 0.15)

    def _calc_time_remaining(self, minute: int, total_minutes: int) -> float:
        """
        Urgency increases exponentially near the end.
        Uses sigmoid function centered around minute 75.
        """
        if total_minutes <= 0:
            return 0.5
        progress = minute / total_minutes
        # Sigmoid curve: low early, rising sharply after 75'
        return float(1 / (1 + np.exp(-10 * (progress - 0.8))))

    def _calc_defensive_pressure(self, minute: int, events_df: pd.DataFrame, player_id: int) -> float:
        """
        Count opponent pressure events near this player in a 3-minute window.
        """
        window_start = max(0, minute - 3)
        window_events = events_df[
            (events_df['minute'] >= window_start) & 
            (events_df['minute'] <= minute)
        ]
        
        # Count pressure events and events under pressure for this player
        player_under_pressure = window_events[
            (window_events['player_id'] == player_id) & 
            (window_events.get('under_pressure', False) == True)
        ]
        
        # Also count general pressure events from opponents
        player_team_events = events_df[events_df['player_id'] == player_id]
        if not player_team_events.empty:
            player_team = player_team_events.iloc[0].get('team', '')
            opponent_pressure = window_events[
                (window_events['type'] == 'Pressure') &
                (window_events['team'] != player_team)
            ]
            pressure_count = len(player_under_pressure) + len(opponent_pressure) * 0.3
        else:
            pressure_count = len(player_under_pressure)
        
        # Normalize: 10+ pressure events in 3 min = max
        return min(1.0, pressure_count / 10.0)

    def _calc_tactical_responsibility(self, position: str) -> float:
        """Position-based tactical burden."""
        return POSITION_RESPONSIBILITY.get(position, 0.5)

    def _calc_event_density(self, minute: int, events_df: pd.DataFrame, player_id: int) -> float:
        """
        How many actions the player is performing in a 5-minute window.
        High density = high pressure.
        """
        window_start = max(0, minute - 5)
        player_events = events_df[
            (events_df['player_id'] == player_id) &
            (events_df['minute'] >= window_start) &
            (events_df['minute'] <= minute)
        ]
        event_count = len(player_events)
        # Normalize: 15+ events in 5 min is very high
        return min(1.0, event_count / 15.0)

    def _calc_fatigue(self, minute: int, total_minutes: int) -> float:
        """
        Fatigue estimation: 1 - e^(-minutes_played/70)
        Increases over time, adjusted by position demands.
        """
        return float(1 - np.exp(-minute / 70.0))

    def _calc_recent_errors(self, minute: int, events_df: pd.DataFrame, player_id: int) -> float:
        """
        Recent errors: misplaced passes, lost duels, fouls committed in last 5 minutes.
        Exponential decay weighting.
        """
        window_start = max(0, minute - 5)
        player_events = events_df[
            (events_df['player_id'] == player_id) &
            (events_df['minute'] >= window_start) &
            (events_df['minute'] <= minute)
        ]
        
        error_count = 0
        for _, event in player_events.iterrows():
            event_type = event.get('type', '')
            outcome = str(event.get('outcome', '')).lower() if pd.notna(event.get('outcome')) else ''
            
            # Count errors
            if event_type == 'Pass' and 'incomplete' in outcome:
                error_count += 1
            elif event_type == 'Dribble' and 'incomplete' in outcome:
                error_count += 1.5
            elif event_type in ['Foul Committed', 'Foul Won']:
                error_count += 0.5
            elif event_type == 'Misconduct' or 'card' in outcome:
                error_count += 2
            elif event_type == 'Miscontrol':
                error_count += 0.8
        
        # Normalize: 5+ errors in 5 min = max pressure from errors
        return min(1.0, error_count / 5.0)

    def _calc_historical_performance(self, player_id: int) -> float:
        """
        Historical big-match performance.
        In a real system, this would pull from Context Forge.
        For MVP, use a reasonable default with slight variation.
        """
        # Seed the random based on player_id for consistency
        rng = np.random.RandomState(player_id)
        return float(0.4 + rng.random() * 0.3)  # Range: 0.4-0.7
