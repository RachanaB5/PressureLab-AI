"""
Event-grounded tactical explanations — every AI output must reference the selected moment.
Deterministic fallbacks when Granite is unavailable; no generic football prose.
"""

from __future__ import annotations

from typing import Any, Optional


GENERIC_PHRASES = (
    "good attacking opportunity",
    "created space",
    "applied pressure",
    "tactical pressure",
    "player positioning",
    "game state dynamics",
    "interplay of",
    "could describe any",
    "analysis pending",
    "temporarily processing",
    "fallback",
    "unable to generate",
    "local granite fallback",
)


def _short(text: str, n: int = 140) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def is_generic_text(text: str) -> bool:
    if not text or len(text.strip()) < 12:
        return True
    lower = text.lower()
    return any(p in lower for p in GENERIC_PHRASES)


def build_tactical_snapshot(
    event: dict,
    pitch: Optional[dict] = None,
    match_state: Optional[dict] = None,
    replay_ctx: Optional[dict] = None,
    why: Optional[dict] = None,
    match_info: Optional[dict] = None,
) -> dict:
    """Structured facts for prompts and deterministic answers — unique per event."""
    pitch = pitch or {}
    match_state = match_state or {}
    replay_ctx = replay_ctx or {}
    why = why or {}
    match_info = match_info or {}

    ball = pitch.get("ball", {}) or {}
    bx = float(ball.get("x", event.get("location_x") or 60))
    by = float(ball.get("y", event.get("location_y") or 40))
    lanes = pitch.get("passing_lanes", []) or []
    players = pitch.get("players", []) or []
    active = next((p for p in players if p.get("is_active")), None)
    pressers = [p for p in players if p.get("team") == "away" and (p.get("pressure") or 0) > 55]

    home = match_state.get("home_team") or match_info.get("home_team", "Home")
    away = match_state.get("away_team") or match_info.get("away_team", "Away")
    score = match_state.get("score") or (
        f"{match_state.get('home_score', match_info.get('home_score', 0))}-"
        f"{match_state.get('away_score', match_info.get('away_score', 0))}"
    )

    minute = int(event.get("minute", match_state.get("minute", 0)))
    player = event.get("player_name", "Player")
    team = event.get("team", "")
    et = str(event.get("event_type", "Event"))
    outcome = event.get("outcome") or "N/A"
    pressure_idx = round(float(replay_ctx.get("pressure_index", 50)), 0)

    best_lane = None
    if lanes:
        best_lane = max(lanes, key=lambda l: (1 if l.get("success") else 0, l.get("to", [0])[0]))

    defensive_line = pitch.get("defensive_lines", {}) or {}
    away_line = defensive_line.get("away")
    home_shape = (pitch.get("team_shape") or {}).get("home", {})

    return {
        "event_id": event.get("id"),
        "minute": minute,
        "player": player,
        "team": team,
        "event_type": et,
        "outcome": outcome,
        "score": score,
        "home_team": home,
        "away_team": away,
        "ball_x": round(bx, 1),
        "ball_y": round(by, 1),
        "pressure_index": pressure_idx,
        "under_pressure": bool(event.get("under_pressure")),
        "passing_lanes_count": len(lanes),
        "best_pass_target": best_lane.get("to") if best_lane else None,
        "active_player": active.get("name") if active else player,
        "pressers_nearby": len(pressers),
        "space_exploited": why.get("space_exploited") or _space_label(bx, by),
        "tactical_pattern": why.get("tactical_pattern", ""),
        "defender_reaction": why.get("defender_reaction") or replay_ctx.get("situation", {}).get("opponent_pressure", ""),
        "attacker_view": why.get("attacker_choice") or replay_ctx.get("situation", {}).get("what_player_likely_saw", ""),
        "momentum_home": (match_state.get("momentum") or {}).get("home"),
        "momentum_away": (match_state.get("momentum") or {}).get("away"),
        "possession_home": (match_state.get("possession") or {}).get("home"),
        "away_defensive_line": away_line,
        "home_compactness": home_shape.get("compactness"),
        "recent_actions": replay_ctx.get("recent_actions", [])[:5],
    }


def _space_label(bx: float, by: float) -> str:
    if bx > 102 and by < 30:
        return "far-post channel at x={:.0f}, y={:.0f}".format(bx, by)
    if bx > 102 and by > 50:
        return "near-post cut-back zone at x={:.0f}, y={:.0f}".format(bx, by)
    if 80 < bx <= 102:
        return "half-space between lines at x={:.0f}, y={:.0f}".format(bx, by)
    return "central corridor at x={:.0f}, y={:.0f}".format(bx, by)


def format_snapshot_for_prompt(snapshot: dict) -> str:
    lines = [
        f"SELECTED EVENT: {snapshot['event_type']} by {snapshot['player']} ({snapshot['team']}) at {snapshot['minute']}'",
        f"SCORE: {snapshot['home_team']} {snapshot['score']} {snapshot['away_team']}",
        f"BALL: x={snapshot['ball_x']}, y={snapshot['ball_y']}",
        f"OUTCOME: {snapshot['outcome']} | Under pressure: {snapshot['under_pressure']}",
        f"PRESSURE INDEX: {snapshot['pressure_index']}/100 | Pressers nearby: {snapshot['pressers_nearby']}",
        f"PASSING LANES: {snapshot['passing_lanes_count']}",
    ]
    if snapshot.get("best_pass_target"):
        t = snapshot["best_pass_target"]
        lines.append(f"BEST LANE TARGET: ({t[0]:.0f}, {t[1]:.0f})")
    if snapshot.get("space_exploited"):
        lines.append(f"SPACE: {snapshot['space_exploited']}")
    if snapshot.get("tactical_pattern"):
        lines.append(f"PATTERN: {snapshot['tactical_pattern']}")
    if snapshot.get("momentum_home") is not None:
        lines.append(f"MOMENTUM: {snapshot['home_team']} {snapshot['momentum_home']}% / {snapshot['away_team']} {snapshot['momentum_away']}%")
    if snapshot.get("recent_actions"):
        lines.append("RECENT: " + "; ".join(str(a) for a in snapshot["recent_actions"][:4]))
    return "\n".join(lines)


def build_grounded_bullets(snapshot: dict) -> list[dict]:
    """4–6 bullets — deterministic, event-unique."""
    s = snapshot
    lane_txt = "no open lane"
    if s.get("best_pass_target"):
        t = s["best_pass_target"]
        lane_txt = f"pass to ({t[0]:.0f}, {t[1]:.0f})"

    mistake = s.get("defender_reaction") or (
        f"{s['pressers_nearby']} away pressers allowed {s['player']} to receive at x={s['ball_x']}"
        if s["pressers_nearby"] < 2
        else f"Away line at x≈{s.get('away_defensive_line', 75)} left {s['space_exploited']}"
    )

    bullets = [
        {
            "key": "why",
            "label": "Why this happened",
            "text": _short(
                f"At {s['minute']}' ({s['score']}), {s['player']}'s {s['event_type']} at ball "
                f"(x={s['ball_x']}, y={s['ball_y']}) under {s['pressure_index']}/100 pressure "
                f"exploited {s['space_exploited']}.",
                160,
            ),
        },
        {
            "key": "mistake",
            "label": "Biggest tactical mistake",
            "text": _short(mistake, 140),
        },
        {
            "key": "pass",
            "label": "Best alternative",
            "text": _short(
                f"With {s['passing_lanes_count']} lanes visible, best option was {lane_txt} "
                f"before {s['event_type'].lower()} at {s['minute']}'.",
                140,
            ),
        },
        {
            "key": "space",
            "label": "Most important space",
            "text": _short(s["space_exploited"], 120),
        },
        {
            "key": "player",
            "label": "Key player",
            "text": _short(f"{s['player']} ({s['team']}) — on-ball at x={s['ball_x']}, y={s['ball_y']}", 100),
        },
        {
            "key": "takeaway",
            "label": "Tactical takeaway",
            "text": _short(
                s.get("tactical_pattern")
                or f"At {s['minute']}' the {s['event_type'].lower()} shifted threat to {s['space_exploited']}.",
                140,
            ),
        },
    ]
    return [b for b in bullets if b.get("text")][:6]


def build_grounded_explanation(snapshot: dict) -> dict:
    bullets = build_grounded_bullets(snapshot)
    bullet_text = "\n".join(f"• {b['text']}" for b in bullets)
    return {
        "summary": bullets[0]["text"] if bullets else f"{snapshot['player']} at {snapshot['minute']}'",
        "reasoning": bullet_text,
        "explanation": bullet_text,
        "answer": bullet_text,
        "headline": bullets[0]["text"] if bullets else "",
        "tactical_pattern": snapshot.get("tactical_pattern") or bullets[-1]["text"],
        "defender_reaction": bullets[1]["text"] if len(bullets) > 1 else "",
        "attacker_choice": bullets[2]["text"] if len(bullets) > 2 else "",
        "space_exploited": snapshot.get("space_exploited", ""),
        "evidence": [
            f"{snapshot['minute']}' {snapshot['event_type']} — {snapshot['player']} ({snapshot['team']})",
            f"Score {snapshot['score']} | Ball ({snapshot['ball_x']}, {snapshot['ball_y']})",
            f"Pressure {snapshot['pressure_index']}/100 | {snapshot['passing_lanes_count']} passing lanes",
        ],
        "alternatives": [bullets[2]["text"]] if len(bullets) > 2 else [],
        "confidence": 0.82,
        "bullets": bullets,
        "generated_by": "PressureLab Event Engine",
    }


def build_grounded_copilot_answer(question: str, snapshot: dict) -> dict:
    base = build_grounded_explanation(snapshot)
    q = question.lower()
    lead = bullets_lead_for_question(q, snapshot)
    answer = "\n".join(f"• {b['text']}" for b in lead)
    return {
        **base,
        "answer": answer,
        "why_now": f"This applies at {snapshot['minute']}' with score {snapshot['score']}.",
        "what_if": lead[2]["text"] if len(lead) > 2 else base["alternatives"][0] if base["alternatives"] else "",
        "what_next": f"Track {snapshot['player']} and lanes from ball ({snapshot['ball_x']}, {snapshot['ball_y']}).",
    }


def bullets_lead_for_question(question: str, snapshot: dict) -> list[dict]:
    all_b = build_grounded_bullets(snapshot)
    if "mistake" in question or "defend" in question:
        return [all_b[1], all_b[0], all_b[5]] if len(all_b) > 5 else all_b[:3]
    if "pass" in question or "lane" in question:
        return [all_b[2], all_b[3], all_b[0]] if len(all_b) > 2 else all_b[:3]
    if "pep" in question or "guardiola" in question:
        return [_coach_bullet("pep", snapshot)] + all_b[:2]
    if "klopp" in question:
        return [_coach_bullet("klopp", snapshot)] + all_b[:2]
    return all_b[:5]


def coach_pick(snapshot: dict, coach_id: str) -> str:
    bx = snapshot["ball_x"]
    lanes = snapshot["passing_lanes_count"]
    pressure = snapshot["pressure_index"]
    score_parts = str(snapshot["score"]).split("-")
    try:
        gd = int(score_parts[0]) - int(score_parts[1])
    except (ValueError, IndexError):
        gd = 0

    if coach_id == "pep":
        return "switch" if lanes < 2 and bx < 80 else "pass" if bx > 78 else "carry"
    if coach_id == "klopp":
        return "press" if pressure < 65 and bx < 75 else "carry" if bx < 90 else "shot"
    if coach_id == "ancelotti":
        return "hold_shape" if gd > 0 and snapshot["minute"] > 70 else "pass" if lanes >= 2 else "carry"
    if coach_id == "mourinho":
        return "hold_shape" if bx < 95 else "switch"
    if coach_id == "granite":
        opts = ["pass", "shot", "carry", "switch"]
        scores = {
            "pass": bx / 120 * 0.4 + lanes * 0.08,
            "shot": max(0, (bx - 95) / 25) * 0.5,
            "carry": 0.25 if 70 < bx < 95 else 0.1,
            "switch": 0.2 if lanes < 3 else 0.05,
        }
        return max(opts, key=lambda k: scores[k])
    return "pass"


def coach_reason(coach_id: str, snapshot: dict, action_id: str) -> str:
    s = snapshot
    names = {
        "pep": "Pep Guardiola",
        "klopp": "Jürgen Klopp",
        "ancelotti": "Carlo Ancelotti",
        "mourinho": "José Mourinho",
        "granite": "IBM Granite",
    }
    name = names.get(coach_id, coach_id)
    if coach_id == "pep":
        return (
            f"{name}: at {s['minute']}' ({s['score']}), {s['player']} on ball x={s['ball_x']} — "
            f"{'switch to reset the press' if action_id == 'switch' else 'third-man pass'} "
            f"using {s['passing_lanes_count']} lanes into {s['space_exploited']}."
        )
    if coach_id == "klopp":
        return (
            f"{name}: {s['pressers_nearby']} pressers at {s['pressure_index']}/100 — "
            f"{'trigger gegenpress now' if action_id == 'press' else 'carry to draw another defender'} "
            f"before {s['away_team']} recover shape at minute {s['minute']}."
        )
    if coach_id == "ancelotti":
        return (
            f"{name}: score {s['score']} at {s['minute']}' — "
            f"{'manage tempo, hold shape' if action_id == 'hold_shape' else 'progress via ' + s['space_exploited']} "
            f"with {s['player']} at x={s['ball_x']}."
        )
    if coach_id == "mourinho":
        return (
            f"{name}: deny {s['space_exploited']} — "
            f"{'compact block, no engagement' if action_id == 'hold_shape' else 'force wide via switch'} "
            f"with ball at ({s['ball_x']}, {s['ball_y']})."
        )
    return (
        f"{name}: {action_id} at {s['minute']}' — ball ({s['ball_x']}, {s['ball_y']}), "
        f"pressure {s['pressure_index']}/100, {s['passing_lanes_count']} lanes."
    )


def _coach_bullet(coach_id: str, snapshot: dict) -> dict:
    pick = coach_pick(snapshot, coach_id)
    return {
        "key": coach_id,
        "label": coach_id.title(),
        "text": _short(coach_reason(coach_id, snapshot, pick), 160),
    }


def merge_granite_with_grounding(granite: dict, snapshot: dict) -> dict:
    """Prefer Granite when specific; replace generic fields with grounded facts."""
    grounded = build_grounded_explanation(snapshot)
    out = {**grounded, **granite}
    for key in ("reasoning", "explanation", "answer", "summary", "headline"):
        val = granite.get(key, "")
        if is_generic_text(str(val)):
            out[key] = grounded.get(key, val)
    if is_generic_text(str(granite.get("historical_context", ""))):
        out["historical_context"] = ""
    out["bullets"] = grounded["bullets"]
    out["generated_by"] = granite.get("generated_by", "IBM Granite")
    return out
