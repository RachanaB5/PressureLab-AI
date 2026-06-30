"""
PressureLab AI - Universal Match Loader
Parses StatsBomb JSON, stores processed matches, and rebuilds analyses from uploaded data.
Works for any match — not hardcoded to France vs Croatia.
"""

import base64
import gzip
import json
import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed_matches"


class MatchLoader:
    """Universal engine for loading, parsing, and persisting match data."""

    def __init__(self, statsbomb_loader=None):
        self.statsbomb = statsbomb_loader
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def parse_statsbomb_json(
        self,
        raw: Any,
        match_info: Optional[dict] = None,
    ) -> dict:
        """
        Parse uploaded StatsBomb event JSON into PressureLab schema.
        Accepts raw event arrays or objects with common wrapper keys.
        """
        raw = self._coerce_payload(raw)
        events_raw, discovered_info, lineups_raw = self._extract_payload_parts(raw)
        match_info = self._merge_match_info(discovered_info, match_info)

        if not events_raw:
            raise ValueError(
                "No events found. Provide a StatsBomb event array or an object containing "
                "'events', 'events_json', 'data', or a match object with embedded events."
            )
        if not isinstance(events_raw, list):
            raise ValueError("Events must be a JSON array of StatsBomb event objects.")

        processed = []
        teams: dict[str, int] = {}
        home_team = self._normalise_name(match_info.get("home_team")) if match_info else None
        away_team = self._normalise_name(match_info.get("away_team")) if match_info else None
        formations: dict[str, list[dict]] = {}
        substitutions: list[dict] = []
        cards: list[dict] = []

        for idx, event in enumerate(events_raw):
            if not isinstance(event, dict):
                continue

            team_name = self._extract_team(event)
            if team_name:
                teams[team_name] = teams.get(team_name, 0) + 1

            loc = event.get("location") or [None, None]
            if isinstance(loc, list) and len(loc) >= 2:
                loc_x, loc_y = loc[0], loc[1]
            else:
                loc_x = event.get("location_x")
                loc_y = event.get("location_y")

            event_type = self._extract_event_type(event)
            outcome = self._extract_outcome(event, event_type)

            player_name = (
                event.get("player_name")
                or self._normalise_name(event.get("player"))
                or "Unknown"
            )

            player_obj = event.get("player") if isinstance(event.get("player"), dict) else {}
            player_id = event.get("player_id") or player_obj.get("id") or 0
            if isinstance(player_id, dict):
                player_id = player_id.get("id", 0)

            position = self._normalise_name(event.get("position"))
            details = self._extract_details(event, event_type)
            if position:
                details["position"] = position
            formation = self._extract_formation(event)
            if formation and team_name:
                formations.setdefault(team_name, []).append({
                    "minute": int(event.get("minute", 0) or 0),
                    "formation": formation,
                })
            if event_type == "Substitution":
                substitutions.append({
                    "minute": int(event.get("minute", 0) or 0),
                    "team": team_name,
                    "player_out": str(player_name),
                    "player_in": self._normalise_name(
                        event.get("substitution_replacement")
                        or event.get("replacement")
                        or self._nested(event, "substitution", "replacement")
                    ),
                })
            card = self._extract_card(event)
            if card:
                cards.append({
                    "minute": int(event.get("minute", 0) or 0),
                    "team": team_name,
                    "player": str(player_name),
                    "card": card,
                })

            processed.append({
                "id": idx + 1,
                "match_id": match_info.get("id") if match_info else 0,
                "event_type": str(event_type),
                "minute": int(event.get("minute", 0) or 0),
                "second": int(event.get("second", 0) or 0),
                "player_name": str(player_name),
                "player_id": int(player_id or 0),
                "team": str(team_name or ""),
                "location_x": float(loc_x) if loc_x is not None else None,
                "location_y": float(loc_y) if loc_y is not None else None,
                "outcome": outcome,
                "under_pressure": bool(event.get("under_pressure", False)),
                "details": details,
            })

        processed.sort(key=lambda e: (e["minute"], e["second"]))
        for i, e in enumerate(processed):
            e["id"] = i + 1

        if not home_team or not away_team:
            sorted_teams = sorted(teams.items(), key=lambda x: -x[1])
            if len(sorted_teams) >= 2:
                home_team = home_team or sorted_teams[0][0]
                away_team = away_team or sorted_teams[1][0]
            elif len(sorted_teams) == 1:
                home_team = home_team or sorted_teams[0][0]
                away_team = away_team or "Away"

        home_team = home_team or "Home"
        away_team = away_team or "Away"

        home_score, away_score = self._compute_score(processed, home_team, away_team)
        if match_info:
            home_score = self._safe_int(match_info.get("home_score"), home_score)
            away_score = self._safe_int(match_info.get("away_score"), away_score)

        info = {
            "statsbomb_id": self._safe_int(match_info.get("statsbomb_id"), None) if match_info else None,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": int(home_score),
            "away_score": int(away_score),
            "competition": self._normalise_name((match_info or {}).get("competition")) or "Uploaded Match",
            "season": self._normalise_name((match_info or {}).get("season")) or "",
            "match_date": self._normalise_name((match_info or {}).get("match_date")) or "",
            "venue": self._normalise_name((match_info or {}).get("venue") or (match_info or {}).get("stadium")) or "",
        }

        players = self._extract_players(processed, lineups_raw)
        twin = self._build_digital_match_twin(info, processed, players, formations, substitutions, cards)
        return {
            "match_info": info,
            "events": processed,
            "players": players,
            "lineups": lineups_raw or [],
            "formations": formations,
            "substitutions": substitutions,
            "cards": cards,
            "digital_match_twin": twin,
        }

    def load_demo_match(self) -> dict:
        """Load the default 2018 World Cup Final demo."""
        if self.statsbomb:
            return self.statsbomb.load_world_cup_final()
        raise RuntimeError("StatsBomb loader not available for demo match")

    def save_processed(self, match_id: int, data: dict) -> Path:
        """Persist processed match JSON for reload."""
        path = DATA_DIR / f"match_{match_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)
        logger.info("Saved processed match %s to %s", match_id, path)
        return path

    def load_processed(self, match_id: int) -> Optional[dict]:
        path = DATA_DIR / f"match_{match_id}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def build_tactical_signature(self, events: list[dict]) -> dict:
        """Build a tactical fingerprint from event data for similarity search."""
        df = pd.DataFrame(events)
        if df.empty:
            return {}

        if "event_type" in df.columns and "type" not in df.columns:
            df["type"] = df["event_type"]

        total = len(df)
        passes = df[df["type"] == "Pass"]
        shots = df[df["type"] == "Shot"]
        pressures = df[df["type"] == "Pressure"]
        carries = df[df["type"] == "Carry"]
        tackles = df[df["type"] == "Tackle"]

        under_pressure = df["under_pressure"].sum() if "under_pressure" in df.columns else 0
        pass_complete = 0
        if len(passes) > 0 and "outcome" in passes.columns:
            pass_complete = passes["outcome"].apply(
                lambda x: pd.isna(x) or str(x).lower() in ("", "complete")
            ).sum()

        teams = df["team"].value_counts()
        possession_balance = 0.5
        if len(teams) >= 2:
            possession_balance = float(teams.iloc[0]) / total

        avg_x = df["location_x"].dropna().mean() if "location_x" in df.columns else 60.0
        defensive_third = (
            df["location_x"].dropna().apply(lambda x: x < 40).sum() / max(len(df["location_x"].dropna()), 1)
            if "location_x" in df.columns else 0.33
        )

        return {
            "pass_ratio": len(passes) / total,
            "shot_ratio": len(shots) / total,
            "pressure_ratio": len(pressures) / total,
            "carry_ratio": len(carries) / total,
            "tackle_ratio": len(tackles) / total,
            "under_pressure_ratio": under_pressure / total,
            "pass_completion_rate": pass_complete / max(len(passes), 1),
            "possession_balance": possession_balance,
            "avg_field_position": float(avg_x) / 120.0,
            "defensive_third_ratio": float(defensive_third),
            "total_events": total,
        }

    def _coerce_payload(self, raw: Any) -> Any:
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                raise ValueError("Empty JSON payload.")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                try:
                    decoded = base64.b64decode(text)
                    try:
                        decoded = gzip.decompress(decoded)
                    except OSError:
                        pass
                    return json.loads(decoded.decode("utf-8"))
                except Exception as exc:
                    raise ValueError("Invalid JSON or compressed/base64 JSON payload.") from exc
        return raw

    def _extract_payload_parts(self, raw: Any) -> tuple[list, dict, Any]:
        if isinstance(raw, list):
            return raw, {}, []
        if not isinstance(raw, dict):
            raise ValueError("Payload must be a JSON object or array.")

        info = raw.get("match_info") or raw.get("metadata") or raw.get("match") or {}
        lineups = raw.get("lineups") or raw.get("lineup") or []
        events = raw.get("events") or raw.get("events_json") or raw.get("data")

        matches = raw.get("matches")
        if events is None and isinstance(matches, list) and matches:
            first = matches[0]
            if isinstance(first, dict):
                info = {**first, **info}
                events = first.get("events") or first.get("events_json") or first.get("data")
                lineups = first.get("lineups") or lineups

        if isinstance(events, str):
            events = self._coerce_payload(events)

        return events or [], info if isinstance(info, dict) else {}, lineups

    def _merge_match_info(self, discovered: Optional[dict], explicit: Optional[dict]) -> dict:
        base: dict = {}
        for source in (discovered or {}, explicit or {}):
            if not isinstance(source, dict):
                continue
            base.update(source)

        aliases = {
            "match_id": "statsbomb_id",
            "id": "statsbomb_id",
            "match_date": "match_date",
            "kick_off": "kick_off",
            "stadium": "venue",
        }
        for src, dst in aliases.items():
            if src in base and dst not in base:
                base[dst] = base[src]

        for key in ("home_team", "away_team", "competition", "season", "venue", "stadium"):
            if key in base:
                base[key] = self._normalise_name(base[key])
        return base

    def _normalise_name(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            for key in ("name", "home_team_name", "away_team_name", "stadium_name"):
                if value.get(key):
                    return str(value[key])
            return ""
        return str(value)

    def _safe_int(self, value: Any, default: Optional[int] = 0) -> Optional[int]:
        if value is None or value == "":
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _extract_team(self, event: dict) -> str:
        team = event.get("team")
        if isinstance(team, dict):
            return str(team.get("name", ""))
        return str(team or "")

    def _extract_event_type(self, event: dict) -> str:
        et = event.get("event_type") or event.get("type")
        if isinstance(et, dict):
            return str(et.get("name", "Unknown"))
        return str(et or "Unknown")

    def _extract_outcome(self, event: dict, event_type: str) -> Optional[str]:
        if event.get("outcome"):
            o = event["outcome"]
            return str(o.get("name", o) if isinstance(o, dict) else o)

        nested_outcome = (
            self._nested(event, "shot", "outcome")
            or self._nested(event, "pass", "outcome")
            or self._nested(event, "dribble", "outcome")
        )
        if nested_outcome:
            return self._normalise_name(nested_outcome)

        for key in ("shot_outcome", "pass_outcome", "dribble_outcome"):
            if event.get(key):
                v = event[key]
                return str(v.get("name", v) if isinstance(v, dict) else v)

        if event_type == "Pass":
            return "Complete"
        return None

    def _extract_details(self, event: dict, event_type: str) -> dict:
        details = {
            "period": int(event.get("period", 1) or 1),
            "possession": event.get("possession"),
            "play_pattern": self._normalise_name(event.get("play_pattern")),
            "statsbomb_event_id": event.get("id"),
        }
        nested_keys = (
            "shot", "pass", "carry", "duel", "dribble", "foul_committed",
            "foul_won", "substitution", "bad_behaviour", "ball_receipt",
            "clearance", "interception", "goalkeeper", "tactics",
        )
        for key in nested_keys:
            if isinstance(event.get(key), dict):
                details[key] = event[key]
        card = self._extract_card(event)
        if card:
            details["card"] = card
        if event_type.lower().startswith("own goal"):
            details["own_goal"] = True
        return details

    def _nested(self, event: dict, container_key: str, value_key: str) -> Any:
        container = event.get(container_key)
        if isinstance(container, dict):
            return container.get(value_key)
        return None

    def _extract_formation(self, event: dict) -> Optional[int]:
        tactics = event.get("tactics")
        if isinstance(tactics, dict) and tactics.get("formation"):
            return self._safe_int(tactics.get("formation"), None)
        return None

    def _extract_card(self, event: dict) -> str:
        for container_key, card_key in (
            ("foul_committed", "card"),
            ("bad_behaviour", "card"),
        ):
            container = event.get(container_key)
            if isinstance(container, dict) and container.get(card_key):
                return self._normalise_name(container[card_key])
        for flat_key in ("foul_committed_card", "bad_behaviour_card", "card"):
            if event.get(flat_key):
                return self._normalise_name(event[flat_key])
        return ""

    def _goal_team_for_event(self, event: dict, home: str, away: str) -> Optional[str]:
        et = str(event.get("event_type", "")).lower()
        outcome = str(event.get("outcome", "")).lower()
        team = event.get("team", "")
        if "own goal against" in et:
            if team == home:
                return away
            if team == away:
                return home
            return None
        if "own goal for" in et:
            return team
        if et == "goal" or ("shot" in et and "goal" in outcome):
            return team
        return None

    def _compute_score(self, events: list[dict], home: str, away: str) -> tuple[int, int]:
        home_goals, away_goals = 0, 0
        for e in events:
            scoring_team = self._goal_team_for_event(e, home, away)
            if scoring_team == home:
                home_goals += 1
            elif scoring_team == away:
                away_goals += 1
        return home_goals, away_goals

    def _extract_players(self, events: list[dict], lineups: Any = None) -> list[dict]:
        players: dict[int, dict] = {}
        if isinstance(lineups, dict):
            lineup_iter = []
            for team, rows in lineups.items():
                if isinstance(rows, list):
                    lineup_iter.extend((team, p) for p in rows)
        elif isinstance(lineups, list):
            lineup_iter = [("", p) for p in lineups if isinstance(p, dict)]
        else:
            lineup_iter = []

        for team_name, player in lineup_iter:
            pid = self._safe_int(player.get("player_id") or player.get("id"), 0)
            if pid and pid not in players:
                positions = player.get("positions") or []
                position = ""
                if isinstance(positions, list) and positions:
                    position = self._normalise_name(positions[0].get("position") if isinstance(positions[0], dict) else positions[0])
                players[pid] = {
                    "id": pid,
                    "name": self._normalise_name(player.get("player_name") or player.get("name")) or "Unknown",
                    "team": self._normalise_name(player.get("team") or team_name),
                    "position": position or self._normalise_name(player.get("position")) or "Unknown",
                    "jersey_number": self._safe_int(player.get("jersey_number"), 0) or 0,
                }

        for e in events:
            pid = e.get("player_id", 0)
            if pid and pid > 0 and pid not in players:
                players[pid] = {
                    "id": pid,
                    "name": e.get("player_name", "Unknown"),
                    "team": e.get("team", ""),
                    "position": e.get("details", {}).get("position") or "Unknown",
                    "jersey_number": 0,
                }
        return list(players.values())

    def _build_digital_match_twin(
        self,
        info: dict,
        events: list[dict],
        players: list[dict],
        formations: dict[str, list[dict]],
        substitutions: list[dict],
        cards: list[dict],
    ) -> dict:
        counts: dict[str, int] = {}
        team_counts: dict[str, dict[str, int]] = {}
        for event in events:
            et = event["event_type"]
            team = event.get("team") or "Unknown"
            counts[et] = counts.get(et, 0) + 1
            team_counts.setdefault(team, {})
            team_counts[team][et] = team_counts[team].get(et, 0) + 1

        goals = [
            {
                "minute": e["minute"],
                "team": self._goal_team_for_event(e, info["home_team"], info["away_team"]),
                "player": e["player_name"],
                "outcome": e.get("outcome"),
            }
            for e in events
            if self._goal_team_for_event(e, info["home_team"], info["away_team"])
        ]

        return {
            "match_info": info,
            "teams": [info["home_team"], info["away_team"]],
            "score": {"home": info["home_score"], "away": info["away_score"]},
            "players": players,
            "formations": formations,
            "events": {
                "total": len(events),
                "by_type": counts,
                "by_team": team_counts,
                "goals": goals,
                "substitutions": substitutions,
                "cards": cards,
            },
        }
