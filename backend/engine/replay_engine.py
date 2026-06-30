"""
PressureLab AI - Replay Engine
Reconstructs what a player likely saw at a given minute from event data.
"""

import math
from typing import Any, Optional

import pandas as pd


class ReplayEngine:
    """Build evidence-backed player context for Replay Through Player's Mind."""

    def reconstruct(
        self,
        events_df: pd.DataFrame,
        player_id: int,
        player_name: str,
        team: str,
        minute: int,
        home_team: str,
        away_team: str,
        pressure_score: float,
        pressure_factors: dict,
        psych_profile: dict,
        team_momentum: float,
        opponent_momentum: float,
        competition: str = "",
    ) -> dict:
        if "type" not in events_df.columns and "event_type" in events_df.columns:
            events_df = events_df.copy()
            events_df["type"] = events_df["event_type"]

        score = self._score_at_minute(events_df, minute, home_team, away_team)
        player_event = self._nearest_player_event(events_df, player_id, minute)
        loc_x = player_event.get("location_x") if player_event is not None else 60.0
        loc_y = player_event.get("location_y") if player_event is not None else 40.0

        defenders_nearby = self._count_nearby_opponents(
            events_df, team, minute, loc_x, loc_y
        )
        passing_options = self._infer_passing_options(
            events_df, player_id, team, minute, loc_x, loc_y
        )
        recent = self._recent_player_actions(events_df, player_id, minute)
        pressing = self._pressing_intensity(pressure_factors.get("defensive_pressure", 0.5))

        return {
            "minute": minute,
            "pressure_index": round(pressure_score, 1),
            "score": score,
            "game_state": {
                "score": score,
                "team_momentum": round(team_momentum, 2),
                "opponent_momentum": round(opponent_momentum, 2),
                "competition_importance": competition or "Match",
                "minutes_played": minute,
            },
            "situation": {
                "position_description": self._describe_position(loc_x, loc_y, team, minute, score),
                "opponent_pressure": self._describe_opponent_pressure(
                    defenders_nearby, pressure_score, pressing
                ),
                "defenders_nearby": defenders_nearby,
                "passing_options": passing_options,
                "what_player_likely_saw": self._what_player_saw(
                    defenders_nearby, passing_options, pressure_score, score, team_momentum
                ),
            },
            "psychological_state": {
                attr["name"]: round(attr["value"], 2)
                for attr in psych_profile.get("attributes", [])
            },
            "recent_actions": recent,
            "expected_decision": self._expected_decision(passing_options, pressure_score),
            "risk_appetite": round(
                next(
                    (a["value"] for a in psych_profile.get("attributes", []) if "Risk" in a["name"]),
                    0.5,
                ),
                2,
            ),
        }

    def format_for_granite(self, ctx: dict, player_name: str) -> str:
        return (
            f"Player: {player_name}\n"
            f"Minute: {ctx['minute']}, Score: {ctx['score']}\n"
            f"Pressure Index: {ctx['pressure_index']}/100\n"
            f"Defenders nearby: {ctx['situation']['defenders_nearby']}\n"
            f"Passing options: {ctx['situation']['passing_options']}\n"
            f"What player likely saw: {ctx['situation']['what_player_likely_saw']}\n"
            f"Recent actions: {', '.join(ctx['recent_actions'][:5])}\n"
            f"Psychological state: {ctx['psychological_state']}\n"
        )

    def _score_at_minute(self, df: pd.DataFrame, minute: int, home: str, away: str) -> str:
        subset = df[(df["minute"] <= minute) & (df["type"] == "Shot")]
        if subset.empty:
            subset = df[(df["minute"] <= minute) & (df["type"] == "Goal")]
        home_g, away_g = 0, 0
        for _, row in subset.iterrows():
            outcome = str(row.get("outcome", "")).lower()
            if "goal" not in outcome and row.get("type") != "Goal":
                continue
            if row.get("team") == home:
                home_g += 1
            elif row.get("team") == away:
                away_g += 1
        return f"{home_g}-{away_g}"

    def _nearest_player_event(
        self, df: pd.DataFrame, player_id: int, minute: int
    ) -> Optional[pd.Series]:
        pe = df[(df["player_id"] == player_id) & (df["minute"] <= minute)]
        if pe.empty:
            return None
        pe = pe.copy()
        pe["dist"] = (minute - pe["minute"]).abs()
        return pe.sort_values("dist").iloc[0]

    def _count_nearby_opponents(
        self, df: pd.DataFrame, team: str, minute: int, x: float, y: float
    ) -> int:
        window = df[
            (df["minute"] >= max(0, minute - 1))
            & (df["minute"] <= minute + 1)
            & (df["team"] != team)
        ]
        count = 0
        for _, row in window.iterrows():
            ox, oy = row.get("location_x"), row.get("location_y")
            if pd.isna(ox) or pd.isna(oy) or pd.isna(x) or pd.isna(y):
                if row.get("type") in ("Pressure", "Tackle", "Interception"):
                    count += 1
                continue
            dist = math.hypot(float(ox) - float(x), float(oy) - float(y))
            if dist < 15 or row.get("type") == "Pressure":
                count += 1
        return min(count, 6)

    def _infer_passing_options(
        self, df: pd.DataFrame, player_id: int, team: str, minute: int, x: float, y: float
    ) -> list[dict]:
        window = df[
            (df["minute"] >= max(0, minute - 3))
            & (df["minute"] <= minute)
            & (df["team"] == team)
            & (df["player_id"] != player_id)
        ]
        teammates: dict[str, dict] = {}
        for _, row in window.iterrows():
            name = str(row.get("player_name", "Teammate"))
            if name not in teammates:
                teammates[name] = {"actions": 0, "complete": 0, "under_pressure": 0}
            teammates[name]["actions"] += 1
            outcome = str(row.get("outcome", "")).lower()
            if row.get("type") == "Pass" and ("complete" in outcome or outcome == ""):
                teammates[name]["complete"] += 1
            if row.get("under_pressure"):
                teammates[name]["under_pressure"] += 1

        options = []
        for name, stats in sorted(teammates.items(), key=lambda x: -x[1]["actions"])[:4]:
            base = 0.55 + min(0.25, stats["actions"] * 0.03)
            if stats["actions"]:
                base += (stats["complete"] / stats["actions"]) * 0.15
            if stats["under_pressure"] > 2:
                base -= 0.1
            options.append({
                "target": name,
                "success_probability": round(max(0.15, min(0.95, base)), 2),
            })

        if not options:
            options = [
                {"target": "Nearest teammate", "success_probability": 0.72},
                {"target": "Hold possession", "success_probability": 0.58},
                {"target": "Switch play", "success_probability": 0.45},
            ]
        return options

    def _recent_player_actions(self, df: pd.DataFrame, player_id: int, minute: int) -> list[str]:
        pe = df[
            (df["player_id"] == player_id)
            & (df["minute"] >= max(0, minute - 5))
            & (df["minute"] <= minute)
        ].sort_values(["minute", "second"], ascending=False)
        actions = []
        for _, row in pe.head(6).iterrows():
            et = row.get("type", "Action")
            outcome = row.get("outcome")
            s = f"{row['minute']}' {et}"
            if outcome:
                s += f" ({outcome})"
            actions.append(s)
        return actions or ["No recent actions in event data"]

    def _describe_position(self, x: float, y: float, team: str, minute: int, score: str) -> str:
        if pd.isna(x):
            x = 60.0
        zone = "defensive third" if x < 40 else ("middle third" if x < 80 else "attacking third")
        return (
            f"At minute {minute} with the score {score}, operating in the {zone} "
            f"(approx. x={x:.0f}/120 on the pitch)."
        )

    def _describe_opponent_pressure(
        self, defenders: int, pressure: float, pressing: str
    ) -> str:
        return (
            f"{defenders} opponent(s) within pressing range. "
            f"Pressure index {pressure:.0f}/100 with {pressing} pressing intensity."
        )

    def _pressing_intensity(self, factor: float) -> str:
        if factor > 0.7:
            return "High"
        if factor > 0.4:
            return "Medium"
        return "Low"

    def _what_player_saw(
        self, defenders: int, options: list, pressure: float, score: str, momentum: float
    ) -> str:
        best = max(options, key=lambda o: o["success_probability"]) if options else None
        opt_text = f"Best outlet: {best['target']} ({best['success_probability']*100:.0f}%)" if best else "Limited options"
        return (
            f"Score {score}, team momentum {momentum:.0%}. {defenders} defenders nearby. "
            f"{opt_text}. Perceived pressure: {pressure:.0f}/100."
        )

    def _expected_decision(self, options: list, pressure: float) -> str:
        if pressure > 75:
            return "Clear the ball or safe pass under pressure"
        if options:
            return f"Pass to {options[0]['target']}"
        return "Maintain possession"
