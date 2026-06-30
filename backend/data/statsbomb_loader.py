"""
PressureLab AI - StatsBomb Data Loader
Loads and processes the 2018 FIFA World Cup Final (France vs Croatia) from StatsBomb Open Data.
"""

import pandas as pd
import numpy as np
import json
import logging
from typing import Optional
from pathlib import Path
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# 2018 FIFA World Cup: competition_id=43, season_id=3
WORLD_CUP_2018 = {"competition_id": 43, "season_id": 3}

# France vs Croatia World Cup Final match_id
# This is looked up dynamically but we cache it
FINAL_MATCH_ID = 8658  # StatsBomb match ID for France vs Croatia 2018 WC Final


class StatsBombLoader:
    """Loads and processes StatsBomb open data."""

    def __init__(self):
        self._events_cache: dict[int, pd.DataFrame] = {}
        self._matches_cache: Optional[pd.DataFrame] = None

    def load_world_cup_final(self) -> dict:
        """
        Load the 2018 FIFA World Cup Final data.
        Returns dict with 'match_info', 'events', 'players', 'lineups'.
        """
        try:
            from statsbombpy import sb
            
            # Get matches for 2018 World Cup
            matches = sb.matches(
                competition_id=WORLD_CUP_2018["competition_id"],
                season_id=WORLD_CUP_2018["season_id"],
            )
            
            # Find the final
            final = matches[
                (matches['home_team'] == 'France') & 
                (matches['away_team'] == 'Croatia') |
                (matches['home_team'] == 'Croatia') & 
                (matches['away_team'] == 'France')
            ]
            
            if final.empty:
                logger.warning("Could not find France vs Croatia match, using fallback data")
                return self._generate_fallback_data()
            
            match_id = int(final.iloc[0]['match_id'])
            logger.info(f"Found World Cup Final: match_id={match_id}")
            
            # Load events
            events = sb.events(match_id=match_id)
            logger.info(f"Loaded {len(events)} events for match {match_id}")
            
            # Load lineups
            lineups = sb.lineups(match_id=match_id)
            
            # Process match info
            match_row = final.iloc[0]
            match_info = {
                'id': 1,
                'statsbomb_id': match_id,
                'home_team': str(match_row.get('home_team', 'France')),
                'away_team': str(match_row.get('away_team', 'Croatia')),
                'home_score': int(match_row.get('home_score', 4)),
                'away_score': int(match_row.get('away_score', 2)),
                'competition': '2018 FIFA World Cup',
                'season': '2018',
                'match_date': '2018-07-15',
                'venue': 'Luzhniki Stadium, Moscow',
            }
            
            # Process events into our format
            processed_events = self._process_events(events, match_id)
            
            # Extract players
            players = self._extract_players(events, lineups)
            
            return {
                'match_info': match_info,
                'events': processed_events,
                'players': players,
                'raw_events': events,
            }
            
        except ImportError:
            logger.warning("statsbombpy not installed, using fallback data")
            return self._generate_fallback_data()
        except Exception as e:
            logger.error(f"Error loading StatsBomb data: {e}")
            return self._generate_fallback_data()

    def match_exists(self, match_id: int) -> bool:
        """Check if event file exists in StatsBomb open-data repo."""
        url = f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json"
        try:
            req = Request(url, method="HEAD")
            with urlopen(req, timeout=8) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _teams_from_lineups(self, lineups) -> tuple[str, str]:
        if isinstance(lineups, dict):
            teams = list(lineups.keys())
            if len(teams) >= 2:
                return str(teams[0]), str(teams[1])
        return "Home", "Away"

    def _scores_from_events(self, events, home: str, away: str) -> tuple[int, int]:
        home_goals = 0
        away_goals = 0
        if events is None or len(events) == 0:
            return home_goals, away_goals
        for _, event in events.iterrows():
            if str(event.get("type", "")) != "Shot":
                continue
            if str(event.get("shot_outcome", "") or "") != "Goal":
                continue
            team = str(event.get("team", ""))
            if team == home:
                home_goals += 1
            elif team == away:
                away_goals += 1
        return home_goals, away_goals

    def load_match_by_statsbomb_id(self, match_id: int) -> dict:
        """Load any StatsBomb open-data match by match_id."""
        if not self.match_exists(match_id):
            raise ValueError(
                f"Match {match_id} is not in StatsBomb open data. "
                "Try a World Cup, Euro, Premier League, or La Liga match from search."
            )
        try:
            from statsbombpy import sb
            from engine.match_catalog import get_catalog_entry

            events = sb.events(match_id=match_id)
            lineups = sb.lineups(match_id=match_id)
            catalog = get_catalog_entry(match_id)

            if catalog:
                home = catalog["home_team"]
                away = catalog["away_team"]
                competition = catalog["competition"]
                season = catalog.get("season", "")
                match_date = catalog.get("match_date", "")
            else:
                home, away = self._teams_from_lineups(lineups)
                if home == "Home" and "team" in events.columns:
                    teams = [str(t) for t in events["team"].dropna().unique()[:2]]
                    home = teams[0] if teams else home
                    away = teams[1] if len(teams) > 1 else away
                competition = "StatsBomb Match"
                season = ""
                match_date = ""

            home_score, away_score = self._scores_from_events(events, home, away)
            match_info = {
                "statsbomb_id": match_id,
                "home_team": home,
                "away_team": away,
                "home_score": home_score,
                "away_score": away_score,
                "competition": competition,
                "season": season,
                "match_date": match_date,
                "venue": "",
            }
            processed = self._process_events(events, match_id)
            players = self._extract_players(events, lineups)
            return {"match_info": match_info, "events": processed, "players": players}
        except ImportError:
            raise RuntimeError("statsbombpy not installed")
        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to load match %s: %s", match_id, e)
            raise

    def _process_events(self, events: pd.DataFrame, match_id: int) -> list[dict]:
        """Process raw StatsBomb events into our schema with full coordinates."""
        processed = []

        for idx, event in events.iterrows():
            loc_x, loc_y = self._extract_location(event)
            event_type = str(event.get("type", ""))
            outcome = None

            if event_type == "Shot":
                shot_outcome = event.get("shot_outcome", None)
                if pd.notna(shot_outcome):
                    outcome = str(shot_outcome)
            elif event_type == "Pass":
                pass_outcome = event.get("pass_outcome", None)
                if pd.notna(pass_outcome):
                    outcome = str(pass_outcome)
                else:
                    outcome = "Complete"
            elif event_type == "Dribble":
                dribble_outcome = event.get("dribble_outcome", None)
                if pd.notna(dribble_outcome):
                    outcome = str(dribble_outcome)

            under_pressure = bool(event.get("under_pressure", False))
            player_name = str(event.get("player", "")) if pd.notna(event.get("player")) else "Unknown"
            player_id = int(event.get("player_id", 0)) if pd.notna(event.get("player_id")) else 0
            team = str(event.get("team", "")) if pd.notna(event.get("team")) else ""

            processed.append({
                "id": len(processed) + 1,
                "match_id": match_id,
                "event_type": event_type,
                "minute": int(event.get("minute", 0)),
                "second": int(event.get("second", 0)),
                "player_name": player_name,
                "player_id": player_id,
                "team": team,
                "location_x": loc_x,
                "location_y": loc_y,
                "outcome": outcome,
                "under_pressure": under_pressure,
                "details": self._build_event_details(event, event_type),
            })

        return processed

    def _safe_float(self, val) -> float | None:
        try:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return float(val)
        except (TypeError, ValueError):
            return None

    def _parse_xy(self, val) -> tuple[float | None, float | None]:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None, None
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            return self._safe_float(val[0]), self._safe_float(val[1])
        return None, None

    def _extract_location(self, event: pd.Series) -> tuple[float | None, float | None]:
        if "location" in event.index:
            loc = event["location"]
            if loc is not None and not (isinstance(loc, float) and pd.isna(loc)):
                lx, ly = self._parse_xy(loc)
                if lx is not None and ly is not None:
                    return lx, ly
        lx = self._safe_float(event.get("location_x"))
        ly = self._safe_float(event.get("location_y"))
        if lx is not None and ly is not None:
            return lx, ly
        return None, None

    def _build_event_details(self, event: pd.Series, event_type: str) -> dict:
        details: dict = {
            "period": int(event.get("period", 1) or 1),
            "possession": int(event.get("possession", 0)) if pd.notna(event.get("possession")) else 0,
            "play_pattern": str(event.get("play_pattern", "")) if pd.notna(event.get("play_pattern")) else "",
        }
        if event_type == "Pass":
            ex, ey = self._parse_xy(event.get("pass_end_location"))
            if ex is not None:
                rid = int(event.get("pass_recipient_id", 0) or 0) if pd.notna(event.get("pass_recipient_id")) else 0
                rname = str(event.get("pass_recipient", "")) if pd.notna(event.get("pass_recipient")) else ""
                details["pass"] = {
                    "end_location": [ex, ey],
                    "recipient": {"id": rid, "name": rname},
                }
        if event_type == "Carry":
            ex, ey = self._parse_xy(event.get("carry_end_location"))
            if ex is not None:
                details["carry"] = {"end_location": [ex, ey]}
        if event_type == "Dribble":
            ex, ey = self._parse_xy(event.get("carry_end_location"))
            if ex is not None:
                details["dribble"] = {"end_location": [ex, ey]}
        if event_type == "Shot":
            shot_block: dict = {}
            ex, ey = self._parse_xy(event.get("shot_end_location"))
            if ex is not None:
                shot_block["end_location"] = [ex, ey]
            if pd.notna(event.get("shot_statsbomb_xg")):
                shot_block["statsbomb_xg"] = float(event.get("shot_statsbomb_xg"))
            if shot_block:
                details["shot"] = shot_block
        return details

    def _extract_players(self, events: pd.DataFrame, lineups: dict) -> list[dict]:
        """Extract unique players from events and lineups."""
        players = {}
        
        # From lineups
        for team_name, lineup_df in lineups.items():
            for _, player in lineup_df.iterrows():
                pid = int(player.get('player_id', 0))
                if pid not in players:
                    positions = player.get('positions', [])
                    position = 'Unknown'
                    if isinstance(positions, list) and len(positions) > 0:
                        if isinstance(positions[0], dict):
                            position = positions[0].get('position', 'Unknown')
                        else:
                            position = str(positions[0])
                    
                    players[pid] = {
                        'id': pid,
                        'name': str(player.get('player_name', 'Unknown')),
                        'team': str(team_name),
                        'position': position,
                        'jersey_number': int(player.get('jersey_number', 0)) if pd.notna(player.get('jersey_number')) else 0,
                    }
        
        # From events (fallback for any missed players)
        for _, event in events.iterrows():
            pid = int(event.get('player_id', 0)) if pd.notna(event.get('player_id')) else 0
            if pid > 0 and pid not in players:
                position = str(event.get('position', 'Unknown')) if pd.notna(event.get('position')) else 'Unknown'
                players[pid] = {
                    'id': pid,
                    'name': str(event.get('player', 'Unknown')),
                    'team': str(event.get('team', '')),
                    'position': position,
                    'jersey_number': 0,
                }
        
        return list(players.values())

    def get_events_dataframe(self, events: list[dict]) -> pd.DataFrame:
        """Convert processed events list to DataFrame for engine calculations."""
        df = pd.DataFrame(events)
        if "id" not in df.columns:
            df["id"] = range(1, len(df) + 1)
        # Ensure required columns exist
        for col in ['player_id', 'minute', 'second', 'type', 'team', 'under_pressure', 'outcome']:
            if col not in df.columns:
                if col == 'type' and 'event_type' in df.columns:
                    df['type'] = df['event_type']
                elif col == 'under_pressure':
                    df[col] = False
                elif col == 'outcome':
                    df[col] = None
                else:
                    df[col] = None
        return df

    def _generate_fallback_data(self) -> dict:
        """Generate realistic fallback data for the 2018 World Cup Final."""
        logger.info("Generating fallback data for France vs Croatia 2018")
        
        match_info = {
            'id': 1,
            'statsbomb_id': FINAL_MATCH_ID,
            'home_team': 'France',
            'away_team': 'Croatia',
            'home_score': 4,
            'away_score': 2,
            'competition': '2018 FIFA World Cup',
            'season': '2018',
            'match_date': '2018-07-15',
            'venue': 'Luzhniki Stadium, Moscow',
        }
        
        # Key players
        france_players = [
            {'id': 1, 'name': 'Hugo Lloris', 'team': 'France', 'position': 'Goalkeeper', 'jersey_number': 1},
            {'id': 2, 'name': 'Benjamin Pavard', 'team': 'France', 'position': 'Right Back', 'jersey_number': 2},
            {'id': 3, 'name': 'Raphaël Varane', 'team': 'France', 'position': 'Center Back', 'jersey_number': 4},
            {'id': 4, 'name': 'Samuel Umtiti', 'team': 'France', 'position': 'Center Back', 'jersey_number': 5},
            {'id': 5, 'name': 'Lucas Hernandez', 'team': 'France', 'position': 'Left Back', 'jersey_number': 21},
            {'id': 6, 'name': "N'Golo Kanté", 'team': 'France', 'position': 'Center Midfield', 'jersey_number': 13},
            {'id': 7, 'name': 'Paul Pogba', 'team': 'France', 'position': 'Center Midfield', 'jersey_number': 6},
            {'id': 8, 'name': 'Blaise Matuidi', 'team': 'France', 'position': 'Left Midfield', 'jersey_number': 14},
            {'id': 9, 'name': 'Antoine Griezmann', 'team': 'France', 'position': 'Center Forward', 'jersey_number': 7},
            {'id': 10, 'name': 'Kylian Mbappé', 'team': 'France', 'position': 'Right Wing', 'jersey_number': 10},
            {'id': 11, 'name': 'Olivier Giroud', 'team': 'France', 'position': 'Striker', 'jersey_number': 9},
        ]
        
        croatia_players = [
            {'id': 12, 'name': 'Danijel Subašić', 'team': 'Croatia', 'position': 'Goalkeeper', 'jersey_number': 23},
            {'id': 13, 'name': 'Šime Vrsaljko', 'team': 'Croatia', 'position': 'Right Back', 'jersey_number': 2},
            {'id': 14, 'name': 'Dejan Lovren', 'team': 'Croatia', 'position': 'Center Back', 'jersey_number': 6},
            {'id': 15, 'name': 'Domagoj Vida', 'team': 'Croatia', 'position': 'Center Back', 'jersey_number': 21},
            {'id': 16, 'name': 'Ivan Strinić', 'team': 'Croatia', 'position': 'Left Back', 'jersey_number': 3},
            {'id': 17, 'name': 'Luka Modrić', 'team': 'Croatia', 'position': 'Center Midfield', 'jersey_number': 10},
            {'id': 18, 'name': 'Ivan Rakitić', 'team': 'Croatia', 'position': 'Center Midfield', 'jersey_number': 7},
            {'id': 19, 'name': 'Marcelo Brozović', 'team': 'Croatia', 'position': 'Center Defensive Midfield', 'jersey_number': 11},
            {'id': 20, 'name': 'Ivan Perišić', 'team': 'Croatia', 'position': 'Left Wing', 'jersey_number': 4},
            {'id': 21, 'name': 'Ante Rebić', 'team': 'Croatia', 'position': 'Right Wing', 'jersey_number': 18},
            {'id': 22, 'name': 'Mario Mandžukić', 'team': 'Croatia', 'position': 'Striker', 'jersey_number': 17},
        ]
        
        players = france_players + croatia_players
        
        # Generate key match events
        events = self._generate_match_events(players)
        
        return {
            'match_info': match_info,
            'events': events,
            'players': players,
            'raw_events': pd.DataFrame(events),
        }

    def _generate_match_events(self, players: list[dict]) -> list[dict]:
        """Generate realistic events for the 2018 World Cup Final."""
        np.random.seed(2018)
        events = []
        event_id = 1
        
        # Key moments of the actual match
        key_events = [
            # Mandžukić own goal (18')
            {'minute': 18, 'type': 'Shot', 'player_id': 9, 'team': 'France', 'outcome': 'Goal',
             'details': {'goal_type': 'Own Goal by Mandžukić from Griezmann free kick'}},
            # Perišić goal (28')
            {'minute': 28, 'type': 'Shot', 'player_id': 20, 'team': 'Croatia', 'outcome': 'Goal',
             'details': {'goal_type': 'Left foot volley from Vrsaljko cross'}},
            # VAR handball check on Perišić (33')
            {'minute': 33, 'type': 'Foul Committed', 'player_id': 20, 'team': 'Croatia', 'outcome': 'Penalty',
             'details': {'foul_type': 'Handball', 'var_review': True}},
            # Griezmann penalty (38')
            {'minute': 38, 'type': 'Shot', 'player_id': 9, 'team': 'France', 'outcome': 'Goal',
             'details': {'goal_type': 'Penalty', 'var_assisted': True}},
            # Pogba goal (59')
            {'minute': 59, 'type': 'Shot', 'player_id': 7, 'team': 'France', 'outcome': 'Goal',
             'details': {'goal_type': 'Right foot from edge of box'}},
            # Mbappé goal (65')
            {'minute': 65, 'type': 'Shot', 'player_id': 10, 'team': 'France', 'outcome': 'Goal',
             'details': {'goal_type': 'Right foot low shot, 19 years old — 2nd teenager to score in WC Final'}},
            # Lloris error + Mandžukić goal (69')
            {'minute': 69, 'type': 'Shot', 'player_id': 22, 'team': 'Croatia', 'outcome': 'Goal',
             'details': {'goal_type': 'Lloris error, Mandžukić capitalized on goalkeeper mistake'}},
        ]
        
        # Add key events
        for ke in key_events:
            player = next((p for p in players if p['id'] == ke['player_id']), None)
            events.append({
                'id': event_id,
                'match_id': 1,
                'event_type': ke['type'],
                'minute': ke['minute'],
                'second': np.random.randint(0, 59),
                'player_name': player['name'] if player else 'Unknown',
                'player_id': ke['player_id'],
                'team': ke['team'],
                'location_x': np.random.uniform(80, 120) if ke['type'] == 'Shot' else np.random.uniform(30, 90),
                'location_y': np.random.uniform(20, 60),
                'outcome': ke['outcome'],
                'under_pressure': np.random.random() > 0.4,
                'details': ke.get('details', {}),
            })
            event_id += 1
        
        # Generate regular match events (passes, pressure, carries, etc.)
        for minute in range(0, 95):
            # Each minute has ~20-30 events
            n_events = np.random.randint(15, 35)
            for _ in range(n_events):
                player = players[np.random.randint(0, len(players))]
                event_type = np.random.choice(
                    ['Pass', 'Carry', 'Pressure', 'Ball Receipt*', 'Dribble', 'Tackle', 
                     'Interception', 'Clearance', 'Foul Committed', 'Foul Won', 'Miscontrol'],
                    p=[0.35, 0.20, 0.12, 0.10, 0.05, 0.04, 0.04, 0.03, 0.03, 0.02, 0.02]
                )
                
                # Determine outcome
                if event_type == 'Pass':
                    outcome = np.random.choice(['Complete', 'Incomplete'], p=[0.82, 0.18])
                elif event_type == 'Dribble':
                    outcome = np.random.choice(['Complete', 'Incomplete'], p=[0.55, 0.45])
                elif event_type == 'Tackle':
                    outcome = np.random.choice(['Won', 'Lost'], p=[0.60, 0.40])
                else:
                    outcome = None
                
                events.append({
                    'id': event_id,
                    'match_id': 1,
                    'event_type': event_type,
                    'minute': minute,
                    'second': np.random.randint(0, 59),
                    'player_name': player['name'],
                    'player_id': player['id'],
                    'team': player['team'],
                    'location_x': float(np.random.uniform(0, 120)),
                    'location_y': float(np.random.uniform(0, 80)),
                    'outcome': outcome,
                    'under_pressure': bool(np.random.random() > 0.65),
                    'details': {'period': 1 if minute < 45 else 2},
                })
                event_id += 1
        
        # Sort by minute and second
        events.sort(key=lambda e: (e['minute'], e['second']))
        
        # Re-assign IDs after sorting
        for i, event in enumerate(events):
            event['id'] = i + 1
        
        return events
