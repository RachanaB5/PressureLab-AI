"""
PressureLab AI - Disk + memory cache for demo-fast responses.
Precomputed demo data loads instantly; uploads cache after first compute.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "demo_cache"
DEMO_MATCH_KEY = "match_1"


class CacheManager:
    """Persist and retrieve match analysis bundles and feature-level caches."""

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, Any] = {}

    @staticmethod
    def feature_key(feature: str, match_id: int, **parts) -> str:
        raw = f"{feature}:{match_id}:" + ":".join(f"{k}={parts[k]}" for k in sorted(parts))
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get(self, key: str) -> Optional[Any]:
        if key in self._memory:
            return self._memory[key]
        path = CACHE_DIR / f"{key}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._memory[key] = data
            return data
        return None

    def set(self, key: str, data: Any) -> None:
        self._memory[key] = data
        path = CACHE_DIR / f"{key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)

    def save_match_bundle(self, match_id: int, bundle: dict) -> Path:
        path = CACHE_DIR / f"match_{match_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, default=str)
        logger.info("Saved match cache bundle for match %s → %s", match_id, path)
        return path

    def load_match_bundle(self, match_id: int) -> Optional[dict]:
        path = CACHE_DIR / f"match_{match_id}.json"
        if not path.exists() and match_id == 1:
            path = CACHE_DIR / f"{DEMO_MATCH_KEY}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def has_match_bundle(self, match_id: int) -> bool:
        return (
            (CACHE_DIR / f"match_{match_id}.json").exists()
            or (match_id == 1 and (CACHE_DIR / f"{DEMO_MATCH_KEY}.json").exists())
        )


cache_manager = CacheManager()
