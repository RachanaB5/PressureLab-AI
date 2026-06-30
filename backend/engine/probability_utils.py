"""Normalize match outcome probabilities for API + LLM prompts."""

from __future__ import annotations


def _to_percent(value: float) -> float:
    v = float(value or 0)
    if 0 <= v <= 1.0:
        return v * 100.0
    return v


def normalize_outcome_probs(home_win: float, draw: float, away_win: float) -> dict[str, float]:
    """Return home/draw/away on 0–100 scale summing to ~100."""
    h = max(0.0, _to_percent(home_win))
    d = max(0.0, _to_percent(draw))
    a = max(0.0, _to_percent(away_win))
    total = h + d + a
    if total <= 0:
        return {"home_win": 33.3, "draw": 33.3, "away_win": 33.4}
    h, d, a = (h / total) * 100, (d / total) * 100, (a / total) * 100
    return {
        "home_win": round(h, 1),
        "draw": round(d, 1),
        "away_win": round(a, 1),
    }


def normalize_prediction_payload(payload: dict) -> dict:
    """Normalize base/counterfactual blocks in counterfactual API responses."""
    out = dict(payload)
    for key in ("base", "counterfactual"):
        block = out.get(key)
        if isinstance(block, dict):
            normed = normalize_outcome_probs(
                block.get("home_win", 0),
                block.get("draw", 0),
                block.get("away_win", 0),
            )
            out[key] = {**block, **normed}
    if "deltas" in out and isinstance(out["deltas"], dict):
        out["deltas"] = {
            k: round(float(v), 1) for k, v in out["deltas"].items()
        }
    return out
