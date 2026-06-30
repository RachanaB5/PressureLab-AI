"""
PressureLab AI - Main FastAPI Application
Entry point for the backend server.
Initializes ML models and database at startup.
"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import json
import asyncio
import zlib
from typing import Any, Optional
from pydantic import BaseModel

from config import settings
from db.database import init_db, get_db, SessionLocal, DBEvent, DBMatch, Session
from data.statsbomb_loader import StatsBombLoader
from engine.pressure_index import PressureIndexEngine
from engine.momentum import MomentumEngine
from engine.psychology import PsychologyEngine
from engine.match_loader import MatchLoader
from engine.replay_engine import ReplayEngine
from engine.cache_manager import cache_manager
from engine.moment_workspace import MomentWorkspaceEngine
from engine.match_catalog import MatchCatalog
from engine.pitch_state_engine import coord_coverage, merge_fresh_coordinates

from ai.providers import create_llm_provider
from ai.granite_client import GraniteClient
from ai.context_forge import ContextForgeClient
from ai.langflow_client import LangflowClient
from ai.docling_processor import DoclingProcessor

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- App State & Lifespan ---

class AppState:
    """Holds global instances initialized at startup."""
    def __init__(self):
        self.statsbomb: StatsBombLoader = None
        self.pressure_engine: PressureIndexEngine = None
        self.momentum_engine: MomentumEngine = None
        self.psychology_engine: PsychologyEngine = None
        self.granite: GraniteClient = None
        self.context_forge: ContextForgeClient = None
        self.langflow: LangflowClient = None
        self.docling: DoclingProcessor = None
        self.match_loader: MatchLoader = None
        self.replay_engine: ReplayEngine = None
        self.moment_workspace: MomentWorkspaceEngine = None
        self.match_catalog: MatchCatalog = None

        self.pressure_timeline_cache = {}
        self.momentum_timeline_cache = {}
        self.moment_cache: dict[str, dict] = {}
        self.enriched_events_cache: dict[int, list[dict]] = {}
        self.analysis_status: dict[int, str] = {}
        self.analysis_stages: dict[int, dict] = {}
        self.demo_match_ids: set[int] = set()

state = AppState()


class MatchConnectionManager:
    """Small in-process WebSocket manager for analysis progress updates."""

    def __init__(self):
        self._connections: dict[int, set[WebSocket]] = {}

    async def connect(self, match_id: int, websocket: WebSocket):
        await websocket.accept()
        self._connections.setdefault(match_id, set()).add(websocket)

    def disconnect(self, match_id: int, websocket: WebSocket):
        conns = self._connections.get(match_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._connections.pop(match_id, None)

    async def send_to_match(self, match_id: int, message: dict):
        conns = list(self._connections.get(match_id, set()))
        if not conns:
            return
        stale: list[WebSocket] = []
        for websocket in conns:
            try:
                await websocket.send_json({"match_id": match_id, **message})
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(match_id, websocket)


ws_manager = MatchConnectionManager()


def _status_payload(match_id: int) -> dict:
    ready = match_id in state.pressure_timeline_cache
    stage_info = state.analysis_stages.get(match_id, {})
    return {
        "type": "analysis_update",
        "status": "ready" if ready else state.analysis_status.get(match_id, "unknown"),
        "timelines_ready": ready,
        "stage": stage_info.get("stage", 5 if ready else 1),
        "stage_label": stage_info.get("label", "Complete" if ready else "Preparing analysis"),
        "progress": stage_info.get("progress", 100 if ready else 0),
        "pressure": match_id in state.pressure_timeline_cache,
        "momentum": match_id in state.momentum_timeline_cache,
    }


async def _broadcast_status(match_id: int) -> None:
    await ws_manager.send_to_match(match_id, _status_payload(match_id))


def _apply_match_bundle(match_id: int, bundle: dict) -> None:
    """Hydrate in-memory caches from a precomputed disk bundle."""
    if bundle.get("pressure_timeline"):
        state.pressure_timeline_cache[match_id] = bundle["pressure_timeline"]
    if bundle.get("momentum_timeline"):
        state.momentum_timeline_cache[match_id] = bundle["momentum_timeline"]
    state.analysis_status[match_id] = "ready"
    state.analysis_stages[match_id] = {
        "stage": 5,
        "label": "Complete",
        "progress": 100,
        "demo_mode": bundle.get("demo_mode", False),
    }
    if bundle.get("demo_mode"):
        state.demo_match_ids.add(match_id)


def _load_demo_cache(match_id: int) -> bool:
    bundle = cache_manager.load_match_bundle(match_id)
    if not bundle:
        return False
    _apply_match_bundle(match_id, bundle)
    logger.info("Loaded precomputed demo cache for match %s", match_id)
    return True


async def precompute_timelines_task(match_id: int, demo_mode: bool = False):
    """Background precompute with its own DB session."""
    db = SessionLocal()
    try:
        await precompute_timelines(db, match_id, demo_mode=demo_mode)
    finally:
        db.close()

async def seed_data(db: Session):
    """Seed the database with the 2018 World Cup Final if empty."""
    match = db.query(DBMatch).first()
    if match:
        logger.info("Database already seeded.")
        return match.id

    logger.info("Seeding database with 2018 World Cup Final data...")
    data = state.statsbomb.load_world_cup_final()
    
    # Save Match
    info = data['match_info']
    db_match = DBMatch(**info)
    db.add(db_match)
    db.commit()
    db.refresh(db_match)
    
    # Save Events in chunks
    events = data['events']
    chunk_size = 500
    for i in range(0, len(events), chunk_size):
        chunk = events[i:i + chunk_size]
        for e in chunk:
            e['match_id'] = db_match.id
        db_events = [DBEvent(**e) for e in chunk]
        db.add_all(db_events)
        db.commit()
        
    logger.info(f"Seeded {len(events)} events for match {db_match.id}")
    return db_match.id

async def precompute_timelines(db: Session, match_id: int, demo_mode: bool = False):
    """Precompute pressure, momentum, and predictions for fast API responses."""
    state.analysis_status[match_id] = "processing"
    state.analysis_stages[match_id] = {"stage": 1, "label": "Parsing match", "progress": 10}
    await _broadcast_status(match_id)
    logger.info(f"Precomputing timelines for match {match_id}...")
    
    try:
        # Load events into DataFrame
        events = db.query(DBEvent).filter(DBEvent.match_id == match_id).all()
        events_dicts = [e.__dict__ for e in events]
        events_df = state.statsbomb.get_events_dataframe(events_dicts)
        
        match = db.query(DBMatch).filter(DBMatch.id == match_id).first()
        match_info = match.__dict__
        
        # Initialize Context Forge
        if state.context_forge:
            state.context_forge.initialize_from_events(events_df, match_info)
        
        # Extract unique players
        players = {}
        for e in events_dicts:
            if e.get('player_id') and e['player_id'] > 0:
                players[e['player_id']] = {
                    'id': e['player_id'],
                    'name': e.get('player_name', 'Unknown'),
                    'team': e.get('team', ''),
                    'position': 'Unknown'
                }
        player_list = list(players.values())
        
        state.analysis_stages[match_id] = {"stage": 2, "label": "Generating pressure", "progress": 35}
        await _broadcast_status(match_id)

        # 1. Momentum Timeline
        logger.info("Computing momentum timeline...")
        momentum = state.momentum_engine.compute_momentum_timeline(
            events_df, match.home_team, match.away_team, 95
        )
        state.momentum_timeline_cache[match_id] = momentum
        state.analysis_stages[match_id] = {"stage": 2, "label": "Generating pressure", "progress": 50}
        await _broadcast_status(match_id)
        
        # 2. Pressure Timeline
        logger.info("Computing pressure timeline for all players...")
        pressure = state.pressure_engine.compute_all_players(events_df, player_list, 95)
        
        formatted_pressure = []
        for pid, pt_list in pressure.items():
            p_info = players[pid]
            formatted_pressure.append({
                'player_id': pid,
                'player_name': p_info['name'],
                'team': p_info['team'],
                'position': p_info['position'],
                'timeline': pt_list
            })
        state.pressure_timeline_cache[match_id] = formatted_pressure
        state.analysis_stages[match_id] = {"stage": 4, "label": "Finalizing", "progress": 90}
        await _broadcast_status(match_id)

        cache_manager.save_match_bundle(match_id, {
            "match_id": match_id,
            "demo_mode": demo_mode,
            "pressure_timeline": formatted_pressure,
            "momentum_timeline": momentum,
        })
        
        state.analysis_status[match_id] = "ready"
        state.analysis_stages[match_id] = {"stage": 5, "label": "Complete", "progress": 100}
        await _broadcast_status(match_id)
        logger.info("Precomputation complete for match %s", match_id)
    except Exception as e:
        state.analysis_status[match_id] = "error"
        state.analysis_stages[match_id] = {"stage": 0, "label": "Analysis failed", "progress": 0}
        await _broadcast_status(match_id)
        logger.error("Precomputation failed for match %s: %s", match_id, e)
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup — yield fast so API is reachable immediately."""
    init_db()

    state.statsbomb = StatsBombLoader()
    state.match_loader = MatchLoader(statsbomb_loader=state.statsbomb)
    state.replay_engine = ReplayEngine()
    state.moment_workspace = MomentWorkspaceEngine()
    state.match_catalog = MatchCatalog(statsbomb_loader=state.statsbomb)
    state.pressure_engine = PressureIndexEngine(match_importance=1.0)
    state.momentum_engine = MomentumEngine()
    state.psychology_engine = PsychologyEngine()
    state.context_forge = ContextForgeClient()
    state.docling = DoclingProcessor()
    state.granite = None
    state.langflow = None

    async def _heavy_startup():
        try:
            try:
                provider = create_llm_provider(
                    provider_type=settings.llm_provider,
                    hf_api_key=settings.hf_api_key,
                    granite_model_id=settings.granite_model_id,
                    watsonx_api_key=settings.watsonx_api_key,
                    watsonx_project_id=settings.watsonx_project_id,
                    watsonx_url=settings.watsonx_url,
                )
                state.granite = GraniteClient(provider)
                state.langflow = LangflowClient(
                    granite_client=state.granite,
                    context_forge=state.context_forge,
                    docling_processor=state.docling,
                )
                logger.info("Initialized Granite client with %s", settings.llm_provider)
            except Exception as e:
                logger.error("Failed to initialize Granite client: %s", e)

            state.docling.get_match_knowledge_base()

            db = SessionLocal()
            try:
                match_id = await seed_data(db)
                if _load_demo_cache(match_id):
                    state.demo_match_ids.add(match_id)
                else:
                    await precompute_timelines(db, match_id, demo_mode=True)
            finally:
                db.close()
        except Exception as e:
            logger.error("Background startup failed: %s", e)

    asyncio.create_task(_heavy_startup())
    logger.info("PressureLab API ready — heavy init running in background")
    yield
    logger.info("Shutting down PressureLab AI...")

# --- App Definition ---

app = FastAPI(
    title=settings.app_name,
    description="Explainable AI platform for football tactical and psychological analysis.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _events_from_db(db: Session, match_id: int) -> list[dict]:
    events = db.query(DBEvent).filter(DBEvent.match_id == match_id).order_by(DBEvent.minute, DBEvent.second, DBEvent.id).all()
    return [
        {"id": e.id, **{k: getattr(e, k) for k in (
            "event_type", "minute", "second", "player_name", "player_id", "team",
            "outcome", "under_pressure", "location_x", "location_y", "details",
        )}}
        for e in events
    ]


def _get_enriched_events(db: Session, match_id: int, match: DBMatch) -> list[dict]:
    """Return match events with coordinates backfilled from StatsBomb when DB is sparse."""
    if match_id in state.enriched_events_cache:
        return state.enriched_events_cache[match_id]

    events_dicts = _events_from_db(db, match_id)
    if match.statsbomb_id and coord_coverage(events_dicts) < 0.35:
        try:
            fresh = state.statsbomb.load_match_by_statsbomb_id(int(match.statsbomb_id))
            merged = merge_fresh_coordinates(events_dicts, fresh.get("events", []))
            events_dicts = merged
            logger.info(
                "Backfilled coordinates for match %s (coverage %.0f%%)",
                match_id, coord_coverage(events_dicts) * 100,
            )
        except Exception as exc:
            logger.warning("Coordinate backfill failed for match %s: %s", match_id, exc)

    state.enriched_events_cache[match_id] = events_dicts
    return events_dicts


def _event_value(event: Any, key: str, default: Any = None) -> Any:
    if isinstance(event, dict):
        return event.get(key, default)
    return getattr(event, key, default)


def _goal_team(event: Any, home_team: str, away_team: str) -> Optional[str]:
    event_type = str(_event_value(event, "event_type", "")).lower()
    outcome = str(_event_value(event, "outcome", "") or "").lower()
    team = _event_value(event, "team", "")
    if "own goal against" in event_type:
        if team == home_team:
            return away_team
        if team == away_team:
            return home_team
        return None
    if "own goal for" in event_type:
        return team
    if event_type == "goal" or ("shot" in event_type and "goal" in outcome):
        return team
    return None


def _score_from_events(events: list[Any], home_team: str, away_team: str, minute: Optional[int] = None) -> tuple[int, int]:
    home_goals = 0
    away_goals = 0
    for event in events:
        if minute is not None and (_event_value(event, "minute", 0) or 0) > minute:
            continue
        scorer = _goal_team(event, home_team, away_team)
        if scorer == home_team:
            home_goals += 1
        elif scorer == away_team:
            away_goals += 1
    return home_goals, away_goals


def _unique_statsbomb_id(db: Session, info: dict) -> int:
    raw_id = info.get("statsbomb_id")
    if raw_id:
        try:
            candidate = int(raw_id)
        except (TypeError, ValueError):
            candidate = zlib.crc32(str(raw_id).encode("utf-8")) % (10 ** 9)
    else:
        seed = f"{info.get('home_team', 'Home')}|{info.get('away_team', 'Away')}|{info.get('match_date', '')}|{info.get('competition', '')}"
        candidate = zlib.crc32(seed.encode("utf-8")) % (10 ** 9)

    while db.query(DBMatch).filter(DBMatch.statsbomb_id == candidate).first():
        candidate = (candidate + 1) % (10 ** 9)
    return candidate


def _store_parsed_match(parsed: dict, db: Session) -> DBMatch:
    """Persist parsed match events and return the DB match row."""
    info = parsed["match_info"]
    db_match = DBMatch(**{k: v for k, v in info.items() if k != "id" and hasattr(DBMatch, k)})
    db_match.statsbomb_id = _unique_statsbomb_id(db, info)
    db.add(db_match)
    db.commit()
    db.refresh(db_match)

    events = parsed["events"]
    chunk_size = 500
    for i in range(0, len(events), chunk_size):
        chunk = events[i:i + chunk_size]
        db_events = []
        for e in chunk:
            e = {**e, "match_id": db_match.id}
            e.pop("id", None)
            db_events.append(DBEvent(**{k: v for k, v in e.items() if hasattr(DBEvent, k)}))
        db.add_all(db_events)
        db.commit()

    parsed["match_info"]["id"] = db_match.id
    if "digital_match_twin" in parsed:
        parsed["digital_match_twin"]["match_info"] = parsed["match_info"]

    # Reconcile final score from stored events (handles Shot/Goal outcomes).
    if state.match_loader:
        scored = [
            {"event_type": e.event_type, "outcome": e.outcome, "team": e.team}
            for e in db.query(DBEvent).filter(DBEvent.match_id == db_match.id).all()
        ]
        home_score, away_score = state.match_loader._compute_score(
            scored, db_match.home_team, db_match.away_team,
        )
        if home_score or away_score:
            db_match.home_score = int(home_score)
            db_match.away_score = int(away_score)
            db.commit()
            db.refresh(db_match)
            parsed["match_info"]["home_score"] = db_match.home_score
            parsed["match_info"]["away_score"] = db_match.away_score

    state.match_loader.save_processed(db_match.id, parsed)
    return db_match


# --- Routes ---


@app.get("/api/matches/suggest")
async def suggest_matches(q: str = "", db: Session = Depends(get_db)):
    """Fast autocomplete suggestions — no external API calls."""
    if not state.match_catalog:
        return {"query": q, "suggestions": []}
    db_matches = db.query(DBMatch).all()
    return {"query": q, "suggestions": state.match_catalog.suggest(q, db_matches)}


class ImportMatchReq(BaseModel):
    statsbomb_id: Optional[int] = None
    match_id: Optional[int] = None


@app.post("/api/matches/import")
async def import_match(req: ImportMatchReq, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Load a match from StatsBomb by ID or return existing DB match."""
    if req.match_id:
        match = db.query(DBMatch).filter(DBMatch.id == req.match_id).first()
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")
        ready = req.match_id in state.pressure_timeline_cache
        if not ready:
            background_tasks.add_task(precompute_timelines_task, req.match_id, False)
        return {"match_id": req.match_id, "status": "ready" if ready else "processing", "existing": True}

    if not req.statsbomb_id:
        raise HTTPException(status_code=400, detail="statsbomb_id or match_id required")

    if not state.statsbomb.match_exists(req.statsbomb_id):
        raise HTTPException(
            status_code=400,
            detail=f"Match {req.statsbomb_id} is not available in StatsBomb open data.",
        )

    existing = db.query(DBMatch).filter(DBMatch.statsbomb_id == req.statsbomb_id).first()
    if existing:
        mid = existing.id
        if mid not in state.pressure_timeline_cache:
            if not _load_demo_cache(mid):
                background_tasks.add_task(precompute_timelines_task, mid, False)
        return {"match_id": mid, "status": "ready" if mid in state.pressure_timeline_cache else "processing", "existing": True}

    try:
        raw = state.statsbomb.load_match_by_statsbomb_id(req.statsbomb_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not load match {req.statsbomb_id}: {e}")

    parsed = {
        "match_info": {**raw.get("match_info", {}), "statsbomb_id": req.statsbomb_id},
        "events": raw.get("events", []),
        "players": raw.get("players", []),
    }
    db_match = _store_parsed_match(parsed, db)
    state.enriched_events_cache.pop(db_match.id, None)
    state.analysis_status[db_match.id] = "processing"
    background_tasks.add_task(precompute_timelines_task, db_match.id, False)
    return {"match_id": db_match.id, "status": "processing", "existing": False}


@app.get("/api/matches/{match_id}")
async def get_match(match_id: int, db: Session = Depends(get_db)):
    match = db.query(DBMatch).filter(DBMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@app.get("/api/matches/{match_id}/key-events")
async def get_key_events(match_id: int, db: Session = Depends(get_db)):
    events = db.query(DBEvent).filter(DBEvent.match_id == match_id).order_by(DBEvent.minute, DBEvent.second).all()
    match = db.query(DBMatch).filter(DBMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    events_dicts = [{"id": e.id, **{k: getattr(e, k) for k in ("event_type", "minute", "second", "player_name", "player_id", "team", "outcome", "under_pressure", "location_x", "location_y", "details")}} for e in events]
    momentum = state.momentum_timeline_cache.get(match_id, [])
    goals = state.moment_workspace.build_goal_timeline(events_dicts, match.home_team, match.away_team)
    return {
        "events": state.moment_workspace.build_key_events(events_dicts, match.home_team, match.away_team, momentum),
        "goals": goals,
    }


@app.get("/api/matches/{match_id}/moments/{event_id}")
async def get_moment_workspace(match_id: int, event_id: int, db: Session = Depends(get_db)):
    """Unified moment payload — pitch, tactical brief, coach recommendations."""
    cache_key = f"moment:v9:{match_id}:{event_id}"
    if cache_key in state.moment_cache:
        return state.moment_cache[cache_key]

    match = db.query(DBMatch).filter(DBMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    event = db.query(DBEvent).filter(DBEvent.match_id == match_id, DBEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    events_dicts = _get_enriched_events(db, match_id, match)
    events_df = state.statsbomb.get_events_dataframe(events_dicts)
    event_dict = next((e for e in events_dicts if e.get("id") == event_id), event.__dict__)

    pressure_cache = state.pressure_timeline_cache.get(match_id, [])
    momentum = state.momentum_timeline_cache.get(match_id, [])

    pitch = state.moment_workspace.build_pitch_frame(
        events_df, event_dict, match.home_team, match.away_team, pressure_cache
    )

    player_id = event.player_id or 0
    player_name = event.player_name or "Player"
    team = event.team or ""
    pressure_score = 50.0
    pressure_factors = {}
    if player_id:
        player_pt = next((pt for pt in pressure_cache if pt["player_id"] == player_id), None)
        if player_pt:
            pt_point = next((t for t in player_pt["timeline"] if t["minute"] == event.minute), None)
            if pt_point:
                pressure_score = pt_point["pressure_score"]
                pressure_factors = pt_point.get("factors", {})

    team_mom, op_mom = 0.5, 0.5
    if momentum:
        mp = next((m for m in momentum if m.get("minute") == event.minute), None)
        if mp is None:
            mp = momentum[event.minute] if event.minute < len(momentum) else momentum[-1]
        if team == match.home_team:
            team_mom, op_mom = mp.get("home_momentum", 0.5), mp.get("away_momentum", 0.5)
        else:
            team_mom, op_mom = mp.get("away_momentum", 0.5), mp.get("home_momentum", 0.5)

    psych = state.psychology_engine.compute_profile(player_id, player_name, event.minute, events_df, pressure_score)
    replay_ctx = state.replay_engine.reconstruct(
        events_df, player_id, player_name, team, event.minute,
        match.home_team, match.away_team, pressure_score, pressure_factors,
        psych, team_mom, op_mom, match.competition or "",
    )

    why = state.moment_workspace.build_local_why(event_dict, replay_ctx, pitch)
    match_state = state.moment_workspace.build_overview_at_minute(
        match.__dict__, events_df, momentum, match.home_team, match.away_team, event.minute,
    )

    from engine.event_grounding import (
        build_tactical_snapshot,
        build_grounded_explanation,
        build_grounded_bullets,
    )
    event_dict["id"] = event_id
    snapshot = build_tactical_snapshot(
        event_dict, pitch, match_state, replay_ctx, why, match.__dict__,
    )
    why = {**why, **build_grounded_explanation(snapshot)}

    if state.granite:
        try:
            explanation = await asyncio.wait_for(
                state.granite.explain_event(
                    event_type=event_dict.get("event_type", ""),
                    minute=event_dict.get("minute", 0),
                    player_name=event_dict.get("player_name", ""),
                    team=event_dict.get("team", ""),
                    outcome=event_dict.get("outcome") or "N/A",
                    location_x=event_dict.get("location_x") or pitch.get("ball", {}).get("x", 0),
                    location_y=event_dict.get("location_y") or pitch.get("ball", {}).get("y", 0),
                    under_pressure=bool(event_dict.get("under_pressure")),
                    pressure_score=replay_ctx.get("pressure_index", 50),
                    pressure_factors={},
                    score=match_state.get("score", replay_ctx.get("score", "0-0")),
                    team_momentum=replay_ctx.get("game_state", {}).get("team_momentum", 0.5),
                    opponent_momentum=replay_ctx.get("game_state", {}).get("opponent_momentum", 0.5),
                    recent_events=", ".join(replay_ctx.get("recent_actions", [])[:5]),
                    explanation_level="analyst",
                    tactical_snapshot=snapshot,
                ),
                timeout=18.0,
            )
            bullets = explanation.get("bullets") or build_grounded_bullets(snapshot)
            why = {
                **why,
                **explanation,
                "headline": explanation.get("summary") or bullets[0]["text"],
                "tactical_pattern": bullets[-1]["text"] if bullets else why.get("tactical_pattern"),
                "defender_reaction": bullets[1]["text"] if len(bullets) > 1 else why.get("defender_reaction"),
                "attacker_choice": bullets[2]["text"] if len(bullets) > 2 else why.get("attacker_choice"),
                "analyst_narrative": explanation.get("reasoning", ""),
                "granite_pending": False,
                "generated_by": explanation.get("generated_by", "IBM Granite"),
            }
        except Exception as e:
            logger.warning("Granite moment analysis failed: %s", e)
            why = {**why, **build_grounded_explanation(snapshot), "granite_pending": False}

    investigation = state.moment_workspace.build_visual_investigation(
        event_dict, pitch, why, {},
    )
    why_brief = state.moment_workspace.build_why_brief(why, event_dict, investigation)
    investigation = state.moment_workspace.build_visual_investigation(
        event_dict, pitch, why, why_brief,
    )
    why_brief = state.moment_workspace.build_why_brief(why, event_dict, investigation)
    detective_challenge = state.moment_workspace.build_detective_challenge(
        event_dict, pitch, why, match_state=match_state, snapshot=snapshot,
    )
    coach_recommendations = state.moment_workspace.build_coach_recommendations(
        event_dict, pitch, why, snapshot=snapshot,
    )

    payload = {
        "match_id": match_id,
        "event_id": event_id,
        "minute": event.minute,
        "event": {
            "type": event.event_type,
            "player": event.player_name,
            "team": event.team,
            "outcome": event.outcome,
        },
        "pitch": pitch,
        "match_state": match_state,
        "why": {**why, "brief": why_brief},
        "why_brief": why_brief,
        "tactical_brief": why_brief.get("bullets", []),
        "investigation": investigation,
        "coach_recommendations": coach_recommendations,
        "detective_challenge": detective_challenge,
        "replay": replay_ctx,
    }

    state.moment_cache[cache_key] = payload
    return payload



class DetectiveChoiceReq(BaseModel):
    choice: str


@app.post("/api/matches/{match_id}/moments/{event_id}/detective")
async def evaluate_detective(
    match_id: int, event_id: int, req: DetectiveChoiceReq, db: Session = Depends(get_db)
):
    cache_key = f"moment:v9:{match_id}:{event_id}"
    cached = state.moment_cache.get(cache_key)
    if not cached or not cached.get("detective_challenge"):
        raise HTTPException(status_code=404, detail="Moment not loaded")
    event = db.query(DBEvent).filter(DBEvent.id == event_id).first()
    pitch = cached.get("pitch")
    why = cached.get("why", {})
    event_dict = event.__dict__ if event else {}
    result = state.moment_workspace.evaluate_detective_choice(
        req.choice, cached["detective_challenge"], event_dict, pitch=pitch,
    )
    result["coach_recommendations"] = state.moment_workspace.build_coach_recommendations(
        event_dict, pitch, why, user_choice=req.choice,
    )
    return result


@app.get("/api/library/catalog")
async def library_catalog(
    q: str = "",
    league: str = "",
    season: str = "",
    manager: str = "",
    club: str = "",
    player: str = "",
    db: Session = Depends(get_db),
):
    """Streaming-style match library with rich filters."""
    from engine.match_catalog import CATALOG_MATCHES
    items = []
    for m in CATALOG_MATCHES:
        label = f"{m['home_team']} vs {m['away_team']}"
        players = " ".join(m.get("featured_players", []))
        hay = f"{label} {m.get('competition','')} {m.get('league','')} {m.get('season','')} {m.get('manager_home','')} {m.get('manager_away','')} {players}".lower()
        if q and q.lower() not in hay and not any(w in hay for w in q.lower().split() if len(w) > 2):
            continue
        if league and league.lower() not in m.get("league", "").lower():
            continue
        if season and season not in str(m.get("season", "")):
            continue
        if manager and manager.lower() not in hay:
            continue
        if club and club.lower() not in hay:
            continue
        if player and player.lower() not in hay:
            continue
        db_match = db.query(DBMatch).filter(DBMatch.statsbomb_id == m["statsbomb_id"]).first()
        pressure = m.get("pressure_index", 70)
        importance = m.get("importance", 5)
        ai_difficulty = round(min(10, max(3, pressure / 10 + importance * 0.3)), 1)
        items.append({
            **m,
            "label": label,
            "id": db_match.id if db_match else None,
            "loaded": db_match is not None,
            "home_score": db_match.home_score if db_match else None,
            "away_score": db_match.away_score if db_match else None,
            "ai_difficulty": ai_difficulty,
            "xthreat_rating": round(pressure * 0.85 + importance * 2, 0),
        })
    items.sort(key=lambda x: (-x.get("importance", 0), -x.get("pressure_index", 0)))
    return {
        "matches": items,
        "filters": {
            "leagues": sorted({m.get("league", "") for m in CATALOG_MATCHES}),
            "seasons": sorted({m.get("season", "") for m in CATALOG_MATCHES}, reverse=True),
            "players": sorted({p for m in CATALOG_MATCHES for p in m.get("featured_players", [])}),
        },
        "curated": {
            "trending": [i for i in items if "trending" in (i.get("tags") or [])][:4],
            "high_pressure": sorted(items, key=lambda x: -x.get("pressure_index", 0))[:4],
            "comebacks": [i for i in items if "comeback" in (i.get("tags") or [])],
            "high_xthreat": sorted(
                [i for i in items if "high_xthreat" in (i.get("tags") or [])] or items,
                key=lambda x: -x.get("xthreat_rating", 0),
            )[:4],
            "highest_difficulty": sorted(items, key=lambda x: -x.get("ai_difficulty", 0))[:4],
        },
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "env": settings.app_env, "llm": settings.llm_provider}


@app.websocket("/ws/match/{match_id}")
async def match_analysis_socket(websocket: WebSocket, match_id: int):
    await ws_manager.connect(match_id, websocket)
    await websocket.send_json({"match_id": match_id, **_status_payload(match_id)})
    try:
        while True:
            await websocket.receive_text()
            await websocket.send_json({"match_id": match_id, **_status_payload(match_id)})
    except WebSocketDisconnect:
        ws_manager.disconnect(match_id, websocket)
    except Exception:
        ws_manager.disconnect(match_id, websocket)


@app.get("/api/matches/{match_id}/status")
async def get_match_analysis_status(match_id: int):
    return {
        "match_id": match_id,
        "demo_mode": match_id in state.demo_match_ids,
        **_status_payload(match_id),
    }


# Ask PressureLab — natural language analyst on the workspace
class AskQueryReq(BaseModel):
    question: str
    match_id: int
    minute: int = 0
    event_id: Optional[int] = None
    page_context: str = ""
    conversation_history: list[dict[str, str]] = []

@app.post("/api/explain/query")
async def ask_pressurelab(req: AskQueryReq, db: Session = Depends(get_db)):
    """Ask about the selected event — always grounded in tactical snapshot."""
    from engine.event_grounding import (
        build_tactical_snapshot,
        build_grounded_copilot_answer,
        format_snapshot_for_prompt,
    )

    match = db.query(DBMatch).filter(DBMatch.id == req.match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    snapshot = None
    if req.event_id:
        cache_key = f"moment:v9:{req.match_id}:{req.event_id}"
        cached = state.moment_cache.get(cache_key)
        if cached:
            ev = cached.get("event", {})
            event_dict = {
                "id": req.event_id,
                "event_type": ev.get("type"),
                "player_name": ev.get("player"),
                "team": ev.get("team"),
                "outcome": ev.get("outcome"),
                "minute": cached.get("minute", req.minute),
            }
            snapshot = build_tactical_snapshot(
                event_dict,
                cached.get("pitch"),
                cached.get("match_state"),
                cached.get("replay"),
                cached.get("why"),
                match.__dict__,
            )
        else:
            event = db.query(DBEvent).filter(DBEvent.id == req.event_id).first()
            if event:
                snapshot = build_tactical_snapshot(
                    event.__dict__,
                    None,
                    None,
                    None,
                    None,
                    match.__dict__,
                )

    if not snapshot:
        snapshot = build_tactical_snapshot(
            {"minute": req.minute, "player_name": "Player", "event_type": "Moment", "team": match.home_team},
            None,
            {"home_team": match.home_team, "away_team": match.away_team, "minute": req.minute},
            None,
            None,
            match.__dict__,
        )

    match_ctx = format_snapshot_for_prompt(snapshot)
    if state.context_forge:
        mctx = state.context_forge.get_match_context(req.match_id, req.minute)
        match_ctx += "\n" + json.dumps(mctx, default=str)[:800]

    history_ctx = ""
    if req.conversation_history:
        history_ctx = "\n".join(
            f"User: {t.get('q', '')}\nAssistant: {t.get('a', '')[:300]}"
            for t in req.conversation_history[-4:]
        )
    page_ctx = f"{req.page_context}\n{history_ctx}".strip()

    if state.langflow and state.granite:
        pipeline_result = await state.langflow.run_ask_pipeline(
            question=req.question,
            match_id=req.match_id,
            minute=snapshot.get("minute", req.minute),
            match_context=match_ctx,
            tactical_knowledge="",
            historical_comparisons="",
            page_context=page_ctx,
        )
        answer = pipeline_result.get("answer") or pipeline_result.get("reasoning", "")
        if not answer or len(answer) < 30:
            return {**build_grounded_copilot_answer(req.question, snapshot), "generated_by": "PressureLab Event Engine"}
        return {**pipeline_result, "answer": answer, "generated_by": "IBM Granite via LangFlow"}

    if state.granite:
        answer = await state.granite.ask_question(
            question=req.question,
            match_context=match_ctx,
            tactical_knowledge="",
            historical_comparisons="",
            minute=snapshot.get("minute", req.minute),
            page_context=page_ctx,
            tactical_snapshot=snapshot,
        )
        return {**answer, "generated_by": answer.get("generated_by", "IBM Granite")}

    return {**build_grounded_copilot_answer(req.question, snapshot), "generated_by": "PressureLab Event Engine"}
