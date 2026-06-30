#!/usr/bin/env python3
"""Precompute 2018 World Cup Final demo cache for fast first load."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import init_db, SessionLocal, DBEvent, DBMatch
from data.statsbomb_loader import StatsBombLoader
from engine.pressure_index import PressureIndexEngine
from engine.momentum import MomentumEngine
from engine.match_loader import MatchLoader
from engine.cache_manager import cache_manager, CACHE_DIR


async def main():
    init_db()
    db = SessionLocal()
    statsbomb = StatsBombLoader()
    pressure_engine = PressureIndexEngine(match_importance=1.0)
    momentum_engine = MomentumEngine()

    match = db.query(DBMatch).first()
    if not match:
        data = statsbomb.load_world_cup_final()
        info = data["match_info"]
        match = DBMatch(**info)
        db.add(match)
        db.commit()
        db.refresh(match)
        for e in data["events"]:
            e["match_id"] = match.id
            db.add(DBEvent(**e))
        db.commit()

    match_id = match.id
    events = db.query(DBEvent).filter(DBEvent.match_id == match_id).all()
    events_dicts = [e.__dict__ for e in events]
    events_df = statsbomb.get_events_dataframe(events_dicts)

    players = {}
    for e in events_dicts:
        if e.get("player_id") and e["player_id"] > 0:
            players[e["player_id"]] = {
                "id": e["player_id"],
                "name": e.get("player_name", "Unknown"),
                "team": e.get("team", ""),
                "position": "Unknown",
            }

    print("Computing momentum...")
    momentum = momentum_engine.compute_momentum_timeline(
        events_df, match.home_team, match.away_team, 95
    )

    print("Computing pressure...")
    pressure_raw = pressure_engine.compute_all_players(events_df, list(players.values()), 95)
    pressure = [
        {
            "player_id": pid,
            "player_name": players[pid]["name"],
            "team": players[pid]["team"],
            "position": players[pid]["position"],
            "timeline": pt_list,
        }
        for pid, pt_list in pressure_raw.items()
    ]

    bundle = {
        "match_id": match_id,
        "demo_mode": True,
        "pressure_timeline": pressure,
        "momentum_timeline": momentum,
    }

    out = cache_manager.save_match_bundle(match_id, bundle)
    alias = CACHE_DIR / "match_1.json"
    with open(alias, "w", encoding="utf-8") as f:
        json.dump(bundle, f, default=str)

    print(f"Demo cache written: {out} ({out.stat().st_size // 1024} KB)")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
