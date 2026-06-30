"""
PressureLab AI - Historical Football Knowledge Base
Indexes StatsBomb Open Data matches for tactical similarity, momentum patterns,
and contextual retrieval. Continuously compares current matches against football history.
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

KB_CACHE = Path(__file__).resolve().parent.parent / "data" / "historical_kb.pkl"

SIGNATURE_KEYS = [
    "pass_ratio", "shot_ratio", "pressure_ratio", "carry_ratio", "tackle_ratio",
    "under_pressure_ratio", "pass_completion_rate", "possession_balance",
    "avg_field_position", "defensive_third_ratio",
]

# Curated historical reference matches (fallback when StatsBomb API unavailable)
REFERENCE_MATCHES = [
    {
        "id": "liverpool_barcelona_2019",
        "label": "Liverpool vs Barcelona 2019 (Champions League Semi-Final, 2nd Leg)",
        "competition": "UEFA Champions League 2018/19",
        "tactical_tags": ["gegenpress", "counter_attack", "high_intensity", "comeback"],
        "signature": {
            "pass_ratio": 0.32, "shot_ratio": 0.04, "pressure_ratio": 0.14,
            "carry_ratio": 0.18, "tackle_ratio": 0.05, "under_pressure_ratio": 0.38,
            "pass_completion_rate": 0.78, "possession_balance": 0.42,
            "avg_field_position": 0.58, "defensive_third_ratio": 0.22,
        },
        "narrative": "High-intensity counter-pressing comeback after trailing 3-0 from first leg.",
    },
    {
        "id": "germany_brazil_2014",
        "label": "Germany vs Brazil 2014 (World Cup Semi-Final)",
        "competition": "2014 FIFA World Cup",
        "tactical_tags": ["counter_press", "clinical_finishing", "transition", "high_line"],
        "signature": {
            "pass_ratio": 0.35, "shot_ratio": 0.06, "pressure_ratio": 0.11,
            "carry_ratio": 0.16, "tackle_ratio": 0.04, "under_pressure_ratio": 0.28,
            "pass_completion_rate": 0.85, "possession_balance": 0.55,
            "avg_field_position": 0.62, "defensive_third_ratio": 0.18,
        },
        "narrative": "Relentless counter-pressing and rapid transitions exploiting a high defensive line.",
    },
    {
        "id": "france_croatia_2018",
        "label": "France vs Croatia 2018 (World Cup Final)",
        "competition": "2018 FIFA World Cup",
        "tactical_tags": ["pragmatic", "counter_attack", "set_pieces", "low_block"],
        "signature": {
            "pass_ratio": 0.34, "shot_ratio": 0.05, "pressure_ratio": 0.12,
            "carry_ratio": 0.17, "tackle_ratio": 0.04, "under_pressure_ratio": 0.32,
            "pass_completion_rate": 0.80, "possession_balance": 0.48,
            "avg_field_position": 0.55, "defensive_third_ratio": 0.28,
        },
        "narrative": "Pragmatic counter-attacking with efficient set-piece execution under fatigue.",
    },
    {
        "id": "spain_netherlands_2010",
        "label": "Spain vs Netherlands 2010 (World Cup Final)",
        "competition": "2010 FIFA World Cup",
        "tactical_tags": ["possession", "tiki_taka", "pressing", "physicality"],
        "signature": {
            "pass_ratio": 0.42, "shot_ratio": 0.03, "pressure_ratio": 0.10,
            "carry_ratio": 0.14, "tackle_ratio": 0.06, "under_pressure_ratio": 0.35,
            "pass_completion_rate": 0.88, "possession_balance": 0.62,
            "avg_field_position": 0.58, "defensive_third_ratio": 0.25,
        },
        "narrative": "Possession-dominant tiki-taka against aggressive physical pressing.",
    },
    {
        "id": "leicester_2016",
        "label": "Leicester City Title Run 2015/16 (representative)",
        "competition": "Premier League 2015/16",
        "tactical_tags": ["counter_attack", "low_block", "direct", "pace"],
        "signature": {
            "pass_ratio": 0.28, "shot_ratio": 0.05, "pressure_ratio": 0.13,
            "carry_ratio": 0.20, "tackle_ratio": 0.06, "under_pressure_ratio": 0.25,
            "pass_completion_rate": 0.72, "possession_balance": 0.38,
            "avg_field_position": 0.48, "defensive_third_ratio": 0.35,
        },
        "narrative": "Compact low block with rapid direct transitions on the counter.",
    },
    {
        "id": "man_city_real_2022",
        "label": "Manchester City vs Real Madrid 2022 (Champions League Semi-Final)",
        "competition": "UEFA Champions League 2021/22",
        "tactical_tags": ["possession", "inverted_fullbacks", "high_press", "control"],
        "signature": {
            "pass_ratio": 0.40, "shot_ratio": 0.05, "pressure_ratio": 0.12,
            "carry_ratio": 0.15, "tackle_ratio": 0.04, "under_pressure_ratio": 0.30,
            "pass_completion_rate": 0.86, "possession_balance": 0.58,
            "avg_field_position": 0.60, "defensive_third_ratio": 0.20,
        },
        "narrative": "Positional dominance with inverted fullbacks and sustained territorial control.",
    },
]


class HistoricalKnowledgeBase:
    """Stores and retrieves historical match tactical signatures."""

    def __init__(self):
        self._entries: list[dict] = []
        self._embeddings: Optional[np.ndarray] = None
        self._loaded = False

    def initialize(self, match_loader=None, statsbomb_loader=None):
        """Build or load the knowledge base from cache and StatsBomb data."""
        if KB_CACHE.exists():
            try:
                with open(KB_CACHE, "rb") as f:
                    cached = pickle.load(f)
                self._entries = cached.get("entries", [])
                self._embeddings = cached.get("embeddings")
                self._loaded = True
                logger.info("Loaded historical KB with %d entries from cache", len(self._entries))
                return
            except Exception as e:
                logger.warning("Failed to load KB cache: %s", e)

        self._entries = list(REFERENCE_MATCHES)
        self._index_statsbomb_matches(statsbomb_loader, match_loader)
        self._build_embeddings()
        self._save_cache()
        self._loaded = True
        logger.info("Initialized historical KB with %d entries", len(self._entries))

    def add_match(self, match_id: int, label: str, competition: str, signature: dict, narrative: str = ""):
        """Add a processed match to the knowledge base."""
        entry = {
            "id": f"match_{match_id}",
            "label": label,
            "competition": competition,
            "tactical_tags": self._infer_tags(signature),
            "signature": signature,
            "narrative": narrative or f"Tactical profile from {label}",
        }
        self._entries.append(entry)
        self._build_embeddings()
        self._save_cache()

    def find_similar(
        self,
        signature: dict,
        top_k: int = 5,
        minute: Optional[int] = None,
        context: str = "",
        exclude_labels: Optional[list[str]] = None,
        moment_profile: Optional[dict] = None,
    ) -> list[dict]:
        """Return historically similar tactical situations with dynamic per-moment scores."""
        if not self._entries:
            return []

        from engine.tactical_similarity import build_moment_profile, rank_historical_matches

        if moment_profile:
            return rank_historical_matches(
                moment_profile, self._entries,
                exclude_labels=exclude_labels, top_k=top_k, minute=minute,
            )

        # Fallback: derive profile from match-level signature
        profile = {
            "pressure_index": min(1.0, signature.get("pressure_ratio", 0.12) * 4),
            "xthreat": min(1.0, signature.get("avg_field_position", 0.55) * 0.7),
            "xg": min(0.5, signature.get("shot_ratio", 0.05) * 3),
            "defensive_compactness": min(1.0, signature.get("defensive_third_ratio", 0.25) * 2.5),
            "formation": min(1.0, 0.5 + signature.get("possession_balance", 0.5) * 0.4),
            "passing_network": min(1.0, signature.get("pass_ratio", 0.35) * 2),
            "possession_pattern": signature.get("possession_balance", 0.5),
            "transition_speed": min(1.0, signature.get("carry_ratio", 0.15) * 3),
            "space_occupation": min(1.0, 1 - signature.get("defensive_third_ratio", 0.25)),
            "player_density": 0.72,
            "event_sequence": min(1.0, signature.get("pass_completion_rate", 0.8) * 0.6),
        }
        return rank_historical_matches(
            profile, self._entries,
            exclude_labels=exclude_labels, top_k=top_k, minute=minute,
        )

    def search_by_query(self, query: str, top_k: int = 3) -> list[dict]:
        """Keyword search over historical match narratives and tags."""
        keywords = set(query.lower().split())
        scored = []
        for entry in self._entries:
            text = (
                f"{entry['label']} {entry.get('competition', '')} "
                f"{entry.get('narrative', '')} {' '.join(entry.get('tactical_tags', []))}"
            ).lower()
            words = set(text.split())
            overlap = len(keywords & words)
            if overlap > 0:
                scored.append((overlap, entry))
        scored.sort(key=lambda x: -x[0])
        return [
            {
                "match": e["label"],
                "competition": e["competition"],
                "narrative": e.get("narrative", ""),
                "tactical_tags": e.get("tactical_tags", []),
            }
            for _, e in scored[:top_k]
        ]

    def get_all_entries(self) -> list[dict]:
        return [
            {"id": e["id"], "label": e["label"], "competition": e["competition"]}
            for e in self._entries
        ]

    def _index_statsbomb_matches(self, statsbomb_loader, match_loader):
        """Index additional matches from StatsBomb Open Data when available."""
        try:
            from statsbombpy import sb

            competitions = [
                (43, 3, "2018 FIFA World Cup"),
                (11, 1, "2014 FIFA World Cup"),
                (16, 1, "Champions League 2018/19"),
            ]
            indexed = 0
            for comp_id, season_id, comp_name in competitions:
                try:
                    matches = sb.matches(competition_id=comp_id, season_id=season_id)
                    for _, row in matches.head(8).iterrows():
                        mid = int(row["match_id"])
                        try:
                            events = sb.events(match_id=mid)
                            if match_loader:
                                sig = match_loader.build_tactical_signature(
                                    match_loader.statsbomb._process_events(events, mid)
                                    if hasattr(match_loader.statsbomb, "_process_events")
                                    else []
                                )
                            else:
                                sig = self._signature_from_dataframe(events)
                            if not sig:
                                continue
                            label = f"{row.get('home_team', '?')} vs {row.get('away_team', '?')}"
                            self._entries.append({
                                "id": f"sb_{mid}",
                                "label": label,
                                "competition": comp_name,
                                "tactical_tags": self._infer_tags(sig),
                                "signature": sig,
                                "narrative": f"StatsBomb indexed match from {comp_name}.",
                            })
                            indexed += 1
                        except Exception:
                            continue
                except Exception:
                    continue
            logger.info("Indexed %d StatsBomb matches into historical KB", indexed)
        except ImportError:
            logger.info("statsbombpy not available — using reference match library only")

    def _signature_from_dataframe(self, events) -> dict:
        import pandas as pd
        records = []
        for _, row in events.iterrows():
            records.append({
                "event_type": str(row.get("type", "")),
                "team": str(row.get("team", "")),
                "under_pressure": bool(row.get("under_pressure", False)),
                "location_x": row.get("location", [None, None])[0] if isinstance(row.get("location"), list) else None,
                "outcome": row.get("pass_outcome") or row.get("shot_outcome"),
            })
        from engine.match_loader import MatchLoader
        return MatchLoader().build_tactical_signature(records)

    def _signature_to_vector(self, sig: dict) -> np.ndarray:
        vec = np.array([sig.get(k, 0.0) for k in SIGNATURE_KEYS], dtype=np.float64)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def _build_embeddings(self):
        vectors = [self._signature_to_vector(e["signature"]) for e in self._entries]
        self._embeddings = np.array(vectors) if vectors else np.zeros((0, len(SIGNATURE_KEYS)))

    def _save_cache(self):
        KB_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(KB_CACHE, "wb") as f:
            pickle.dump({"entries": self._entries, "embeddings": self._embeddings}, f)

    def _infer_tags(self, sig: dict) -> list[str]:
        tags = []
        if sig.get("pressure_ratio", 0) > 0.12:
            tags.append("high_press")
        if sig.get("pass_ratio", 0) > 0.38:
            tags.append("possession")
        if sig.get("defensive_third_ratio", 0) > 0.30:
            tags.append("low_block")
        if sig.get("carry_ratio", 0) > 0.17:
            tags.append("direct_transitions")
        if sig.get("under_pressure_ratio", 0) > 0.35:
            tags.append("contested")
        if sig.get("possession_balance", 0.5) < 0.45:
            tags.append("counter_attack")
        return tags or ["balanced"]

    def _build_comparison_text(self, sim_pct: float, entry: dict, context: str, minute: Optional[int]) -> str:
        minute_str = f" at minute {minute}" if minute is not None else ""
        tags = ", ".join(entry.get("tactical_tags", []))
        return (
            f"This{minute_str} resembles {entry['label']} with {sim_pct:.0f}% tactical similarity. "
            f"Shared patterns: {tags}. {entry.get('narrative', '')}"
        )


historical_kb = HistoricalKnowledgeBase()
