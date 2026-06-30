"""
PressureLab AI - Unified Moment Workspace
Single API payload for the workspace: pitch, tactical brief, coach recommendations.
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Optional

import pandas as pd

from engine.pitch_state_engine import PitchStateEngine

logger = logging.getLogger(__name__)


def _short(text: str, max_len: int = 120) -> str:
    t = " ".join(str(text or "").split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"

KEY_EVENT_TYPES = {
    "Shot", "Goal", "Pass", "Carry", "Pressure", "Dribble", "Tackle",
    "Interception", "Substitution", "Foul Committed", "Bad Behaviour",
}


class MomentWorkspaceEngine:
    """Builds all workspace sections for a selected match moment."""

    def build_overview(
        self,
        match_info: dict,
        events_df: pd.DataFrame,
        momentum: list[dict],
        home_team: str,
        away_team: str,
    ) -> dict:
        if "type" not in events_df.columns and "event_type" in events_df.columns:
            events_df = events_df.copy()
            events_df["type"] = events_df["event_type"]

        total = max(len(events_df), 1)
        home_ev = events_df[events_df["team"] == home_team]
        away_ev = events_df[events_df["team"] == away_team]
        possession_home = round(len(home_ev) / total * 100, 1)
        possession_away = round(100 - possession_home, 1)

        shots_h = len(home_ev[home_ev["type"] == "Shot"])
        shots_a = len(away_ev[away_ev["type"] == "Shot"])
        xg_h = round(shots_h * 0.12 + len(home_ev[home_ev["type"] == "Goal"]) * 0.35, 2)
        xg_a = round(shots_a * 0.12 + len(away_ev[away_ev["type"] == "Goal"]) * 0.35, 2)

        mom_peak = max(momentum, key=lambda m: m.get("home_momentum", 0), default={}) if momentum else {}
        latest = momentum[-1] if momentum else {}
        mom_h = latest.get("home_momentum", 0.5)
        mom_a = latest.get("away_momentum", 0.5)
        pressure_idx = round((mom_a + shots_a * 0.04) * 50, 0)
        xthreat_h = round(xg_h * 1.2 + possession_home * 0.01, 2)
        xthreat_a = round(xg_a * 1.2 + possession_away * 0.01, 2)
        danger = "home" if xg_h > xg_a + 0.15 else "away" if xg_a > xg_h + 0.15 else "balanced"
        gd = int(match_info.get("home_score", 0)) - int(match_info.get("away_score", 0))
        if gd > 0:
            exp_winner = home_team
        elif gd < 0:
            exp_winner = away_team
        else:
            exp_winner = home_team if mom_h >= mom_a else away_team
        mom_summary = (
            f"{home_team} peaked at {mom_peak.get('minute', 0)}' "
            f"({mom_peak.get('home_momentum', 0.5):.0%} momentum)."
            if momentum
            else f"{home_team} {mom_h:.0%} momentum vs {away_team} {mom_a:.0%}."
        )

        return {
            "home_team": home_team,
            "away_team": away_team,
            "score": f"{match_info.get('home_score', 0)}-{match_info.get('away_score', 0)}",
            "competition": match_info.get("competition", ""),
            "match_date": match_info.get("match_date", ""),
            "venue": match_info.get("venue", ""),
            "xg": {"home": xg_h, "away": xg_a},
            "possession": {"home": possession_home, "away": possession_away},
            "momentum_summary": mom_summary,
            "shots": {"home": shots_h, "away": shots_a},
            "momentum": {"home": round(mom_h * 100), "away": round(mom_a * 100)},
            "pressure_index": pressure_idx,
            "xthreat": {"home": xthreat_h, "away": xthreat_a},
            "danger_zone": danger,
            "formation": {"home": "4-3-3", "away": "4-2-3-1"},
            "expected_winner": exp_winner,
            "game_state": "leading" if gd > 0 else "trailing" if gd < 0 else "level",
        }

    def build_overview_at_minute(
        self,
        match_info: dict,
        events_df: pd.DataFrame,
        momentum: list[dict],
        home_team: str,
        away_team: str,
        minute: int,
    ) -> dict:
        """Match overview scoped to a specific minute — live scoreboard state."""
        if "type" not in events_df.columns and "event_type" in events_df.columns:
            events_df = events_df.copy()
            events_df["type"] = events_df["event_type"]

        subset = events_df[events_df["minute"] <= minute]
        total = max(len(subset), 1)
        home_ev = subset[subset["team"] == home_team]
        away_ev = subset[subset["team"] == away_team]

        home_goals = 0
        away_goals = 0
        for _, r in subset.iterrows():
            scorer = self._scoring_team(r.to_dict(), home_team, away_team)
            if scorer == home_team:
                home_goals += 1
            elif scorer == away_team:
                away_goals += 1

        possession_home = round(len(home_ev) / total * 100, 1)
        possession_away = round(100 - possession_home, 1)
        shots_h = len(home_ev[home_ev["type"] == "Shot"])
        shots_a = len(away_ev[away_ev["type"] == "Shot"])
        xg_h = round(shots_h * 0.12 + home_goals * 0.35, 2)
        xg_a = round(shots_a * 0.12 + away_goals * 0.35, 2)

        mom = next((m for m in momentum if m.get("minute") == minute), None)
        if mom is None and momentum:
            mom = momentum[minute] if minute < len(momentum) else momentum[-1]
        if mom is None:
            mom = {}
        mom_h = mom.get("home_momentum", 0.5)
        mom_a = mom.get("away_momentum", 0.5)
        pressure_idx = round((mom_a + shots_a * 0.04 + minute * 0.01) * 50, 0)
        xthreat_h = round(xg_h * 1.2 + possession_home * 0.01, 2)
        xthreat_a = round(xg_a * 1.2 + possession_away * 0.01, 2)
        danger = "home" if xg_h > xg_a + 0.15 else "away" if xg_a > xg_h + 0.15 else "balanced"
        gd = home_goals - away_goals
        if gd > 0:
            exp_winner = home_team
            game_state = "leading" if mom_h >= 0.45 else "under_pressure"
        elif gd < 0:
            exp_winner = away_team
            game_state = "trailing" if mom_h < 0.55 else "chasing"
        else:
            exp_winner = home_team if mom_h >= mom_a else away_team
            game_state = "level"

        return {
            "home_team": home_team,
            "away_team": away_team,
            "score": f"{home_goals}-{away_goals}",
            "home_score": home_goals,
            "away_score": away_goals,
            "minute": minute,
            "clock": f"{minute}'",
            "competition": match_info.get("competition", ""),
            "match_date": match_info.get("match_date", ""),
            "venue": match_info.get("venue", ""),
            "xg": {"home": xg_h, "away": xg_a},
            "possession": {"home": possession_home, "away": possession_away},
            "momentum_summary": (
                f"At {minute}', {home_team} {mom_h:.0%} momentum · "
                f"{away_team} {mom_a:.0%} · score {home_goals}-{away_goals}."
            ),
            "shots": {"home": shots_h, "away": shots_a},
            "momentum": {"home": round(mom_h * 100), "away": round(mom_a * 100)},
            "pressure_index": min(100, pressure_idx),
            "xthreat": {"home": xthreat_h, "away": xthreat_a},
            "danger_zone": danger,
            "formation": {"home": "4-3-3", "away": "4-2-3-1"},
            "expected_winner": exp_winner,
            "game_state": game_state,
            "win_probability": {
                "home": round(33 + gd * 12 + (mom_h - 0.5) * 30, 1),
                "draw": round(max(15, 28 - abs(gd) * 8), 1),
                "away": round(33 - gd * 12 + (mom_a - 0.5) * 30, 1),
            },
        }

    def build_key_events(
        self,
        events: list[dict],
        home_team: str,
        away_team: str,
        momentum: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Timeline of important events for the interactive strip."""
        key = []
        for e in events:
            et = str(e.get("event_type", ""))
            importance = 0
            label = et
            if et == "Shot":
                outcome = str(e.get("outcome", "")).lower()
                importance = 10 if "goal" in outcome else 7
                label = "Goal" if "goal" in outcome else "Shot"
            elif et == "Goal":
                importance = 10
                label = "Goal"
            elif "Substitution" in et:
                importance = 5
                label = "Substitution"
            elif et in ("Bad Behaviour", "Foul Committed"):
                if e.get("details", {}).get("card") or "card" in str(e.get("outcome", "")).lower():
                    importance = 6
                    label = "Card"
            elif et == "Pressure" and e.get("under_pressure"):
                importance = 3
                label = "Press"
            elif et in ("Carry", "Dribble") and e.get("location_x") and float(e["location_x"] or 0) > 90:
                importance = 4
                label = "Counter"
            if importance >= 3:
                minute = e["minute"]
                mom = momentum[minute] if momentum and minute < len(momentum) else {}
                mom_val = mom.get("home_momentum", 0.5) if e.get("team") == home_team else mom.get("away_momentum", 0.5)
                lx = float(e.get("location_x") or 60)
                xg_est = 0.35 if et == "Goal" or (et == "Shot" and "goal" in str(e.get("outcome", "")).lower()) else round(min(0.45, lx / 120 * 0.4), 2)
                key.append({
                    "id": e["id"],
                    "minute": minute,
                    "second": e.get("second", 0),
                    "type": label,
                    "event_type": et,
                    "player": e.get("player_name", ""),
                    "team": e.get("team", ""),
                    "importance": importance,
                    "outcome": e.get("outcome"),
                    "xg": xg_est,
                    "pressure": round(40 + (1 - mom_val) * 50 + (10 if e.get("under_pressure") else 0)),
                    "momentum": round(mom_val * 100),
                    "confidence": round(72 + importance * 2),
                })
        key.sort(key=lambda x: (x["minute"], x["second"]))
        # Deduplicate dense pressure events — keep max 1 per minute per type
        seen: set[tuple] = set()
        filtered = []
        for item in key:
            sig = (item["minute"], item["type"], item.get("player", ""))
            if item["importance"] >= 7 or sig not in seen:
                filtered.append(item)
                seen.add(sig)
        return filtered[-120:]  # cap for UI

    def build_goal_timeline(self, events: list[dict], home_team: str, away_team: str) -> list[dict]:
        """All goals in order — used for accurate scoreboard at any minute."""
        goals = []
        for e in events:
            scoring_team = self._scoring_team(e, home_team, away_team)
            if not scoring_team:
                continue
            goals.append({
                "minute": e.get("minute", 0),
                "second": e.get("second", 0),
                "team": scoring_team,
                "id": e.get("id"),
            })
        goals.sort(key=lambda g: (g["minute"], g["second"]))
        return goals

    def build_pitch_frame(
        self,
        events_df: pd.DataFrame,
        event: dict,
        home_team: str,
        away_team: str,
        pressure_cache: list[dict],
    ) -> dict:
        """Reconstruct full 22-player pitch state with animated replay tracks."""
        if "type" not in events_df.columns and "event_type" in events_df.columns:
            events_df = events_df.copy()
            events_df["type"] = events_df["event_type"]
        if "second" not in events_df.columns:
            events_df = events_df.copy()
            events_df["second"] = 0

        minute = int(event.get("minute") or 0)
        second = int(event.get("second") or 0)

        window = events_df[
            (events_df["minute"] >= max(0, minute - 1))
            & (events_df["minute"] <= minute + 1)
        ]

        passing_lanes = self._extract_passing_lanes(window)
        passing_lanes_start = self._extract_passing_lanes(
            self._events_before(events_df, minute, second).tail(40)
        )

        pressure_fn = lambda pid, m: self._player_pressure(pid, m, pressure_cache)
        engine = PitchStateEngine(home_team, away_team)
        state_before, state_after = engine.build_states_at_event(events_df, event, pressure_fn)

        ball_x = float(state_after["ball"]["x"])
        ball_y = float(state_after["ball"]["y"])
        ball_start_x = float(state_before["ball"]["x"])
        ball_start_y = float(state_before["ball"]["y"])
        ball_dx = ball_x - ball_start_x
        ball_dy = ball_y - ball_start_y

        freeze_frame = self._extract_freeze_frame(event, events_df, home_team, away_team)
        before_map = {p["id"]: p for p in state_before["players"]}

        players: list[dict] = []
        for p in state_after["players"]:
            pick = dict(p)
            if freeze_frame and pick["id"] in freeze_frame:
                fp = freeze_frame[pick["id"]]
                pick["x"] = fp["x"]
                pick["y"] = fp["y"]
            bp = before_map.get(pick["id"], {})
            fx = float(bp.get("x", pick["x"]))
            fy = float(bp.get("y", pick["y"]))
            tx = float(pick["x"])
            ty = float(pick["y"])
            if math.hypot(tx - fx, ty - fy) < 3.0:
                role = str(pick.get("role") or "")
                sign = 1.0 if pick.get("team") == "home" else -1.0
                fx = tx - sign * max(4.0, abs(ball_dx) * 0.5 + 2.0)
                fy = ty - max(2.0, abs(ball_dy) * 0.35)
            pick["from_x"] = round(max(4, min(116, fx)), 1)
            pick["from_y"] = round(max(4, min(76, fy)), 1)
            pick["to_x"] = round(tx, 1)
            pick["to_y"] = round(ty, 1)
            pick["from_pressure"] = round(
                max(20, min(95, float(pick.get("pressure", 50)) - abs(ball_dx) * 0.1)), 1,
            )
            pick["is_active"] = int(pick.get("player_id") or 0) == int(event.get("player_id") or -1)
            players.append(self._enrich_player(pick, ball_x, ball_y, passing_lanes))

        movements = self._extract_movements(window)
        press_avg = sum(p.get("pressure", 50) for p in players) / max(len(players), 1)
        home_line, away_line = self._defensive_lines(players)
        home_line_start, away_line_start = self._defensive_lines_at_start(
            players, ball_dx, ball_dy, press_avg,
        )

        danger = self._danger_zone(ball_x, ball_y, event)
        danger_start = self._danger_zone(ball_start_x, ball_start_y, event, scale=0.85)

        replay_start_players = [
            {
                "id": p["id"],
                "x": p["from_x"],
                "y": p["from_y"],
                "name": p["name"],
                "team": p["team"],
                "pressure": p.get("from_pressure", p.get("pressure", 50)),
                "is_active": p.get("is_active"),
                "xthreat": round((p.get("xthreat") or 0.1) * 0.7, 2),
            }
            for p in players
        ]

        return {
            "minute": minute,
            "second": second,
            "event_id": event.get("id"),
            "ball": {"x": round(ball_x, 1), "y": round(ball_y, 1)},
            "ball_start": {"x": round(ball_start_x, 1), "y": round(ball_start_y, 1)},
            "players": players,
            "passing_lanes": passing_lanes[:8],
            "passing_lanes_start": passing_lanes_start[:8],
            "movements": movements[:6],
            "attack_direction": "left_to_right" if ball_x < 60 else "right_to_left",
            "pressure_zones": self._pressure_zones(players),
            "pressure_zones_start": self._pressure_zones_from_players(replay_start_players),
            "defensive_lines": {
                "home": round(home_line, 1),
                "away": round(away_line, 1),
                "home_start": round(home_line_start, 1),
                "away_start": round(away_line_start, 1),
            },
            "team_shape": {
                "home": self._calculate_team_shape(players, "home"),
                "away": self._calculate_team_shape(players, "away")
            },
            "danger_zone": danger,
            "danger_zone_start": danger_start,
            "transition_ms": 650,
            "home_team": home_team,
            "away_team": away_team,
            "pitch_adjustment": {
                "defensive_line": round(home_line, 0),
                "press_radius": round(10 + press_avg * 0.08, 1),
                "passing_speed": round(40 + abs(ball_dx) * 2, 0),
            },
            "replay_start": {
                "ball": {"x": round(ball_start_x, 1), "y": round(ball_start_y, 1)},
                "players": replay_start_players,
                "home_team": home_team,
                "away_team": away_team,
                "passing_lanes": passing_lanes_start[:8],
                "pressure_zones": self._pressure_zones_from_players(replay_start_players),
                "defensive_lines": {
                    "home": round(home_line_start, 1),
                    "away": round(away_line_start, 1),
                },
                "danger_zone": danger_start,
            },
        }

    def _events_before(self, events_df: pd.DataFrame, minute: int, second: int) -> pd.DataFrame:
        return events_df[
            (events_df["minute"] < minute)
            | ((events_df["minute"] == minute) & (events_df["second"].fillna(0) < second))
        ].copy()

    def _extract_passing_lanes(self, df: pd.DataFrame) -> list[dict]:
        lanes = []
        if df is None or len(df) == 0:
            return lanes
        passes = df[df["type"] == "Pass"]
        for _, p in passes.iterrows():
            ex, ey = p.get("location_x"), p.get("location_y")
            end = (p.get("details") or {}).get("pass", {})
            if isinstance(end, dict):
                end_loc = end.get("end_location") or end.get("end_x")
                if isinstance(end_loc, list) and len(end_loc) >= 2 and not pd.isna(ex):
                    lanes.append({
                        "from": [float(ex), float(ey)],
                        "to": [float(end_loc[0]), float(end_loc[1])],
                        "success": "goal" not in str(p.get("outcome", "")).lower(),
                    })
        return lanes

    def _extract_movements(self, window: pd.DataFrame) -> list[dict]:
        movements = []
        carries = window[window["type"].isin(["Carry", "Dribble"])]
        for _, c in carries.iterrows():
            sx, sy = c.get("location_x"), c.get("location_y")
            details = c.get("details") or {}
            carry = details.get("carry") or details.get("dribble") or {}
            if isinstance(carry, dict):
                end = carry.get("end_location")
                if isinstance(end, list) and len(end) >= 2 and not pd.isna(sx):
                    movements.append({
                        "from": [float(sx), float(sy)],
                        "to": [float(end[0]), float(end[1])],
                        "player": str(c.get("player_name", "")),
                    })
        return movements

    def _player_pressure(self, pid: int, minute: int, pressure_cache: list[dict]) -> float:
        if pid <= 0:
            return 50.0
        for pt in pressure_cache:
            if pt.get("player_id") == pid:
                for t in pt.get("timeline", []):
                    if t.get("minute") == minute:
                        return float(t.get("pressure_score", 50))
        return 50.0

    def _last_known_positions(
        self,
        events_df: pd.DataFrame,
        minute: int,
        second: int,
        home_team: str,
        away_team: str,
        pressure_cache: list[dict],
    ) -> dict[str, dict]:
        hist = self._events_before(events_df, minute, second)
        hist = hist[hist["location_x"].notna()].sort_values(["minute", "second"])
        known: dict[str, dict] = {}
        for _, row in hist.iterrows():
            pid = int(row.get("player_id") or 0)
            if pid <= 0:
                continue
            team = row.get("team", "")
            sid = str(pid)
            known[sid] = {
                "id": sid,
                "player_id": pid,
                "x": float(row["location_x"]),
                "y": float(row["location_y"]),
                "name": str(row.get("player_name") or f"#{pid}"),
                "team": "home" if team == home_team else "away",
                "team_name": team,
                "pressure": self._player_pressure(pid, int(row.get("minute") or minute), pressure_cache),
            }
        return known

    def _window_positions(
        self,
        window: pd.DataFrame,
        minute: int,
        home_team: str,
        away_team: str,
        pressure_cache: list[dict],
        event: dict,
    ) -> dict[str, dict]:
        positions: dict[str, dict] = {}
        active_pid = event.get("player_id")
        for _, row in window.iterrows():
            pid = int(row.get("player_id") or 0)
            if pid <= 0 or pd.isna(row.get("location_x")):
                continue
            team = row.get("team", "")
            sid = str(pid)
            positions[sid] = {
                "id": sid,
                "player_id": pid,
                "x": float(row["location_x"]),
                "y": float(row["location_y"]),
                "name": str(row.get("player_name") or f"#{pid}"),
                "team": "home" if team == home_team else "away",
                "team_name": team,
                "pressure": self._player_pressure(pid, minute, pressure_cache),
                "is_active": pid == active_pid,
            }
        return positions

    def _extract_freeze_frame(
        self, event: dict, events_df: pd.DataFrame, home_team: str, away_team: str,
    ) -> dict[str, dict] | None:
        """Extract player positions from StatsBomb freeze-frame data if available."""
        details = event.get("details") or {}
        shot = details.get("shot") or {}
        freeze = shot.get("freeze_frame")
        if not isinstance(freeze, list) or not freeze:
            return None
        positions: dict[str, dict] = {}
        for entry in freeze:
            if not isinstance(entry, dict):
                continue
            loc = entry.get("location")
            if not isinstance(loc, list) or len(loc) < 2:
                continue
            player = entry.get("player") or {}
            pid = player.get("id") or 0
            pname = player.get("name") or f"#{pid}"
            if isinstance(pname, dict):
                pname = pname.get("name", f"#{pid}")
            teammate = entry.get("teammate", False)
            event_team = event.get("team", "")
            if teammate:
                team_label = "home" if event_team == home_team else "away"
            else:
                team_label = "away" if event_team == home_team else "home"
            position_name = entry.get("position", {}) if isinstance(entry.get("position"), dict) else {}
            sid = str(pid) if pid else f"freeze-{len(positions)}"
            positions[sid] = {
                "id": sid,
                "player_id": pid,
                "x": float(loc[0]),
                "y": float(loc[1]),
                "name": str(pname),
                "team": team_label,
                "team_name": home_team if team_label == "home" else away_team,
                "position": position_name.get("name", ""),
                "is_active": False,
            }
        return positions if positions else None

    @staticmethod
    def _event_formation_modifier(
        event_type: str, play_pattern: str, possession_team: str,
        team: str, ball_x: float, ball_y: float,
    ) -> list[tuple[float, float]]:
        """Return per-slot (dx, dy) adjustments based on event type and tactical context.

        These offsets are added to the base formation slots to create visually distinct
        team shapes for different types of play.
        """
        et = (event_type or "").lower()
        pp = (play_pattern or "").lower()
        is_possession = possession_team == ("home" if team == "home" else "away")
        sign = 1.0 if team == "home" else -1.0

        #  Slot order: GK, DEF x4, MID x4, FWD x2
        offsets = [(0.0, 0.0)] * 11

        if "shot" in et or "goal" in et:
            if is_possession:
                # Attacking team pushes into the box
                offsets = [
                    (0, 0),  # GK stays
                    (sign * 8, -2), (sign * 8, -1), (sign * 8, 1), (sign * 8, 2),
                    (sign * 12, -4), (sign * 12, 0), (sign * 12, 4), (sign * 10, -6),
                    (sign * 18, -3), (sign * 18, 3),
                ]
            else:
                # Defending team collapses toward goal
                offsets = [
                    (0, 0),
                    (-sign * 6, -3), (-sign * 6, -1), (-sign * 6, 1), (-sign * 6, 3),
                    (-sign * 4, -2), (-sign * 4, 0), (-sign * 4, 2), (-sign * 3, -4),
                    (-sign * 2, -1), (-sign * 2, 1),
                ]
        elif et in ("pressure", "duel", "tackle", "interception"):
            if is_possession:
                # Being pressed — compact shape
                offsets = [
                    (0, 0),
                    (sign * 2, -1), (sign * 2, 0), (sign * 2, 0), (sign * 2, 1),
                    (sign * 3, -2), (sign * 3, 0), (sign * 3, 2), (sign * 2, -3),
                    (sign * 4, -1), (sign * 4, 1),
                ]
            else:
                # High press — push forward
                offsets = [
                    (sign * 4, 0),
                    (sign * 8, -1), (sign * 8, 0), (sign * 8, 0), (sign * 8, 1),
                    (sign * 14, -3), (sign * 14, 0), (sign * 14, 3), (sign * 12, -5),
                    (sign * 18, -2), (sign * 18, 2),
                ]
        elif et in ("carry", "dribble"):
            if is_possession:
                # Support runs during carry
                offsets = [
                    (0, 0),
                    (sign * 4, -1), (sign * 4, 0), (sign * 4, 0), (sign * 4, 1),
                    (sign * 8, -3), (sign * 8, 0), (sign * 8, 3), (sign * 6, -5),
                    (sign * 14, -2), (sign * 14, 4),
                ]
            else:
                # Retreat into shape
                offsets = [
                    (0, 0),
                    (-sign * 4, -1), (-sign * 4, 0), (-sign * 4, 0), (-sign * 4, 1),
                    (-sign * 2, -2), (-sign * 2, 0), (-sign * 2, 2), (-sign * 1, -3),
                    (sign * 2, -1), (sign * 2, 1),
                ]
        elif et == "pass":
            if is_possession:
                # Spread out to receive
                offsets = [
                    (0, 0),
                    (sign * 3, -3), (sign * 3, -1), (sign * 3, 1), (sign * 3, 3),
                    (sign * 6, -5), (sign * 6, 0), (sign * 6, 5), (sign * 5, -7),
                    (sign * 10, -3), (sign * 10, 3),
                ]
            else:
                # Mark passing options
                offsets = [
                    (0, 0),
                    (-sign * 2, -2), (-sign * 2, -1), (-sign * 2, 1), (-sign * 2, 2),
                    (sign * 2, -4), (sign * 2, 0), (sign * 2, 4), (sign * 1, -5),
                    (sign * 5, -2), (sign * 5, 2),
                ]

        # Counter attack pattern
        if "counter" in pp or "from counter" in pp:
            stretch = 1.5 if is_possession else 0.7
            offsets = [(dx * stretch, dy * stretch) for dx, dy in offsets]

        # From goal kick / build-up — deeper positions
        if "from goal kick" in pp or "from kick off" in pp:
            deeper = -sign * 5 if is_possession else sign * 3
            offsets = [(dx + deeper, dy) for dx, dy in offsets]

        return offsets

    def _formation_slots(
        self, team: str, ball_x: float, ball_y: float, press_avg: float,
        event: dict | None = None,
    ) -> list[tuple[float, float]]:
        compress = (press_avg - 50) / 100 * 6
        ball_shift = (ball_x - 60) * 0.14
        y_shift = (ball_y - 40) * 0.08

        # Per-event hash jitter so no two events produce identical positions
        event_id = int(event.get("id", 0) or 0) if event else 0
        jitter_seed = hashlib.md5(str(event_id).encode()).digest()

        # Determine event context for formation modifiers
        event_type = str(event.get("event_type", "")) if event else ""
        play_pattern = str((event.get("details") or {}).get("play_pattern", "")) if event else ""
        possession_team = str(event.get("team", "")) if event else ""

        if team == "home":
            base = [
                (12, 40), (22, 14), (22, 32), (22, 48), (22, 66),
                (42, 18), (42, 36), (42, 52), (42, 70),
                (62, 28), (62, 52),
            ]
        else:
            base = [
                (108, 40), (98, 14), (98, 32), (98, 48), (98, 66),
                (78, 18), (78, 36), (78, 52), (78, 70),
                (58, 28), (58, 52),
            ]

        # Apply event-type formation modifier
        modifiers = self._event_formation_modifier(
            event_type, play_pattern, possession_team, team, ball_x, ball_y,
        )

        result = []
        for i, (x, y) in enumerate(base):
            dx, dy = modifiers[i] if i < len(modifiers) else (0, 0)

            # Hash-based per-player jitter: ±2 to ±4 units
            jx = ((jitter_seed[i % len(jitter_seed)] - 128) / 128.0) * 3.5
            jy = ((jitter_seed[(i + 5) % len(jitter_seed)] - 128) / 128.0) * 2.5

            mult = 1.0 if team == "home" else 0.6
            nx = x + ball_shift * mult + dx + jx
            ny = y + y_shift + dy + jy - compress * (0.15 if team == "home" else -0.15)
            result.append((max(8, min(112, nx)), max(6, min(74, ny))))

        return result

    def _build_full_squad(
        self,
        last_known: dict[str, dict],
        window_positions: dict[str, dict],
        home_team: str,
        away_team: str,
        event: dict,
        ball_x: float,
        ball_y: float,
        passing_lanes: list[dict],
        freeze_frame: dict[str, dict] | None = None,
    ) -> list[dict]:
        """Always return 22 players (11 home + 11 away) with event-specific coordinates."""
        press_vals = [p.get("pressure", 50) for p in {**last_known, **window_positions}.values()]
        press_avg = sum(press_vals) / max(len(press_vals), 1)
        active_pid = event.get("player_id")
        players: list[dict] = []

        # If we have freeze-frame data, use it as the primary source
        freeze_home = {k: v for k, v in (freeze_frame or {}).items() if v.get("team") == "home"}
        freeze_away = {k: v for k, v in (freeze_frame or {}).items() if v.get("team") == "away"}

        for team, team_name in (("home", home_team), ("away", away_team)):
            slots = self._formation_slots(team, ball_x, ball_y, press_avg, event)
            team_known = [p for p in last_known.values() if p["team"] == team]
            team_window = [p for p in window_positions.values() if p["team"] == team]
            team_freeze = list((freeze_home if team == "home" else freeze_away).values())
            used_ids: set[str] = set()

            for i, (sx, sy) in enumerate(slots):
                slot_id = f"{team}-{i}"
                pick = None

                # Priority 1: freeze-frame data (exact StatsBomb positions)
                if i < len(team_freeze):
                    ff = team_freeze[i]
                    if ff["id"] not in used_ids:
                        pick = {**ff}

                # Priority 2: window positions (actual event data)
                if pick is None:
                    for wp in team_window:
                        if wp["id"] not in used_ids:
                            pick = wp
                            break

                # Priority 3: last-known positions (heavily favored over template)
                if pick is None:
                    for lk in team_known:
                        if lk["id"] not in used_ids:
                            pick = lk
                            break

                if pick is None:
                    pick = {
                        "id": slot_id,
                        "player_id": 9000 + i + (0 if team == "home" else 11),
                        "x": sx,
                        "y": sy,
                        "name": f"{'H' if team == 'home' else 'A'}{i + 1}",
                        "team": team,
                        "team_name": team_name,
                        "pressure": 48.0 + (press_avg - 50) * 0.2,
                        "is_active": False,
                    }
                else:
                    pick = {**pick, "id": pick.get("id", slot_id)}
                    # Blend: heavily favor real data (75%) over formation template (25%)
                    if pick["id"] not in window_positions and pick["id"] not in (freeze_frame or {}):
                        if pick["id"] in last_known:
                            lk = last_known[pick["id"]]
                            pick["x"] = lk["x"] * 0.75 + sx * 0.25
                            pick["y"] = lk["y"] * 0.75 + sy * 0.25

                used_ids.add(pick["id"])
                pick["is_active"] = int(pick.get("player_id") or 0) == int(active_pid or -1)
                players.append(
                    self._enrich_player(pick, ball_x, ball_y, passing_lanes)
                )

        return players

    def _defensive_lines(self, players: list[dict]) -> tuple[float, float]:
        home_def = [p["x"] for p in players if p.get("team") == "home" and p["x"] < 38]
        away_def = [p["x"] for p in players if p.get("team") == "away" and p["x"] > 82]
        home_line = sum(home_def) / len(home_def) if home_def else 22.0
        away_line = sum(away_def) / len(away_def) if away_def else 98.0
        return home_line, away_line

    def _calculate_team_shape(self, players: list[dict], team: str) -> dict:
        team_pl = [p for p in players if p.get("team") == team and p.get("x") is not None and p.get("y") is not None]
        if not team_pl:
            return {"width": 0, "depth": 0, "compactness": 0, "offside_line": 0}
        xs = [p["x"] for p in team_pl]
        ys = [p["y"] for p in team_pl]
        width = max(ys) - min(ys)
        depth = max(xs) - min(xs)
        compactness = (width * depth) / max(len(team_pl), 1)
        if team == "home":
            offside_line = min(xs) if min(xs) > 10 else min([x for x in xs if x > 10] or [10])
        else:
            offside_line = max(xs) if max(xs) < 110 else max([x for x in xs if x < 110] or [110])
        
        return {
            "width": round(width, 1),
            "depth": round(depth, 1),
            "compactness": round(compactness, 1),
            "offside_line": round(offside_line, 1)
        }

    def _defensive_lines_at_start(
        self, players: list[dict], ball_dx: float, ball_dy: float, press_avg: float,
    ) -> tuple[float, float]:
        home_line, away_line = self._defensive_lines(players)
        compress = (press_avg - 50) / 50
        home_start = home_line - ball_dx * 0.55 - compress * 2
        away_start = away_line - ball_dx * 0.45 + compress * 2
        return home_start, away_start

    def _danger_zone(self, ball_x: float, ball_y: float, event: dict, scale: float = 1.0) -> dict:
        et = str(event.get("event_type", "")).lower()
        threat = 1.25 if "shot" in et or "goal" in et else 1.0
        atk_push = 10 if ball_x > 60 else -10
        return {
            "x": round(max(8, min(112, ball_x + atk_push * 0.35)), 1),
            "y": round(max(6, min(74, ball_y)), 1),
            "radius": round((11 + abs(ball_x - 60) * 0.08) * threat * scale, 1),
            "intensity": round(min(1.0, 0.35 + abs(ball_x - 60) / 120), 2),
        }

    def _pressure_zones_from_players(self, players: list[dict]) -> list[dict]:
        zones = []
        for p in players:
            press = p.get("pressure", 50)
            if press > 42:
                zones.append({
                    "x": p.get("x", 60),
                    "y": p.get("y", 40),
                    "radius": 7 + press / 18,
                    "intensity": press / 100,
                })
        return zones[:14]

    def _ball_at_replay_start(self, events_df: pd.DataFrame, minute: int, event: dict) -> tuple[float, float]:
        """Ball location at the start of the replay segment (before this moment)."""
        sec = int(event.get("second") or 0)
        if "location_x" not in events_df.columns:
            return float(event.get("location_x") or 60), float(event.get("location_y") or 40)

        prior = events_df[
            (events_df["minute"] < minute)
            | ((events_df["minute"] == minute) & (events_df["second"].fillna(0) < sec))
        ].copy()
        prior = prior[prior["location_x"].notna()].sort_values(["minute", "second"], ascending=False)
        window = prior[prior["minute"] >= max(0, minute - 3)]
        if len(window) > 0:
            r = window.iloc[0]
            return float(r["location_x"]), float(r["location_y"])
        if len(prior) > 0:
            r = prior.iloc[0]
            return float(r["location_x"]), float(r["location_y"])
        bx = float(event.get("location_x") or 60)
        by = float(event.get("location_y") or 40)
        return max(10, bx - 12), by

    def _attach_replay_tracks(
        self,
        players: list[dict],
        events_df: pd.DataFrame,
        minute: int,
        event: dict,
        ball_x: float,
        ball_y: float,
        ball_start_x: float,
        ball_start_y: float,
    ) -> list[dict]:
        """Per-player from→to coordinates — tactical shift guaranteed visible movement."""
        sec = int(event.get("second") or 0)
        hist = self._events_before(events_df, minute, sec)
        if "second" not in hist.columns:
            hist["second"] = 0
        hist = hist.sort_values(["minute", "second"], ascending=False)

        ball_dx = ball_x - ball_start_x
        ball_dy = ball_y - ball_start_y
        press_avg = sum(p.get("pressure", 50) for p in players) / max(len(players), 1)
        compress = (press_avg - 50) / 100

        for p in players:
            pid = int(p.get("player_id") or 0)
            fx, fy, fpress = None, None, p.get("pressure", 50)
            role = str(p.get("role", ""))

            if pid > 0 and len(hist):
                rows = hist[hist["player_id"] == pid]
                if len(rows) and not pd.isna(rows.iloc[0].get("location_x")):
                    r = rows.iloc[0]
                    fx = float(r["location_x"])
                    fy = float(r["location_y"])

            team = p.get("team", "home")
            if "Defender" in role or (team == "home" and p["x"] < 35) or (team == "away" and p["x"] > 85):
                wx, wy = 0.68, 0.32
            elif "Midfielder" in role:
                wx, wy = 0.48, 0.28
            else:
                wx, wy = 0.82, 0.45

            sign = 1.0 if team == "home" else -1.0
            if fx is None:
                fx = p["x"] - sign * ball_dx * wx - 5 * sign
                fy = p["y"] - ball_dy * wy
            if "Midfielder" in role:
                fy = fy + compress * 4 * (1 if p["y"] > 40 else -1)

            fx = max(8, min(112, fx))
            fy = max(6, min(74, fy))

            tx, ty = p["x"], p["y"]
            # Guarantee visible movement — minimum 5 units displacement
            dist = math.hypot(tx - fx, ty - fy)
            if dist < 5.0:
                fx = tx - sign * max(6.0, abs(ball_dx) * wx + 4.0)
                fy = ty - max(3.0, abs(ball_dy) * wy + 2.0)
                fx = max(8, min(112, fx))
                fy = max(6, min(74, fy))

            p["from_x"] = round(fx, 1)
            p["from_y"] = round(fy, 1)
            p["to_x"] = round(tx, 1)
            p["to_y"] = round(ty, 1)
            p["from_pressure"] = round(max(20, min(95, float(fpress) - abs(ball_dx) * 0.12 - compress * 8)), 1)

        return players

    def _synthetic_formation(
        self,
        existing: list[dict],
        home_team: str,
        away_team: str,
        event: dict,
        ball_x: float,
        ball_y: float,
    ) -> list[dict]:
        """Fill pitch with approximate 4-4-2 when event coordinates are sparse."""
        if len(existing) >= 14:
            return existing
        out = list(existing)
        existing_ids = {p.get("player_id") for p in out}
        active_pid = event.get("player_id")
        home_slots = [
            (12, 40), (25, 15), (25, 35), (25, 55), (25, 75),
            (45, 20), (45, 40), (45, 60), (45, 80),
            (70, 30), (70, 50),
        ]
        away_slots = [
            (108, 40), (95, 15), (95, 35), (95, 55), (95, 75),
            (75, 20), (75, 40), (75, 60), (75, 80),
            (50, 30), (50, 50),
        ]
        pid = 9000
        for i, (x, y) in enumerate(home_slots):
            if len([p for p in out if p["team"] == "home"]) >= 11:
                break
            pid += 1
            if pid in existing_ids:
                continue
            out.append({
                "id": str(pid),
                "player_id": pid,
                "x": x + (ball_x - 60) * 0.05,
                "y": y,
                "name": f"H{i+1}",
                "team": "home",
                "team_name": home_team,
                "pressure": 45.0,
                "is_active": pid == active_pid,
            })
        for i, (x, y) in enumerate(away_slots):
            if len([p for p in out if p["team"] == "away"]) >= 11:
                break
            pid += 1
            if pid in existing_ids:
                continue
            out.append({
                "id": str(pid),
                "player_id": pid,
                "x": x - (ball_x - 60) * 0.05,
                "y": y,
                "name": f"A{i+1}",
                "team": "away",
                "team_name": away_team,
                "pressure": 55.0,
                "is_active": pid == active_pid,
            })
        return out

    def _pressure_zones(self, players: list[dict]) -> list[dict]:
        return self._pressure_zones_from_players(players)

    def build_local_why(self, event: dict, replay_ctx: dict, pitch: dict) -> dict:
        et = event.get("event_type", "event")
        player = event.get("player_name", "Player")
        minute = event.get("minute", 0)
        situation = replay_ctx.get("situation", {})
        return {
            "headline": f"Why this {et.lower()} happened at {minute}'",
            "tactical_pattern": self._infer_pattern(event, pitch),
            "defender_reaction": situation.get("opponent_pressure", ""),
            "attacker_choice": situation.get("what_player_likely_saw", ""),
            "space_exploited": self._space_exploited(pitch),
            "pressure_effect": f"Pressure index {replay_ctx.get('pressure_index', 50):.0f}/100 on {player}.",
            "cognitive_load": replay_ctx.get("psychological_state", {}),
            "analyst_narrative": situation.get("what_player_likely_saw", ""),
            "granite_pending": False,
        }

    def _infer_pattern(self, event: dict, pitch: dict) -> str:
        bx = pitch.get("ball", {}).get("x", 60)
        et = str(event.get("event_type", ""))
        if bx > 100:
            return "Final-third overload with runners beyond the defensive line."
        if et == "Pass" and event.get("under_pressure"):
            return "Press-resistant circulation under coordinated midfield press."
        if et in ("Carry", "Dribble"):
            return "Individual carry to break compact defensive block."
        if et == "Shot":
            return "Shot creation from established attacking phase."
        return "Structured possession progression into advanced areas."

    def _space_exploited(self, pitch: dict) -> str:
        bx = pitch.get("ball", {}).get("x", 60)
        by = pitch.get("ball", {}).get("y", 40)
        if bx > 102 and by < 30:
            return "Far-post channel behind the defensive line."
        if bx > 102 and by > 50:
            return "Near-post cut-back zone."
        if 80 < bx <= 102:
            return "Half-space between midfield and defensive line."
        return "Central corridor between defensive units."

    def _scoring_team(self, event: dict, home_team: str, away_team: str) -> Optional[str]:
        """Resolve which side scored, including own goals."""
        et = str(event.get("event_type") or event.get("type", "")).lower()
        outcome = str(event.get("outcome", "")).lower()
        team = str(event.get("team", "") or "")
        if "own goal against" in et:
            if team == home_team:
                return away_team
            if team == away_team:
                return home_team
            return None
        if "own goal for" in et:
            return team if team in (home_team, away_team) else None
        is_goal = et == "goal" or (et == "shot" and "goal" in outcome)
        if not is_goal:
            return None
        if team in (home_team, away_team):
            return team
        return None

    def _is_goal(self, row, team: str, home_team: str = "", away_team: str = "") -> bool:
        if home_team and away_team:
            return self._scoring_team(dict(row), home_team, away_team) == team
        if row.get("team") != team:
            return False
        if str(row.get("type", "")) == "Goal":
            return True
        return str(row.get("type", "")) == "Shot" and "goal" in str(row.get("outcome", "")).lower()

    def _enrich_player(self, p: dict, ball_x: float, ball_y: float, lanes: list) -> dict:
        """Derive interactive scout metrics from position + pressure."""
        y = p.get("y", 40)
        x = p.get("x", 60)
        pressure = float(p.get("pressure", 50))
        if y < 26:
            role = "Full-back / wide"
        elif y > 54:
            role = "Full-back / wide"
        elif x > 90:
            role = "Attacker"
        elif x < 35:
            role = "Defender"
        else:
            role = "Midfielder"
        dist_ball = ((x - ball_x) ** 2 + (y - ball_y) ** 2) ** 0.5
        xthreat = max(0, min(1, (x / 120) * 0.6 + (1 - dist_ball / 80) * 0.4))
        decision = max(35, min(95, 72 - pressure * 0.25 + xthreat * 20))
        speed = round(18 + (100 - dist_ball) * 0.12, 1)
        options = []
        for lane in lanes[:3]:
            options.append({
                "type": "pass",
                "to": lane.get("to"),
                "success_prob": 0.72 if lane.get("success") else 0.41,
            })
        if x > 85:
            options.append({"type": "shot", "xG": round(xthreat * 0.35, 2)})
        p.update({
            "role": role,
            "speed_kmh": speed,
            "decision_score": round(decision, 0),
            "xthreat": round(xthreat, 2),
            "pressure_index": round(pressure, 0),
            "expected_action": options[0]["type"] if options else ("shot" if x > 95 else "carry"),
            "pass_options": options,
            "space_control_pct": round(max(0, 100 - dist_ball * 1.2), 0),
        })
        return p

    def build_why_brief(self, why: dict, event: dict, investigation: Optional[dict] = None) -> dict:
        if why.get("bullets"):
            bullets = why["bullets"]
        else:
            inv = investigation or {}
            bullets = [
                {"key": "why", "label": "Why this happened", "text": _short(inv.get("why") or why.get("headline", ""), 120)},
                {"key": "mistake", "label": "Biggest tactical mistake", "text": _short(inv.get("defensive_mistake") or why.get("defender_reaction", ""), 120)},
                {"key": "pass", "label": "Best passing option", "text": _short(inv.get("best_passing_option") or why.get("attacker_choice", ""), 120)},
                {"key": "takeaway", "label": "Tactical takeaway", "text": _short(inv.get("tactical_pattern") or why.get("tactical_pattern", ""), 120)},
            ]
            bullets = [b for b in bullets if b.get("text")]
        conf = why.get("confidence", 0.78)
        if isinstance(conf, (int, float)) and conf <= 1:
            conf = round(conf * 100)
        highlight_map = {
            "why": "attacker movement",
            "mistake": "defensive mistake",
            "pass": "passing lane",
            "takeaway": "pressing trigger",
        }
        return {
            "bullets": bullets,
            "summary": bullets[0]["text"] if bullets else f"Key moment at {event.get('minute')}'",
            "confidence": conf,
            "highlight": why.get("space_exploited", "half-space"),
            "sync_steps": [
                {"text": b["text"], "highlight": highlight_map.get(b["key"], "half-space"), "duration_ms": 2200}
                for b in bullets[:4]
            ],
        }

    def build_visual_investigation(self, event: dict, pitch: dict, why: dict, why_brief: dict) -> dict:
        """Concise pitch-first tactical investigation — replaces long explanation blocks."""
        lanes = pitch.get("passing_lanes", []) if pitch else []
        best_lane = max(lanes, key=lambda l: (1 if l.get("success") else 0, l.get("to", [0])[0]), default=None)
        best_pass = "Through ball wide" if best_lane else "Carry into half-space"
        if best_lane:
            best_pass = f"Pass to ({best_lane.get('to', [0, 0])[0]:.0f}, {best_lane.get('to', [0, 0])[1]:.0f})"

        alts = why.get("alternatives") or []
        missed = alts[0] if alts else why_brief.get("takeaway", "Delayed pass allowed press to recover")
        if isinstance(missed, dict):
            missed = missed.get("label", str(missed))

        conf = why_brief.get("confidence", 78)
        if isinstance(conf, float) and conf <= 1:
            conf = round(conf * 100)

        return {
            "why": _short(why_brief.get("summary") or why.get("headline", ""), 120),
            "best_passing_option": _short(best_pass, 80),
            "missed_opportunity": _short(str(missed), 100),
            "defensive_mistake": _short(str(why.get("defender_reaction", "Line stepped late")), 100),
            "tactical_pattern": _short(str(why.get("tactical_pattern", "Half-space progression")), 90),
            "confidence": conf,
            "highlights": {
                "why": "attacker movement",
                "best_passing_option": "passing lane",
                "missed_opportunity": "half-space",
                "defensive_mistake": "defensive mistake",
                "tactical_pattern": "pressing trigger",
            },
            "granite_line": _short(
                f"At {event.get('minute', 'this minute')}': {event.get('player_name', 'Player')} triggers {why.get('tactical_pattern', 'tactical action').lower()} exploiting {why.get('space_exploited', 'space')}. {best_pass} with {why.get('pressure_effect', 'pressure')}.",
                180,
            ),
        }

    def build_detective_challenge(
        self, event: dict, pitch: dict, why: dict,
        match_state: Optional[dict] = None, snapshot: Optional[dict] = None,
    ) -> dict:
        """AI Tactical Detective — freeze attack, ask user to decide."""
        from engine.event_grounding import build_tactical_snapshot, coach_pick, coach_reason

        et = str(event.get("event_type", "Pass"))
        player = event.get("player_name", "Player")
        minute = event.get("minute", 0)
        bx = pitch.get("ball", {}).get("x", 60)
        xg = round(min(0.55, bx / 120 * 0.45), 2)
        xt = round(min(0.4, bx / 120 * 0.35), 2)

        options = [
            {"id": "pass", "label": "Play the through ball", "xG": round(xg * 0.6, 2), "xT": round(xt * 1.1, 2)},
            {"id": "shot", "label": "Shoot now", "xG": xg, "xT": round(xt * 0.5, 2)},
            {"id": "carry", "label": "Carry and draw pressure", "xG": round(xg * 0.3, 2), "xT": round(xt * 1.3, 2)},
            {"id": "switch", "label": "Switch play wide", "xG": round(xg * 0.25, 2), "xT": round(xt * 0.8, 2)},
            {"id": "press", "label": "Trigger the press", "xG": round(xg * 0.15, 2), "xT": round(xt * 0.9, 2)},
            {"id": "hold_shape", "label": "Hold defensive shape", "xG": round(xg * 0.08, 2), "xT": round(xt * 0.15, 2)},
        ]
        ai_optimal = max(options, key=lambda o: o["xG"] * 0.6 + o["xT"] * 0.4)["id"]

        actual_map = {"Shot": "shot", "Pass": "pass", "Carry": "carry", "Dribble": "carry"}
        actual_id = actual_map.get(et, "pass")

        snap = snapshot or build_tactical_snapshot(event, pitch, match_state, None, why)
        granite_pick = coach_pick(snap, "granite")
        coach_picks = {
            "pep": coach_pick(snap, "pep"),
            "klopp": coach_pick(snap, "klopp"),
            "ancelotti": coach_pick(snap, "ancelotti"),
            "mourinho": coach_pick(snap, "mourinho"),
        }
        personas = {
            k: coach_reason(k, snap, coach_picks[k])
            for k in coach_picks
        }

        return {
            "frozen": True,
            "prompt": (
                f"Frozen at {minute}' ({snap.get('score', '?')}). "
                f"{player} on ball (x={snap['ball_x']}, y={snap['ball_y']}) — "
                f"{snap['passing_lanes_count']} lanes, pressure {snap['pressure_index']}/100."
            ),
            "options": options,
            "actual_choice": actual_id,
            "actual_event": et,
            "metrics": {"xG": xg, "xThreat": xt, "pressure": why.get("pressure_effect", "")},
            "coach_picks": coach_picks,
            "ai_optimal": granite_pick,
            "coach_reasoning": personas,
            "granite_reasoning": coach_reason("granite", snap, granite_pick),
        }

    def build_coach_recommendations(
        self, event: dict, pitch: dict, why: dict, user_choice: Optional[str] = None,
        snapshot: Optional[dict] = None,
    ) -> dict:
        """Situation-derived coach picks for Tactical Detective."""
        from engine.event_grounding import build_tactical_snapshot, coach_reason

        challenge = self.build_detective_challenge(
            event, pitch, why, snapshot=snapshot,
        )
        opts = {o["id"]: o for o in challenge.get("options", [])}
        personas = challenge.get("coach_reasoning") or {}

        def _metrics(pick: str) -> tuple[float, float]:
            o = opts.get(pick, {})
            xg = float(o.get("xG", 0.15))
            xt = float(o.get("xT", 0.12))
            success = round(min(95, 28 + xg * 95 + xt * 22), 0)
            threat = round(min(95, xt * 115 + xg * 18), 0)
            return success, threat

        def _rec(coach_id: str, name: str, pick: str, reason: str) -> dict:
            o = opts.get(pick, {})
            success, threat = _metrics(pick)
            short_reason = _short(reason, 140)
            return {
                "id": coach_id,
                "name": name,
                "action_id": pick,
                "action": o.get("label", pick.replace("_", " ").title()),
                "reason": short_reason,
                "expected_success": success,
                "expected_threat": threat,
                "explanation": _short(short_reason, 90),
            }

        granite_pick = challenge.get("ai_optimal", "pass")
        picks = challenge.get("coach_picks", {})
        coaches = [
            ("granite", "IBM Granite", granite_pick, challenge.get("granite_reasoning", "")),
            ("pep", "Pep Guardiola", picks.get("pep", "pass"), personas.get("pep", "")),
            ("klopp", "Jürgen Klopp", picks.get("klopp", "press"), personas.get("klopp", "")),
            ("ancelotti", "Carlo Ancelotti", picks.get("ancelotti", "hold_shape"), personas.get("ancelotti", "")),
            ("mourinho", "José Mourinho", picks.get("mourinho", "hold_shape"), personas.get("mourinho", "")),
        ]
        recommendations = [_rec(cid, name, pick, reason) for cid, name, pick, reason in coaches if reason]

        if user_choice:
            snap = snapshot or build_tactical_snapshot(event, pitch, None, None, why)
            recommendations.insert(0, _rec(
                "user", "Your Decision", user_choice,
                f"Your read at {snap['minute']}' ({snap['score']}) with {snap['player']} "
                f"at ({snap['ball_x']}, {snap['ball_y']}).",
            ))

        return {
            "prompt": challenge.get("prompt", ""),
            "options": challenge.get("options", []),
            "actual_choice": challenge.get("actual_choice", "pass"),
            "ai_optimal": granite_pick,
            "recommendations": recommendations,
        }

    def _detective_morph_pitch(self, pitch: dict, choice: str) -> dict:
        """Animate tactical outcome for a detective decision."""
        if not pitch:
            return pitch
        out = {**pitch, "players": [dict(p) for p in pitch.get("players", [])]}
        ball = dict(out.get("ball", {"x": 60, "y": 40}))
        bx, by = float(ball.get("x", 60)), float(ball.get("y", 40))
        deltas = {
            "pass": (8, 2),
            "shot": (6, 0),
            "carry": (5, 3),
            "switch": (-4, 12),
            "press": (3, -5),
            "hold_shape": (-2, 0),
        }
        dx, dy = deltas.get(choice, (4, 0))
        ball["x"] = max(10, min(115, bx + dx))
        ball["y"] = max(5, min(75, by + dy))
        out["ball"] = ball

        for p in out["players"]:
            if p.get("is_active"):
                p["x"] = ball["x"] - 2
                p["y"] = ball["y"]
            elif p.get("team") == "home" and choice in ("pass", "carry", "shot"):
                if p.get("x", 0) > bx - 5:
                    p["x"] = min(115, p.get("x", 60) + dx * 0.4)
            elif p.get("team") == "away":
                shift = -3 if choice == "press" else 2 if choice == "hold_shape" else -1
                p["x"] = max(15, min(110, p.get("x", 60) + shift))

        lanes = []
        for lane in pitch.get("passing_lanes", [])[:6]:
            fr, to = lane.get("from", [bx, by]), lane.get("to", [bx + 10, by])
            lanes.append({
                **lane,
                "from": [ball["x"], ball["y"]],
                "to": [ball["x"] + dx * 1.2, ball["y"] + dy * 0.8],
                "success": choice in ("pass", "switch", "carry"),
            })
        out["passing_lanes"] = lanes
        out["pressure_zones"] = self._pressure_zones(out["players"])
        return out

    def evaluate_detective_choice(
        self, user_choice: str, challenge: dict, event: dict, pitch: Optional[dict] = None,
    ) -> dict:
        actual = challenge.get("actual_choice", "pass")
        opts = {o["id"]: o for o in challenge.get("options", [])}
        user_opt = opts.get(user_choice, opts.get("pass", {}))
        actual_opt = opts.get(actual, user_opt)
        coach_picks = challenge.get("coach_picks", {})
        matches_actual = user_choice == actual
        alignment = sum(1 for v in coach_picks.values() if v == user_choice)

        ai_opt = challenge.get("ai_optimal", actual)
        ai_opt_data = opts.get(ai_opt, actual_opt)

        def metrics_for(choice_id: str) -> dict:
            o = opts.get(choice_id, {})
            press = round(40 + (o.get("xT", 0.1) * 80), 1)
            wp = round(33 + o.get("xG", 0.1) * 40 + o.get("xT", 0.1) * 20, 1)
            return {
                "xG": o.get("xG"),
                "xT": o.get("xT"),
                "pressure_outcome": press,
                "win_probability": wp,
            }

        coach_labels = {
            "pep": "Pep Guardiola",
            "klopp": "Jürgen Klopp",
            "mourinho": "José Mourinho",
            "arteta": "Mikel Arteta",
            "ancelotti": "Carlo Ancelotti",
        }
        coach_comparisons = []
        for key, label in coach_labels.items():
            pick = coach_picks.get(key, "pass")
            coach_comparisons.append({
                "coach": label,
                "coach_id": key,
                "choice": pick,
                "label": opts.get(pick, {}).get("label", pick),
                "metrics": metrics_for(pick),
                "replay_pitch": self._detective_morph_pitch(pitch, pick) if pitch else None,
            })

        replays = {
            "user": self._detective_morph_pitch(pitch, user_choice) if pitch else None,
            "actual": self._detective_morph_pitch(pitch, actual) if pitch else None,
            "ai_optimal": self._detective_morph_pitch(pitch, ai_opt) if pitch else None,
        }

        return {
            "user_choice": user_choice,
            "actual_choice": actual,
            "ai_optimal": ai_opt,
            "matches_actual": matches_actual,
            "matches_ai_optimal": user_choice == ai_opt,
            "coach_alignment": alignment,
            "coach_agreement": [coach_labels.get(k, k) for k, v in coach_picks.items() if v == user_choice],
            "user_metrics": metrics_for(user_choice),
            "actual_metrics": metrics_for(actual),
            "ai_optimal_metrics": metrics_for(ai_opt),
            "coach_comparisons": coach_comparisons,
            "replays": replays,
            "verdict": (
                f"Excellent read — you matched what {event.get('player_name', 'the player')} did."
                if matches_actual
                else f"Different from the actual {challenge.get('actual_event', 'action')}, but "
                f"{alignment} elite coaches would choose the same."
            ),
            "granite_note": challenge.get("granite_reasoning", ""),
        }
