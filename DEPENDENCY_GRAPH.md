# PressureLab AI — Active Module Dependency Graph

Production surface after cleanup. Arrows show import/call direction (consumer → provider).

## Frontend (26 source files)

```mermaid
flowchart TB
  subgraph entry [Entry]
    main["main.tsx"]
    App["App.tsx"]
  end

  subgraph context [State]
    MSC["MatchStateContext.tsx"]
  end

  subgraph pages [Pages]
    Home["HomePage.tsx"]
    Library["MatchLibrary.tsx"]
    Workspace["WorkspacePage.tsx"]
    Settings["SettingsPage.tsx"]
  end

  subgraph layout [Layout]
    Shell["AppShell.tsx"]
  end

  subgraph workspace [Workspace]
    MomentHook["useMomentEngine.ts"]
    Header["MatchHeader.tsx"]
    Timeline["InteractiveTimeline.tsx"]
    Transport["ReplayTransport.tsx"]
    Twin["DigitalMatchTwin.tsx"]
    Pitch["MomentPitch.tsx"]
    Detective["TacticalDetective.tsx"]
    Loading["LoadingStages.tsx"]
    Strip["WorkflowStrip.tsx"]
  end

  subgraph copilot [Copilot]
    AICopilot["AICopilot.tsx"]
  end

  subgraph services [Services]
    API["services/api.ts"]
    Catalog["data/matchCatalog.ts"]
  end

  subgraph utils [Utils]
    Overview["matchOverview.ts"]
    Replay["replayPhysics.ts"]
    CopilotFmt["formatCopilot.ts"]
    Visual["visualInvestigation.ts"]
  end

  subgraph ui [UI]
    Spinner["LoadingSpinner.tsx"]
  end

  main --> App
  App --> MSC
  App --> Shell
  Shell --> Home
  Shell --> Library
  Shell --> Workspace
  Shell --> Settings

  Home --> API
  Home --> Catalog
  Home --> MSC

  Library --> API
  Library --> Catalog
  Library --> MSC

  Workspace --> API
  Workspace --> MSC
  Workspace --> MomentHook
  Workspace --> Overview
  Workspace --> Header
  Workspace --> Timeline
  Workspace --> Transport
  Workspace --> Twin
  Workspace --> Detective
  Workspace --> Strip
  Workspace --> Loading
  Workspace --> AICopilot

  MomentHook --> API
  MomentHook --> MSC
  MomentHook --> Replay

  Twin --> Pitch
  Twin --> MSC
  Twin --> Replay
  Twin --> Visual

  Detective --> API
  Detective --> MSC

  AICopilot --> API
  AICopilot --> MSC
  AICopilot --> CopilotFmt

  Header --> MSC
  Header --> Overview
  Timeline --> MSC
  Transport --> MSC
  Transport --> MomentHook
```

### Frontend API calls (only these endpoints)

| Client method | HTTP |
|---|---|
| `matchApi.health` | `GET /api/health` |
| `matchApi.suggest` | `GET /api/matches/suggest` |
| `matchApi.importMatch` | `POST /api/matches/import` |
| `matchApi.getMatch` | `GET /api/matches/{id}` |
| `matchApi.getStatus` | `GET /api/matches/{id}/status` |
| `matchApi.getKeyEvents` | `GET /api/matches/{id}/key-events` |
| `matchApi.getMoment` | `GET /api/matches/{id}/moments/{event_id}` |
| `matchApi.detectiveChoice` | `POST /api/matches/{id}/moments/{event_id}/detective` |
| `matchApi.libraryCatalog` | `GET /api/library/catalog` |
| `copilotApi.ask` | `POST /api/explain/query` |
| WebSocket (HomePage) | `WS /ws/match/{id}` |

---

## Backend (active production path)

```mermaid
flowchart TB
  subgraph api [main.py routes]
    R_health["GET /health"]
    R_suggest["GET /matches/suggest"]
    R_import["POST /matches/import"]
    R_match["GET /matches/{id}"]
    R_status["GET /matches/{id}/status"]
    R_events["GET /matches/{id}/key-events"]
    R_moment["GET /matches/{id}/moments/{event_id}"]
    R_detective["POST .../detective"]
    R_library["GET /library/catalog"]
    R_copilot["POST /explain/query"]
    R_ws["WS /ws/match/{id}"]
  end

  subgraph engines [Engines]
    MW["moment_workspace.py"]
    RE["replay_engine.py"]
    PE["pressure_index.py"]
    ME["momentum.py"]
    PSY["psychology.py"]
    PSE["pitch_state_engine.py"]
    ML["match_loader.py"]
    MC["match_catalog.py"]
    CM["cache_manager.py"]
    EG["event_grounding.py"]
  end

  subgraph ai [AI layer]
    GC["granite_client.py"]
    PR["prompts.py"]
    LLM["providers/*"]
    CF["context_forge.py"]
    LF["langflow_client.py"]
  end

  subgraph data [Data]
    SB["statsbomb_loader.py"]
    DB["db/database.py"]
  end

  R_import --> ML
  R_import --> CM
  R_moment --> MW
  R_moment --> RE
  R_moment --> PE
  R_moment --> PSY
  R_moment --> EG
  R_moment --> GC
  R_detective --> MW
  R_events --> MW
  R_copilot --> EG
  R_copilot --> GC
  R_copilot --> LF
  R_suggest --> MC
  R_library --> MC

  MW --> PSE
  GC --> PR
  GC --> EG
  GC --> LLM
  LF --> GC
  LF --> CF

  main_precompute["precompute_timelines"] --> PE
  main_precompute --> ME
  main_precompute --> CM
```

### Backend modules retained but not on HTTP surface

These support moment analysis or optional Granite enrichment:

- `engine/replay_engine.py` — player decision context inside moment payload
- `engine/psychology.py` — composure/pressure traits for replay context
- `engine/pitch_state_engine.py` — coordinate coverage for pitch frames
- `ai/context_forge.py`, `ai/langflow_client.py`, `ai/docling_processor.py` — optional copilot pipeline
- `ai/providers/huggingface.py`, `ai/providers/watsonx.py` — LLM backends

### Removed from production path

| Category | Removed |
|---|---|
| Frontend components | `PressureTimeline`, `MomentumChart`, `FootballPitch`, `TraitRadarChart`, unused UI kit, `types/index.ts`, `probability.ts` |
| Frontend deps | `d3`, `@types/d3`, `react-router-dom` |
| Backend routes | search, overview, events list, upload/paste, twin, load-demo, live status, match-story, timeline-context, pressure/momentum GET, explain/event, replay/mind, prediction*, psychology*, simulate |
| Backend engines | `coach_simulator.py`, counterfactual methods in `moment_workspace.py` |
| AI prompts | `REPLAY_MIND`, `PREDICTION_EXPLANATION`, `COACH_SIMULATOR`, `PSYCHOLOGY` |
| Other | `backend/test.py`, `backend/models/schemas.py`, placeholder SVG assets |

---

## Data flow (one moment)

```
User selects event on timeline
  → useMomentEngine.syncMoment()
  → GET /moments/{event_id}
      → pressure_index + momentum caches
      → replay_engine (player context)
      → moment_workspace (pitch, why, detective, coach recs)
      → event_grounding + granite_client (bullets)
  → Workspace renders pitch replay + Tactical Detective + Copilot
```
