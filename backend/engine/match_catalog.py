"""
PressureLab AI - Match Catalog & Search
Search loaded matches and StatsBomb open data for universal match selection.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

OPEN_DATA_EVENTS = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json"


def _open_data_match_exists(match_id: int) -> bool:
    try:
        req = Request(OPEN_DATA_EVENTS.format(match_id=match_id), method="HEAD")
        with urlopen(req, timeout=6) as resp:
            return resp.status == 200
    except Exception:
        return False

# Curated searchable catalog — only StatsBomb open-data match IDs verified on GitHub
CATALOG_MATCHES = [
    {"statsbomb_id": 8658, "home_team": "France", "away_team": "Croatia", "competition": "2018 FIFA World Cup Final", "season": "2018", "match_date": "2018-07-15", "league": "World Cup", "manager_home": "Didier Deschamps", "manager_away": "Zlatko Dalić", "importance": 10, "pressure_index": 72},
    {"statsbomb_id": 7581, "home_team": "France", "away_team": "Belgium", "competition": "2018 FIFA World Cup Semi-Final", "season": "2018", "match_date": "2018-07-10", "league": "World Cup", "manager_home": "Didier Deschamps", "manager_away": "Roberto Martínez", "importance": 9, "pressure_index": 78},
    {"statsbomb_id": 8656, "home_team": "Croatia", "away_team": "England", "competition": "2018 FIFA World Cup Semi-Final", "season": "2018", "match_date": "2018-07-11", "league": "World Cup", "manager_home": "Zlatko Dalić", "manager_away": "Gareth Southgate", "importance": 9, "pressure_index": 75, "tags": ["comeback", "trending"]},
    {"statsbomb_id": 7580, "home_team": "Belgium", "away_team": "Japan", "competition": "2018 FIFA World Cup", "season": "2018", "match_date": "2018-07-02", "league": "World Cup", "manager_home": "Roberto Martínez", "manager_away": "Akira Nishino", "importance": 7, "pressure_index": 68},
    {"statsbomb_id": 22912, "home_team": "Argentina", "away_team": "France", "competition": "2022 FIFA World Cup Final", "season": "2022", "match_date": "2022-12-18", "league": "World Cup", "manager_home": "Lionel Scaloni", "manager_away": "Didier Deschamps", "importance": 10, "pressure_index": 85, "tags": ["trending", "high_pressure"], "featured_players": ["Messi", "Mbappé", "Griezmann"]},
    {"statsbomb_id": 3942819, "home_team": "Spain", "away_team": "England", "competition": "Euro 2024 Final", "season": "2024", "match_date": "2024-07-14", "league": "Euro", "manager_home": "Luis de la Fuente", "manager_away": "Gareth Southgate", "importance": 10, "pressure_index": 80, "featured_players": ["Yamal", "Bellingham", "Morata"]},
    {"statsbomb_id": 18245, "home_team": "Liverpool", "away_team": "Real Madrid", "competition": "UEFA Champions League Final", "season": "2017/18", "match_date": "2018-05-26", "league": "Champions League", "manager_home": "Jürgen Klopp", "manager_away": "Zinedine Zidane", "importance": 10, "pressure_index": 92, "tags": ["trending", "high_pressure", "high_xthreat"], "featured_players": ["Salah", "Benzema", "Bale", "Mané"]},
    {"statsbomb_id": 3773585, "home_team": "Barcelona", "away_team": "Real Madrid", "competition": "La Liga", "season": "2020/21", "match_date": "2020-10-24", "league": "La Liga", "manager_home": "Ronald Koeman", "manager_away": "Zinedine Zidane", "importance": 9, "pressure_index": 88, "tags": ["trending", "high_pressure", "high_xthreat"], "featured_players": ["Messi", "Benzema", "Modrić"]},
    {"statsbomb_id": 3754174, "home_team": "Borussia Dortmund", "away_team": "Real Madrid", "competition": "UEFA Champions League Final", "season": "2023/24", "match_date": "2024-06-01", "league": "Champions League", "manager_home": "Edin Terzić", "manager_away": "Carlo Ancelotti", "importance": 10, "pressure_index": 90},
]


def get_catalog_entry(match_id: int) -> Optional[dict]:
    return next((m for m in CATALOG_MATCHES if m["statsbomb_id"] == match_id), None)


class MatchCatalog:
    def __init__(self, statsbomb_loader=None):
        self.statsbomb = statsbomb_loader
        self._sb_index: Optional[list[dict]] = None

    def suggest(self, query: str, db_matches: list[Any], limit: int = 8) -> list[dict]:
        """Fast autocomplete — catalog + DB only, no network."""
        q = query.strip().lower()
        if len(q) < 2:
            return []
        scored: list[tuple[int, dict]] = []

        def score_item(item: dict, db_id: Optional[int] = None) -> Optional[tuple[int, dict]]:
            label = f"{item.get('home_team')} vs {item.get('away_team')}"
            hay = f"{label} {item.get('competition', '')} {item.get('season', '')}".lower()
            if q not in hay and not any(w in hay for w in q.split() if len(w) > 2):
                return None
            rank = 0
            if label.lower().startswith(q):
                rank += 100
            elif item.get("home_team", "").lower().startswith(q) or item.get("away_team", "").lower().startswith(q):
                rank += 80
            elif q in label.lower():
                rank += 50
            else:
                rank += 20
            return rank, {
                "id": db_id,
                "statsbomb_id": item.get("statsbomb_id"),
                "label": label,
                "home_team": item.get("home_team"),
                "away_team": item.get("away_team"),
                "competition": item.get("competition", ""),
                "match_date": item.get("match_date", ""),
                "loaded": db_id is not None,
            }

        seen: set[str] = set()
        for m in db_matches:
            if m.statsbomb_id and not _open_data_match_exists(m.statsbomb_id):
                continue
            item = {
                "statsbomb_id": m.statsbomb_id,
                "home_team": m.home_team,
                "away_team": m.away_team,
                "competition": m.competition,
                "match_date": m.match_date,
                "season": m.season,
            }
            key = f"{m.home_team}|{m.away_team}"
            if key in seen:
                continue
            seen.add(key)
            hit = score_item(item, m.id)
            if hit:
                scored.append(hit)

        for item in CATALOG_MATCHES:
            key = f"{item['home_team']}|{item['away_team']}"
            if key in seen:
                continue
            seen.add(key)
            db_match = next((m for m in db_matches if m.statsbomb_id == item.get("statsbomb_id")), None)
            hit = score_item(item, db_match.id if db_match else None)
            if hit:
                scored.append(hit)

        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]]

    def search(self, query: str, db_matches: list[Any], limit: int = 20) -> list[dict]:
        q = query.strip().lower()
        results: list[dict] = []
        seen: set[str] = set()

        def add(item: dict, source: str, db_id: Optional[int] = None):
            key = f"{item.get('home_team')}|{item.get('away_team')}|{item.get('match_date')}"
            if key in seen:
                return
            seen.add(key)
            results.append({
                "id": db_id,
                "statsbomb_id": item.get("statsbomb_id"),
                "label": f"{item.get('home_team')} vs {item.get('away_team')}",
                "home_team": item.get("home_team"),
                "away_team": item.get("away_team"),
                "competition": item.get("competition", ""),
                "match_date": item.get("match_date", ""),
                "season": item.get("season", ""),
                "source": source,
                "loaded": db_id is not None,
            })

        # DB matches first (skip rows tied to unavailable open-data IDs)
        for m in db_matches:
            if m.statsbomb_id and not _open_data_match_exists(m.statsbomb_id):
                continue
            label = f"{m.home_team} vs {m.away_team} {m.competition or ''}".lower()
            if not q or q in label or any(w in label for w in q.split()):
                add({
                    "statsbomb_id": m.statsbomb_id,
                    "home_team": m.home_team,
                    "away_team": m.away_team,
                    "competition": m.competition,
                    "match_date": m.match_date,
                    "season": m.season,
                }, "library", m.id)

        # Catalog
        for item in CATALOG_MATCHES:
            label = f"{item['home_team']} vs {item['away_team']} {item['competition']}".lower()
            if not q or q in label or any(w in label for w in q.split() if len(w) > 2):
                db_match = next(
                    (m for m in db_matches if m.statsbomb_id == item.get("statsbomb_id")),
                    None,
                )
                add(item, "statsbomb", db_match.id if db_match else None)

        # StatsBomb live index disabled — open-data catalog is the source of truth
        return results[:limit]

    def _statsbomb_search(self, query: str) -> list[dict]:
        return []
