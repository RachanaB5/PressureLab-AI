"""
Chronological pitch state engine — builds true per-event player positions
from event coordinates, pass/carry endpoints, and neighbor inference.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

PW, PH = 120.0, 80.0


def _safe_float(val: Any) -> float | None:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_xy(val: Any) -> tuple[float | None, float | None]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None, None
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return _safe_float(val[0]), _safe_float(val[1])
    return None, None


def _event_time(row: dict) -> tuple[int, int, int]:
    return (
        int(row.get("minute") or 0),
        int(row.get("second") or 0),
        int(row.get("id") or 0),
    )


def _is_before(row: dict, target: dict) -> bool:
    rm, rs, rid = _event_time(row)
    tm, ts, tid = _event_time(target)
    if rm < tm:
        return True
    if rm == tm and rs < ts:
        return True
    if rm == tm and rs == ts and rid < tid:
        return True
    return False


def _is_at_or_before(row: dict, target: dict) -> bool:
    return _is_before(row, target) or (
        _event_time(row) == _event_time(target)
    )


def _team_side(team_name: str, home_team: str) -> str:
    return "home" if team_name == home_team else "away"


def _extract_event_xy(row: dict) -> tuple[float | None, float | None]:
    lx = _safe_float(row.get("location_x"))
    ly = _safe_float(row.get("location_y"))
    if lx is not None and ly is not None:
        return lx, ly
    loc = row.get("location")
    return _parse_xy(loc)


def _extract_pass_end(row: dict) -> tuple[float | None, float | None]:
    details = row.get("details") or {}
    if isinstance(details, dict):
        pas = details.get("pass") or {}
        if isinstance(pas, dict):
            end = pas.get("end_location")
            lx, ly = _parse_xy(end)
            if lx is not None:
                return lx, ly
    return _parse_xy(row.get("pass_end_location"))


def _extract_carry_end(row: dict) -> tuple[float | None, float | None]:
    details = row.get("details") or {}
    if isinstance(details, dict):
        for key in ("carry", "dribble"):
            block = details.get(key) or {}
            if isinstance(block, dict):
                lx, ly = _parse_xy(block.get("end_location"))
                if lx is not None:
                    return lx, ly
    return _parse_xy(row.get("carry_end_location"))


def _extract_freeze_positions(row: dict, home_team: str, away_team: str) -> dict[str, dict]:
    details = row.get("details") or {}
    shot = details.get("shot") if isinstance(details, dict) else {}
    freeze = shot.get("freeze_frame") if isinstance(shot, dict) else None
    if not isinstance(freeze, list):
        return {}
    out: dict[str, dict] = {}
    event_team = str(row.get("team") or "")
    for entry in freeze:
        if not isinstance(entry, dict):
            continue
        lx, ly = _parse_xy(entry.get("location"))
        if lx is None:
            continue
        player = entry.get("player") or {}
        pid = player.get("id") if isinstance(player, dict) else 0
        pname = player.get("name") if isinstance(player, dict) else f"#{pid}"
        teammate = bool(entry.get("teammate", False))
        if teammate:
            side = _team_side(event_team, home_team)
        else:
            side = "away" if event_team == home_team else "home"
        sid = str(pid) if pid else f"ff-{len(out)}"
        out[sid] = {
            "id": sid,
            "player_id": int(pid or 0),
            "x": lx,
            "y": ly,
            "name": str(pname),
            "team": side,
            "team_name": home_team if side == "home" else away_team,
        }
    return out


class PitchStateEngine:
    """Walk match events chronologically to derive true per-event pitch states."""

    def __init__(self, home_team: str, away_team: str, lineup: list[dict] | None = None):
        self.home_team = home_team
        self.away_team = away_team
        self.lineup = lineup or []
        self.ball = {"x": 60.0, "y": 40.0}
        self.players: dict[str, dict] = {}
        self.history: list[dict[str, dict]] = []

    def _apply_row(self, row: dict) -> None:
        et = str(row.get("type") or row.get("event_type") or "")
        pid = int(row.get("player_id") or 0)
        team = str(row.get("team") or "")
        side = _team_side(team, self.home_team) if team else None
        pname = str(row.get("player_name") or f"#{pid}")

        lx, ly = _extract_event_xy(row)
        if lx is not None and ly is not None:
            self.ball = {"x": lx, "y": ly}
            if pid > 0:
                self.players[str(pid)] = {
                    "id": str(pid),
                    "player_id": pid,
                    "x": lx,
                    "y": ly,
                    "name": pname,
                    "team": side or "home",
                    "team_name": team,
                }

        if et == "Pass":
            ex, ey = _extract_pass_end(row)
            if ex is not None:
                self.ball = {"x": ex, "y": ey}
                details = row.get("details") or {}
                pas = details.get("pass") if isinstance(details, dict) else {}
                recipient = {}
                if isinstance(pas, dict):
                    recipient = pas.get("recipient") or {}
                rid = int(recipient.get("id") or row.get("pass_recipient_id") or 0)
                rname = str(recipient.get("name") or row.get("pass_recipient") or f"#{rid}")
                if rid > 0:
                    self.players[str(rid)] = {
                        "id": str(rid),
                        "player_id": rid,
                        "x": ex,
                        "y": ey,
                        "name": rname,
                        "team": side or "home",
                        "team_name": team,
                    }

        if et in ("Carry", "Dribble"):
            ex, ey = _extract_carry_end(row)
            if ex is not None and pid > 0:
                self.players[str(pid)] = {
                    **self.players.get(str(pid), {
                        "id": str(pid), "player_id": pid, "name": pname,
                        "team": side or "home", "team_name": team,
                    }),
                    "x": ex,
                    "y": ey,
                }
                self.ball = {"x": ex, "y": ey}

        freeze = _extract_freeze_positions(row, self.home_team, self.away_team)
        if freeze:
            self.players.update(freeze)
            if lx is not None:
                self.ball = {"x": lx, "y": ly}

        self.history.append({k: {**v} for k, v in self.players.items()})

    def snapshot(self) -> dict:
        return {
            "ball": dict(self.ball),
            "players": {k: {**v} for k, v in self.players.items()},
        }

    def build_states_at_event(
        self,
        events_df: pd.DataFrame,
        target: dict,
        pressure_fn=None,
    ) -> tuple[dict, dict]:
        """Return (state_before, state_after) for the target event."""
        if "type" not in events_df.columns and "event_type" in events_df.columns:
            events_df = events_df.copy()
            events_df["type"] = events_df["event_type"]
        if "second" not in events_df.columns:
            events_df = events_df.copy()
            events_df["second"] = 0

        rows = events_df.sort_values(["minute", "second", "id"]).to_dict("records")
        state_before: dict | None = None

        for row in rows:
            if _is_before(row, target):
                self._apply_row(row)
                continue
            if _event_time(row) == _event_time(target):
                state_before = self.snapshot()
                self._apply_row(row)
                state_after = self.snapshot()
                return (
                    self._finalize_state(state_before, target, pressure_fn),
                    self._finalize_state(state_after, target, pressure_fn),
                )
            break

        if state_before is None:
            state_before = self.snapshot()
        self._apply_row(target)
        return (
            self._finalize_state(state_before, target, pressure_fn),
            self._finalize_state(self.snapshot(), target, pressure_fn),
        )

    def _finalize_state(self, state: dict, target: dict, pressure_fn) -> dict:
        minute = int(target.get("minute") or 0)
        squad = self._build_squad_from_state(state, target, minute, pressure_fn)
        ball = state.get("ball") or {"x": 60.0, "y": 40.0}
        return {"ball": ball, "players": squad}

    def _build_squad_from_state(
        self,
        state: dict,
        target: dict,
        minute: int,
        pressure_fn,
    ) -> list[dict]:
        known = state.get("players") or {}
        active_pid = int(target.get("player_id") or 0)
        ball = state.get("ball") or {"x": 60.0, "y": 40.0}
        bx, by = float(ball["x"]), float(ball["y"])

        lineup_home = [p for p in self.lineup if p.get("team") == self.home_team]
        lineup_away = [p for p in self.lineup if p.get("team") == self.away_team]
        if not lineup_home or not lineup_away:
            lineup_home = [p for p in known.values() if p.get("team") == "home"]
            lineup_away = [p for p in known.values() if p.get("team") == "away"]

        squad: list[dict] = []
        for side, team_name, lineup in (
            ("home", self.home_team, lineup_home),
            ("away", self.away_team, lineup_away),
        ):
            used: set[str] = set()
            roster = list(lineup)[:11]
            if len(roster) < 11:
                extras = [p for p in known.values() if p.get("team") == side and p["id"] not in used]
                for p in extras:
                    if len(roster) >= 11:
                        break
                    roster.append(p)

            while len(roster) < 11:
                idx = len(roster)
                roster.append({
                    "id": f"{side}-{idx}",
                    "player_id": 9000 + idx + (0 if side == "home" else 11),
                    "name": f"{'H' if side == 'home' else 'A'}{idx + 1}",
                    "team": side,
                    "team_name": team_name,
                })

            for i, slot_player in enumerate(roster[:11]):
                pid = int(slot_player.get("player_id") or slot_player.get("id") or 0)
                sid = str(slot_player.get("id") or pid or f"{side}-{i}")
                if isinstance(sid, int):
                    sid = str(sid)

                pick = known.get(sid) or known.get(str(pid))
                if pick is None and pid > 0:
                    pick = known.get(str(pid))

                if pick:
                    x, y = float(pick["x"]), float(pick["y"])
                    name = pick.get("name") or slot_player.get("name", f"#{pid}")
                    use_pid = int(pick.get("player_id") or pid or 0)
                    use_id = str(pick.get("id") or sid)
                else:
                    x, y = self._infer_position(side, i, bx, by, target)
                    name = str(slot_player.get("name") or f"{'H' if side == 'home' else 'A'}{i + 1}")
                    use_pid = pid if pid > 0 else 9000 + i + (0 if side == "home" else 11)
                    use_id = sid

                pressure = 50.0
                if pressure_fn and use_pid > 0:
                    pressure = float(pressure_fn(use_pid, minute))

                squad.append({
                    "id": use_id,
                    "player_id": use_pid,
                    "x": round(max(4, min(116, x)), 1),
                    "y": round(max(4, min(76, y)), 1),
                    "name": name,
                    "team": side,
                    "team_name": team_name,
                    "pressure": pressure,
                    "is_active": use_pid == active_pid,
                })
                used.add(use_id)

        return squad

    def _infer_position(self, side: str, slot_idx: int, bx: float, by: float, target: dict) -> tuple[float, float]:
        """Infer from ball-relative role slot — unique per event via ball + event id."""
        eid = int(target.get("id") or 0)
        jitter = ((eid * 17 + slot_idx * 31) % 100) / 100.0 - 0.5
        roles = [
            (0.08, 0.0), (0.22, -0.22), (0.22, -0.08), (0.22, 0.08), (0.22, 0.22),
            (0.38, -0.18), (0.38, -0.05), (0.38, 0.05), (0.38, 0.18),
            (0.55, -0.12), (0.55, 0.12),
        ]
        rx, ry = roles[min(slot_idx, len(roles) - 1)]
        if side == "away":
            rx = 1.0 - rx
        x = bx + (rx - 0.5) * 70 + jitter * 4
        y = by + ry * 35 + jitter * 3
        if side == "home":
            x = min(x, bx + 25)
        else:
            x = max(x, bx - 25)
        return max(6, min(114, x)), max(6, min(74, y))


def merge_fresh_coordinates(db_events: list[dict], fresh_events: list[dict]) -> list[dict]:
    """Overlay coordinates from freshly loaded StatsBomb events onto DB events."""
    if not fresh_events:
        return db_events

    fresh_sorted = sorted(fresh_events, key=lambda e: (
        int(e.get("minute") or 0),
        int(e.get("second") or 0),
        int(e.get("player_id") or 0),
        str(e.get("event_type") or ""),
    ))
    db_sorted = sorted(db_events, key=lambda e: (
        int(e.get("minute") or 0),
        int(e.get("second") or 0),
        int(e.get("player_id") or 0),
        str(e.get("event_type") or ""),
    ))

    if len(fresh_sorted) == len(db_sorted):
        pairs = zip(db_sorted, fresh_sorted)
    else:
        fresh_map: dict[tuple, dict] = {}
        for fe in fresh_sorted:
            key = (
                int(fe.get("minute") or 0),
                int(fe.get("second") or 0),
                int(fe.get("player_id") or 0),
                str(fe.get("event_type") or ""),
            )
            fresh_map[key] = fe
        pairs = ((de, fresh_map.get((
            int(de.get("minute") or 0),
            int(de.get("second") or 0),
            int(de.get("player_id") or 0),
            str(de.get("event_type") or ""),
        ))) for de in db_sorted)

    merged = []
    for de, fe in pairs:
        if fe is None:
            merged.append(de)
            continue
        out = {**de}
        if fe.get("location_x") is not None:
            out["location_x"] = fe["location_x"]
            out["location_y"] = fe["location_y"]
        if fe.get("details"):
            out["details"] = {**(de.get("details") or {}), **fe["details"]}
        merged.append(out)
    return merged


def coord_coverage(events: list[dict]) -> float:
    if not events:
        return 0.0
    with_coords = sum(1 for e in events if e.get("location_x") is not None)
    return with_coords / len(events)
