import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, Loader2 } from 'lucide-react';
import { matchApi } from '../services/api';
import { useMatchState } from '../context/MatchStateContext';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

export default function HomePage() {
  const { setMatchId, setMatchInfo, setAppView, resetWorkspaceState } = useMatchState();
  const [searchQ, setSearchQ] = useState('');
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    matchApi.health()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false));
  }, []);

  const waitReady = async (id: number) => {
    const initial = await matchApi.getStatus(id);
    if (initial.timelines_ready || initial.status === 'ready') return;
    if (initial.status === 'error') throw new Error('Analysis failed');

    const ready = await new Promise<boolean>((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new WebSocket(`${protocol}//${window.location.host}/ws/match/${id}`);
      const timeout = window.setTimeout(() => {
        socket.close();
        resolve(false);
      }, 90000);

      socket.onmessage = event => {
        const status = JSON.parse(event.data);
        if (status.timelines_ready || status.status === 'ready') {
          window.clearTimeout(timeout);
          socket.close();
          resolve(true);
        } else if (status.status === 'error') {
          window.clearTimeout(timeout);
          socket.close();
          reject(new Error('Analysis failed'));
        }
      };

      socket.onerror = () => {
        window.clearTimeout(timeout);
        socket.close();
        resolve(false);
      };
    });

    if (!ready) throw new Error('Analysis timed out. Please retry the match.');
  };

  const enterWorkspace = async (id: number) => {
    setLoading(true);
    setError(null);
    setShowSuggestions(false);
    try {
      const status = await matchApi.getStatus(id);
      if (!status.timelines_ready) await waitReady(id);
      const match = await matchApi.getMatch(id);
      resetWorkspaceState();
      setMatchId(id);
      setMatchInfo(match);
      setAppView('workspace');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    setSuggestLoading(true);
    try {
      const res = await matchApi.suggest(q);
      setSuggestions(res.suggestions);
      setShowSuggestions(res.suggestions.length > 0);
      setHighlightIdx(-1);
      if (res.offline) setApiOnline(false);
    } catch {
      setSuggestions([]);
    } finally {
      setSuggestLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => fetchSuggestions(searchQ), 280);
    return () => clearTimeout(t);
  }, [searchQ, fetchSuggestions]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const selectMatch = async (r: any) => {
    setSearchQ(r.label);
    setShowSuggestions(false);
    setLoading(true);
    setError(null);
    try {
      const res = await matchApi.importMatch({
        match_id: r.id ?? undefined,
        statsbomb_id: r.statsbomb_id ?? undefined,
      });
      await enterWorkspace(res.match_id);
    } catch (e: any) {
      setError(e.message);
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Enter' && searchQ.trim()) {
        fetchSuggestions(searchQ);
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx(i => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && highlightIdx >= 0) {
      e.preventDefault();
      selectMatch(suggestions[highlightIdx]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  return (
    <div className="min-h-full flex flex-col items-center justify-center p-8 relative">
      {loading && (
        <div className="fixed inset-0 z-50 bg-bg-primary/90 flex items-center justify-center">
          <LoadingSpinner size={48} text="Building Digital Match Twin..." />
        </div>
      )}

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center max-w-2xl mb-16">
        <h1 className="text-6xl font-black mb-4 gradient-text">PressureLab AI</h1>
        <p className="text-xl text-text-secondary">Interactive Digital Match Twin — replay, inspect, and compare every decision.</p>
      </motion.div>

      {apiOnline === false && !error && (
        <div className="mb-6 px-4 py-3 rounded-xl glass border border-accent-gold/30 text-accent-gold text-sm max-w-4xl w-full">
          Backend offline — showing local match suggestions. Run{' '}
          <code className="text-xs bg-bg-tertiary px-1 rounded">bash scripts/start-dev.sh</code>
        </div>
      )}

      {error && (
        <div className="mb-6 px-4 py-3 rounded-xl glass border border-danger/30 text-danger text-sm max-w-4xl w-full">
          {error}
          {error.includes('502') && (
            <p className="mt-2 text-text-muted text-xs">
              Backend not reachable. Run <code>bash scripts/start-dev.sh</code>
            </p>
          )}
        </div>
      )}

      <div className="w-full max-w-4xl">
        <motion.div className="glass rounded-2xl p-6 relative" initial={{ opacity: 0 }} animate={{ opacity: 1 }} ref={searchRef}>
          <div className="flex items-center gap-2 mb-4 text-accent-cyan font-semibold">
            <Search size={20} /> Search Match
          </div>
          <div className="relative">
            <input
              className="w-full bg-bg-tertiary border border-border-glass rounded-xl px-4 py-3 text-sm outline-none focus:border-accent-cyan/50 pr-10"
              placeholder="Liverpool vs Real Madrid, France vs Croatia..."
              value={searchQ}
              onChange={e => { setSearchQ(e.target.value); setShowSuggestions(true); }}
              onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
              onKeyDown={handleKeyDown}
              autoComplete="off"
              role="combobox"
              aria-expanded={showSuggestions}
              aria-autocomplete="list"
            />
            {suggestLoading && (
              <Loader2 size={16} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-text-muted" />
            )}
            <AnimatePresence>
              {showSuggestions && suggestions.length > 0 && (
                <motion.ul
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="absolute z-50 top-full left-0 right-0 mt-2 py-2 rounded-xl glass border border-border-glass shadow-xl max-h-64 overflow-y-auto"
                  role="listbox"
                >
                  {suggestions.map((r, i) => (
                    <li key={`${r.statsbomb_id}-${r.label}`} role="option" aria-selected={i === highlightIdx}>
                      <button
                        type="button"
                        onClick={() => selectMatch(r)}
                        onMouseEnter={() => setHighlightIdx(i)}
                        className={`w-full text-left px-4 py-3 flex justify-between items-center gap-3 transition-colors ${
                          i === highlightIdx ? 'bg-accent-blue/15' : 'hover:bg-bg-glass-hover'
                        }`}
                      >
                        <div>
                          <div className="font-medium text-text-primary">{r.label}</div>
                          <div className="text-xs text-text-muted">{r.competition}{r.match_date ? ` · ${r.match_date}` : ''}</div>
                        </div>
                        {r.loaded && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-pressure-low/20 text-pressure-low shrink-0">Ready</span>
                        )}
                      </button>
                    </li>
                  ))}
                </motion.ul>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
