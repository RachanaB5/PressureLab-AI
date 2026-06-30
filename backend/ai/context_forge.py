"""
PressureLab AI - Context Forge
Dynamic context manager that builds rich player, tournament, and tactical context
from real StatsBomb event data. No hardcoded player history strings.
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class ContextForgeClient:
    """
    Dynamic context manager for PressureLab AI.
    Builds and retrieves contextual memory from actual match event data.
    Stores player context, tournament context, and tactical documents in-memory.
    """

    def __init__(self):
        # In-memory knowledge stores
        self._player_context: dict[int, dict] = {}
        self._tournament_context: dict = {}
        self._match_contexts: dict[int, dict] = {}
        self._tactical_documents: list[dict] = []
        self._historical_situations: list[dict] = []
        self._initialized = False

    def initialize_from_events(self, events_df: pd.DataFrame, match_info: dict):
        """
        Auto-populate all context stores from real StatsBomb event data.

        Args:
            events_df: DataFrame with columns like player_id, player_name, team,
                       type/event_type, minute, second, outcome, under_pressure, etc.
            match_info: dict with home_team, away_team, home_score, away_score, etc.
        """
        logger.info("Context Forge: initializing from event data...")

        # Normalize 'type' column
        if 'type' not in events_df.columns and 'event_type' in events_df.columns:
            events_df = events_df.copy()
            events_df['type'] = events_df['event_type']

        self._build_player_contexts(events_df, match_info)
        self._build_tournament_context(match_info)
        self._build_match_context(events_df, match_info)
        self._build_historical_situations(events_df, match_info)
        self._initialized = True
        logger.info(
            f"Context Forge: initialized with {len(self._player_context)} player profiles, "
            f"{len(self._historical_situations)} historical situations"
        )

    # ────────────────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────────────────

    def get_player_context(self, player_name: str, match_events: Optional[pd.DataFrame] = None) -> str:
        """
        Retrieve dynamically-built context for a player.
        Falls back to building context on-the-fly from match_events if not pre-initialized.
        """
        # Try exact match first, then partial
        ctx = None
        for pid, pctx in self._player_context.items():
            if pctx.get('name', '') == player_name:
                ctx = pctx
                break
        if ctx is None:
            for pid, pctx in self._player_context.items():
                if player_name in pctx.get('name', ''):
                    ctx = pctx
                    break

        if ctx is None and match_events is not None:
            ctx = self._build_single_player_context(player_name, match_events)

        if ctx is None:
            return f"Context for {player_name}: No event data available for this player."

        lines = [f"Dynamic Context for {ctx['name']} ({ctx['team']}):"]
        lines.append(f"  Total actions: {ctx['total_events']}")
        lines.append(f"  Passes: {ctx['passes_total']} ({ctx['pass_accuracy']:.0%} accuracy)")
        lines.append(f"  Under-pressure actions: {ctx['under_pressure_events']} ({ctx['under_pressure_pct']:.0%} of total)")
        if ctx['shots'] > 0:
            lines.append(f"  Shots: {ctx['shots']} (on target: {ctx['shots_on_target']})")
        if ctx['goals'] > 0:
            lines.append(f"  Goals: {ctx['goals']}")
        if ctx['tackles'] > 0:
            lines.append(f"  Tackles: {ctx['tackles']}")
        if ctx['fouls_committed'] > 0:
            lines.append(f"  Fouls committed: {ctx['fouls_committed']}")
        if ctx['key_moments']:
            lines.append("  Key moments:")
            for km in ctx['key_moments'][:5]:
                lines.append(f"    - {km}")
        if ctx['pressure_profile']:
            lines.append(f"  Pressure profile: {ctx['pressure_profile']}")

        return "\n".join(lines)

    def get_tournament_context(self) -> str:
        """Return structured tournament context built from match data."""
        ctx = self._tournament_context
        if not ctx:
            return "Tournament context not yet initialized."

        lines = [
            f"{ctx.get('competition', 'Tournament')} Context:",
            f"  Match: {ctx.get('home_team', '?')} vs {ctx.get('away_team', '?')}",
            f"  Result: {ctx.get('home_score', 0)}-{ctx.get('away_score', 0)}",
            f"  Venue: {ctx.get('venue', 'Unknown')}",
            f"  Date: {ctx.get('match_date', 'Unknown')}",
        ]
        if ctx.get('narrative'):
            lines.append(f"  Narrative: {ctx['narrative']}")
        return "\n".join(lines)

    def get_match_context(self, match_id: int, minute: int) -> dict:
        """
        Return match context at a specific minute, including score, momentum indicators,
        key events in the window, and team control metrics.
        """
        mctx = self._match_contexts.get(match_id)
        if mctx is None:
            return {"minute": minute, "context": "Match context not available."}

        # Find events up to this minute
        minute_data = {
            "minute": minute,
            "home_team": mctx.get("home_team", ""),
            "away_team": mctx.get("away_team", ""),
        }

        # Score at minute
        goals_before = [g for g in mctx.get("goals", []) if g["minute"] <= minute]
        home_goals = sum(1 for g in goals_before if g["team"] == mctx["home_team"])
        away_goals = sum(1 for g in goals_before if g["team"] == mctx["away_team"])
        minute_data["score"] = f"{home_goals}-{away_goals}"

        # Key events in recent 5-minute window
        all_key = mctx.get("key_events", [])
        recent_key = [e for e in all_key if max(0, minute - 5) <= e["minute"] <= minute]
        minute_data["recent_key_events"] = recent_key

        # Possession proxy from event counts
        minute_events = mctx.get("events_by_minute", {})
        home_count = sum(minute_events.get(m, {}).get(mctx["home_team"], 0) for m in range(max(0, minute - 5), minute + 1))
        away_count = sum(minute_events.get(m, {}).get(mctx["away_team"], 0) for m in range(max(0, minute - 5), minute + 1))
        total = home_count + away_count
        minute_data["home_control"] = round(home_count / total, 2) if total > 0 else 0.5
        minute_data["away_control"] = round(away_count / total, 2) if total > 0 else 0.5

        return minute_data

    def get_similar_historical_situations(self, situation_description: str) -> list[dict]:
        """
        Return structured historical match situations similar to the description.
        Uses keyword matching against the situations built from event data.
        """
        if not self._historical_situations:
            return []

        keywords = set(situation_description.lower().split())
        scored = []
        for sit in self._historical_situations:
            sit_words = set(sit.get("description", "").lower().split())
            overlap = len(keywords & sit_words)
            if overlap > 0:
                scored.append((overlap, sit))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:5]]

    def add_tactical_document(self, doc: dict):
        """Add a processed tactical document to the knowledge base."""
        self._tactical_documents.append(doc)

    def get_tactical_documents(self) -> list[dict]:
        """Return all tactical documents in the knowledge base."""
        return self._tactical_documents

    # ────────────────────────────────────────────────────────────────────────
    # Internal builders
    # ────────────────────────────────────────────────────────────────────────

    def _build_player_contexts(self, events_df: pd.DataFrame, match_info: dict):
        """Build player context from event aggregation."""
        players = events_df.groupby('player_id')

        for pid, group in players:
            pid = int(pid)
            if pid <= 0:
                continue

            name = str(group.iloc[0].get('player_name', group.iloc[0].get('player', 'Unknown')))
            team = str(group.iloc[0].get('team', ''))

            total = len(group)
            passes = group[group['type'] == 'Pass']
            passes_complete = passes[
                passes['outcome'].apply(
                    lambda x: pd.isna(x) or str(x) == '' or 'complete' in str(x).lower()
                )
            ] if len(passes) > 0 else passes
            pass_accuracy = len(passes_complete) / len(passes) if len(passes) > 0 else 0.0

            shots = group[group['type'] == 'Shot']
            goals = shots[shots['outcome'].apply(lambda x: 'goal' in str(x).lower())] if len(shots) > 0 else shots[:0]
            shots_on_target = shots[shots['outcome'].apply(
                lambda x: 'goal' in str(x).lower() or 'saved' in str(x).lower()
            )] if len(shots) > 0 else shots[:0]

            under_pressure_events = group[group.get('under_pressure', False) == True] if 'under_pressure' in group.columns else group[:0]

            tackles = group[group['type'] == 'Tackle']
            fouls = group[group['type'] == 'Foul Committed']
            pressures = group[group['type'] == 'Pressure']
            interceptions = group[group['type'] == 'Interception']

            # Identify key moments
            key_moments = []
            for _, row in goals.iterrows():
                key_moments.append(f"Goal at minute {row['minute']}")
            for _, row in group[group['type'].isin(['Foul Committed'])].iterrows():
                outcome_str = str(row.get('outcome', '')).lower()
                if 'card' in outcome_str or 'yellow' in outcome_str or 'red' in outcome_str:
                    key_moments.append(f"Card at minute {row['minute']}")
                else:
                    key_moments.append(f"Foul committed at minute {row['minute']}")

            # Build pressure profile text
            up_pct = len(under_pressure_events) / total if total > 0 else 0
            if up_pct > 0.4:
                pressure_profile = "Frequently under pressure — high defensive attention from opponents"
            elif up_pct > 0.2:
                pressure_profile = "Moderate pressure exposure — involved in contested areas"
            else:
                pressure_profile = "Low pressure exposure — operating in space or limited involvement"

            self._player_context[pid] = {
                'player_id': pid,
                'name': name,
                'team': team,
                'total_events': total,
                'passes_total': len(passes),
                'pass_accuracy': pass_accuracy,
                'shots': len(shots),
                'shots_on_target': len(shots_on_target),
                'goals': len(goals),
                'tackles': len(tackles),
                'fouls_committed': len(fouls),
                'pressures': len(pressures),
                'interceptions': len(interceptions),
                'under_pressure_events': len(under_pressure_events),
                'under_pressure_pct': up_pct,
                'key_moments': key_moments,
                'pressure_profile': pressure_profile,
            }

    def _build_single_player_context(self, player_name: str, events_df: pd.DataFrame) -> Optional[dict]:
        """Build context for a single player on-the-fly from events."""
        if 'type' not in events_df.columns and 'event_type' in events_df.columns:
            events_df = events_df.copy()
            events_df['type'] = events_df['event_type']

        mask = events_df['player_name'].apply(lambda x: player_name in str(x)) if 'player_name' in events_df.columns else pd.Series([False] * len(events_df))
        player_events = events_df[mask]

        if player_events.empty:
            return None

        pid = int(player_events.iloc[0].get('player_id', 0))
        self._build_player_contexts(player_events, {})
        return self._player_context.get(pid)

    def _build_tournament_context(self, match_info: dict):
        """Build tournament context from match metadata."""
        home = match_info.get('home_team', 'Home')
        away = match_info.get('away_team', 'Away')
        home_score = match_info.get('home_score', 0)
        away_score = match_info.get('away_score', 0)
        competition = match_info.get('competition', 'Unknown Competition')

        narrative = f"{home} vs {away} in {competition}. Final score: {home_score}-{away_score}."

        self._tournament_context = {
            'competition': competition,
            'home_team': home,
            'away_team': away,
            'home_score': home_score,
            'away_score': away_score,
            'venue': match_info.get('venue', 'Unknown'),
            'match_date': match_info.get('match_date', 'Unknown'),
            'narrative': narrative,
        }

    def _build_match_context(self, events_df: pd.DataFrame, match_info: dict):
        """Build minute-by-minute match context from events."""
        match_id = match_info.get('id', match_info.get('statsbomb_id', 1))
        home = match_info.get('home_team', 'Home')
        away = match_info.get('away_team', 'Away')

        # Extract goals
        goals = []
        candidate_events = events_df[
            (events_df['type'] == 'Shot')
            | (events_df['type'].astype(str).str.contains('Own Goal|Goal', case=False, na=False))
        ]
        for _, row in candidate_events.iterrows():
            event_type = str(row.get('type', '')).lower()
            outcome = str(row.get('outcome', '')).lower()
            team = str(row.get('team', ''))
            goal_team = None
            if 'own goal against' in event_type:
                goal_team = away if team == home else home if team == away else None
            elif 'own goal for' in event_type:
                goal_team = team
            elif event_type == 'goal' or ('shot' in event_type and 'goal' in outcome):
                goal_team = team
            if goal_team:
                goals.append({
                    'minute': int(row['minute']),
                    'team': goal_team,
                    'player': str(row.get('player_name', row.get('player', 'Unknown'))),
                })

        # Extract key events (goals, cards, fouls leading to penalties, etc.)
        key_events = []
        for g in goals:
            key_events.append({
                'minute': g['minute'],
                'type': 'Goal',
                'team': g['team'],
                'player': g['player'],
                'description': f"Goal by {g['player']} ({g['team']})",
            })

        for _, row in events_df[events_df['type'].isin(['Foul Committed'])].iterrows():
            outcome = str(row.get('outcome', '')).lower()
            if 'penalty' in outcome or 'card' in outcome:
                key_events.append({
                    'minute': int(row['minute']),
                    'type': row['type'],
                    'team': str(row['team']),
                    'player': str(row.get('player_name', row.get('player', 'Unknown'))),
                    'description': f"{row['type']} by {row.get('player_name', 'Unknown')} — {outcome}",
                })

        key_events.sort(key=lambda x: x['minute'])

        # Events-by-minute count per team
        events_by_minute = defaultdict(lambda: defaultdict(int))
        for _, row in events_df.iterrows():
            m = int(row['minute'])
            t = str(row['team'])
            events_by_minute[m][t] += 1

        self._match_contexts[match_id] = {
            'match_id': match_id,
            'home_team': home,
            'away_team': away,
            'goals': goals,
            'key_events': key_events,
            'events_by_minute': dict(events_by_minute),
        }

    def _build_historical_situations(self, events_df: pd.DataFrame, match_info: dict):
        """
        Build historical situation records from the match data.
        Each situation captures the game state at key moments for similarity lookup.
        """
        home = match_info.get('home_team', 'Home')
        away = match_info.get('away_team', 'Away')

        # Identify key moments: goals, cards, substitutions
        shot_events = events_df[events_df['type'] == 'Shot']
        goal_events = shot_events[shot_events['outcome'].apply(lambda x: 'goal' in str(x).lower())]

        home_goals = 0
        away_goals = 0

        for _, g in goal_events.iterrows():
            team = str(g['team'])
            minute = int(g['minute'])
            player = str(g.get('player_name', g.get('player', 'Unknown')))

            if team == home:
                home_goals += 1
            else:
                away_goals += 1

            self._historical_situations.append({
                'match': f"{home} vs {away}",
                'competition': match_info.get('competition', ''),
                'minute': minute,
                'event': 'goal',
                'team': team,
                'player': player,
                'score_after': f"{home_goals}-{away_goals}",
                'description': (
                    f"Goal scored by {player} ({team}) at minute {minute}. "
                    f"Score became {home_goals}-{away_goals} in a {match_info.get('competition', '')} match. "
                    f"{'Leading team extending lead' if (home_goals - away_goals) * (1 if team == home else -1) > 1 else 'Close contest'}."
                ),
            })

        # Add pressure-heavy periods
        if 'under_pressure' in events_df.columns:
            for period_start in range(0, 95, 5):
                window = events_df[
                    (events_df['minute'] >= period_start) &
                    (events_df['minute'] < period_start + 5)
                ]
                if window.empty:
                    continue
                pressure_ratio = window['under_pressure'].sum() / len(window) if len(window) > 0 else 0
                if pressure_ratio > 0.35:
                    dominant_team = window['team'].value_counts().index[0] if len(window) > 0 else home
                    self._historical_situations.append({
                        'match': f"{home} vs {away}",
                        'competition': match_info.get('competition', ''),
                        'minute': period_start,
                        'event': 'high_pressure_period',
                        'team': dominant_team,
                        'player': '',
                        'score_after': '',
                        'description': (
                            f"High-pressure period at minutes {period_start}-{period_start + 5} "
                            f"with {pressure_ratio:.0%} of actions under pressure. "
                            f"{dominant_team} dominated possession during this phase."
                        ),
                    })

        logger.info(f"Context Forge: built {len(self._historical_situations)} historical situations")
