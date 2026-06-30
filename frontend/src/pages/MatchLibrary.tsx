import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, Shield } from 'lucide-react';
import { matchApi } from '../services/api';
import { useMatchState } from '../context/MatchStateContext';

const POSTERS = [
  'from-blue-900 via-indigo-900 to-purple-900',
  'from-emerald-900 via-teal-900 to-cyan-900',
  'from-red-900 via-rose-900 to-orange-900',
  'from-slate-900 via-zinc-800 to-amber-900',
];

export default function MatchLibrary() {
  const { setMatchId, setMatchInfo, setAppView, resetWorkspaceState } = useMatchState();
  const [matches, setMatches] = useState<any[]>([]);
  const [curated, setCurated] = useState<{ trending: any[]; high_pressure: any[]; comebacks: any[]; high_xthreat: any[]; highest_difficulty?: any[] }>({
    trending: [], high_pressure: [], comebacks: [], high_xthreat: [], highest_difficulty: [],
  });
  const [filters, setFilters] = useState({ q: '', league: '', season: '', manager: '', club: '', player: '' });
  const [meta, setMeta] = useState<{ leagues: string[]; seasons: string[]; players?: string[] }>({ leagues: [], seasons: [], players: [] });
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.q) params.set('q', filters.q);
      if (filters.league) params.set('league', filters.league);
      if (filters.season) params.set('season', filters.season);
      if (filters.manager) params.set('manager', filters.manager);
      if (filters.club) params.set('club', filters.club);
      if (filters.player) params.set('player', filters.player);
      const res = await matchApi.libraryCatalog(params.toString());
      setMatches(res.matches);
      setMeta(res.filters);
      if (res.curated) setCurated(res.curated);
    } catch {
      setMatches([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openMatch = async (m: any) => {
    setImporting(m.statsbomb_id);
    try {
      const body = m.id ? { match_id: m.id } : { statsbomb_id: m.statsbomb_id };
      const imp = await matchApi.importMatch(body);
      const id = imp.match_id ?? m.id;
      const match = await matchApi.getMatch(id);
      resetWorkspaceState();
      setMatchId(id);
      setMatchInfo(match);
      setAppView('workspace');
    } finally {
      setImporting(null);
    }
  };

  return (
    <div className="min-h-full bg-bg-primary">
      <div className="relative h-48 bg-gradient-to-r from-accent-blue/30 via-bg-secondary to-accent-purple/20 border-b border-border-glass flex items-end p-8">
        <div>
          <h1 className="text-3xl font-bold">Tactical Replay Library</h1>
          <p className="text-text-muted text-sm mt-1">Search · filter · one-click load into the Digital Match Twin</p>
        </div>
      </div>

      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-[200px] relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              className="w-full pl-9 pr-3 py-2.5 rounded-xl glass border border-border-glass text-sm outline-none focus:border-accent-cyan/50"
              placeholder="Search club, player, manager..."
              value={filters.q}
              onChange={e => setFilters(f => ({ ...f, q: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && load()}
            />
          </div>
          <select className="px-3 py-2 rounded-xl glass border border-border-glass text-sm bg-transparent"
            value={filters.league} onChange={e => setFilters(f => ({ ...f, league: e.target.value }))}>
            <option value="">All leagues</option>
            {meta.leagues.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
          <select className="px-3 py-2 rounded-xl glass border border-border-glass text-sm bg-transparent"
            value={filters.season} onChange={e => setFilters(f => ({ ...f, season: e.target.value }))}>
            <option value="">All seasons</option>
            {meta.seasons.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="px-3 py-2 rounded-xl glass border border-border-glass text-sm bg-transparent"
            value={filters.player} onChange={e => setFilters(f => ({ ...f, player: e.target.value }))}>
            <option value="">All players</option>
            {(meta.players ?? []).map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <button onClick={load} className="px-5 py-2 rounded-xl bg-accent-blue text-white text-sm font-medium">
            Filter
          </button>
        </div>

        {loading ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="h-48 rounded-2xl bg-bg-tertiary animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-10">
            {curated.trending.length > 0 && (
              <CuratedRow title="Trending Now" matches={curated.trending} onOpen={openMatch} importing={importing} />
            )}
            {curated.high_pressure.length > 0 && (
              <CuratedRow title="Highest Pressure" matches={curated.high_pressure} onOpen={openMatch} importing={importing} />
            )}
            {curated.comebacks.length > 0 && (
              <CuratedRow title="Greatest Comebacks" matches={curated.comebacks} onOpen={openMatch} importing={importing} />
            )}
            {(curated.high_xthreat?.length ?? 0) > 0 && (
              <CuratedRow title="Highest xThreat" matches={curated.high_xthreat ?? []} onOpen={openMatch} importing={importing} />
            )}
            {(curated.highest_difficulty?.length ?? 0) > 0 && (
              <CuratedRow title="AI Difficulty Rating" matches={curated.highest_difficulty ?? []} onOpen={openMatch} importing={importing} />
            )}
            <div>
              <h2 className="text-lg font-semibold mb-4">All Matches</h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                <AnimatePresence>
                  {matches.map((m, i) => (
                    <MatchCard key={m.statsbomb_id} m={m} i={i} onOpen={() => openMatch(m)} importing={importing === m.statsbomb_id} />
                  ))}
                </AnimatePresence>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CuratedRow({ title, matches, onOpen, importing }: { title: string; matches: any[]; onOpen: (m: any) => void; importing: number | null }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin">
        {matches.map((m, i) => (
          <div key={m.statsbomb_id} className="flex-shrink-0 w-72">
            <MatchCard m={m} i={i} onOpen={() => onOpen(m)} importing={importing === m.statsbomb_id} horizontal />
          </div>
        ))}
      </div>
    </div>
  );
}

function MatchCard({ m, i, onOpen, importing, horizontal }: { m: any; i: number; onOpen: () => void; importing: boolean; horizontal?: boolean }) {
  const homeInitial = m.home_team?.slice(0, 2).toUpperCase();
  const awayInitial = m.away_team?.slice(0, 2).toUpperCase();
  return (
    <motion.button
      layout
      whileHover={{ scale: 1.02, y: -4 }}
      onClick={onOpen}
      disabled={importing}
      className={`text-left rounded-2xl overflow-hidden border border-border-glass glass-hover shadow-lg disabled:opacity-60 w-full ${horizontal ? '' : ''}`}
    >
      <div className={`bg-gradient-to-br ${POSTERS[i % POSTERS.length]} p-4 relative ${horizontal ? 'h-32' : 'h-28'}`}>
        <div className="flex items-center gap-2 mb-2">
          <span className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-xs font-bold">{homeInitial}</span>
          <span className="text-white/50 text-xs">vs</span>
          <span className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-xs font-bold">{awayInitial}</span>
        </div>
        <div className="font-bold text-white text-sm">{m.home_team} vs {m.away_team}</div>
        <div className="text-[10px] text-white/70 mt-1">{m.competition}</div>
        <div className="absolute top-3 right-3 flex flex-col items-end gap-1 text-xs">
          <div className="flex items-center gap-1 text-amber-300">
            <Shield size={12} /> {m.pressure_index}
          </div>
          {m.ai_difficulty != null && (
            <span className="text-accent-purple font-mono text-[10px]">AI {m.ai_difficulty}/10</span>
          )}
        </div>
      </div>
      <div className="p-3 space-y-1">
        <div className="text-[10px] text-text-muted">{m.manager_home} · {m.manager_away}</div>
        {m.loaded && <span className="text-[10px] text-accent-cyan">Ready to investigate</span>}
      </div>
    </motion.button>
  );
}
