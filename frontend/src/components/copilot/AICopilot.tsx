import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Loader2 } from 'lucide-react';
import { copilotApi } from '../../services/api';
import { useMatchState } from '../../context/MatchStateContext';
import { formatCopilotAnswer, groundedLocalAnswer } from '../../utils/formatCopilot';
import { computeCamera } from '../../utils/replayPhysics';

const SUGGESTIONS = [
  'Why did this moment happen?',
  'What was the biggest defensive mistake?',
  'What was the best passing option?',
  'What would Pep Guardiola do here?',
];

const FOLLOW_UPS = [
  'What was the best alternative?',
  'Explain the pressing trigger.',
  'Which lane had the highest threat?',
];

type Message = { q: string; a: string; ts: number };

function extractHighlights(q: string, a: string): string[] {
  const h: string[] = [];
  const text = `${q} ${a}`.toLowerCase();
  if (text.includes('press')) h.push('pressing trigger');
  if (text.includes('pass') || text.includes('lane')) h.push('passing lane');
  if (text.includes('space') || text.includes('half')) h.push('half-space');
  if (text.includes('defend') || text.includes('mistake') || text.includes('gap')) h.push('defensive mistake');
  if (text.includes('run') || text.includes('movement')) h.push('attacker movement');
  return h.length ? h : ['half-space'];
}

function trimBullets(answer: string): string {
  const lines = answer.split('\n').filter(Boolean);
  if (lines.length <= 6) return answer;
  return lines.slice(0, 6).map(l => (l.startsWith('•') || l.startsWith('- ') ? l : `• ${l}`)).join('\n');
}

export function AICopilot() {
  const {
    matchId, selectedMinute, selectedEventId, momentData,
    setCopilotHighlights,
    setPitchCamera, setReplayProgress, setHighlightedPlayerIds,
    setNarrationText,
    copilotSessionKey,
  } = useMatchState();
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
    setQuestion('');
    setLoading(false);
  }, [copilotSessionKey]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const triggerPitchFromAnswer = (q: string, answer: string) => {
    const highlights = extractHighlights(q, answer);
    setCopilotHighlights(highlights);
    const pitch = momentData?.pitch;
    if (pitch?.ball) {
      const zoom = highlights.includes('half-space') ? 2.4 : highlights.includes('pressing trigger') ? 2.0 : 2.1;
      setPitchCamera(computeCamera(pitch.ball, pitch.players ?? [], zoom));
      setReplayProgress(0.15);
      const active = pitch.players?.find((p: any) => p.is_active);
      const pressers = pitch.players?.filter((p: any) => p.team === 'away' && (p.pressure ?? 0) > 55);
      if (highlights.includes('pressing trigger') && pressers?.length) {
        setHighlightedPlayerIds(pressers.slice(0, 3).map((p: any) => p.id));
      } else if (active) {
        setHighlightedPlayerIds([active.id]);
      }
      if (highlights.includes('passing lane') && pitch.passing_lanes?.length) {
        setNarrationText(`Highlighting passing lane — ${pitch.passing_lanes.length} options visible.`);
      }
    }
  };

  const ask = async (q: string) => {
    if (!q.trim() || !matchId) return;
    setLoading(true);
    setQuestion('');
    const history = messages.map(m => ({ q: m.q, a: m.a }));
    try {
      const res = await copilotApi.ask(q, matchId, selectedMinute, selectedEventId ?? undefined, history);
      const formatted = formatCopilotAnswer(res);
      const answer = trimBullets(formatted || groundedLocalAnswer(momentData, q));
      setMessages(prev => [...prev, { q, a: answer, ts: Date.now() }]);
      triggerPitchFromAnswer(q, answer);
    } catch {
      const answer = groundedLocalAnswer(momentData, q);
      setMessages(prev => [...prev, { q, a: answer, ts: Date.now() }]);
      triggerPitchFromAnswer(q, answer);
    } finally {
      setLoading(false);
    }
  };

  const suggestions = messages.length === 0 ? SUGGESTIONS : FOLLOW_UPS;

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border-glass">
        <div className="flex items-center gap-2 text-accent-cyan font-semibold">
          <Sparkles size={18} />
          AI Copilot
        </div>
        <p className="text-xs text-text-muted mt-1">IBM Granite · ask why this moment happened</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            {suggestions.map(s => (
              <button key={s} onClick={() => ask(s)}
                className="w-full text-left text-xs p-3 rounded-lg glass glass-hover text-text-secondary hover:border-accent-cyan/30 border border-transparent">
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className="space-y-2">
            <div className="text-xs text-accent-cyan font-medium">{m.q}</div>
            <div className="text-sm text-text-secondary leading-relaxed p-3 rounded-lg bg-bg-tertiary whitespace-pre-wrap">
              {m.a.split('\n').map((line, j) => (
                <div key={j}>{line}</div>
              ))}
            </div>
          </div>
        ))}
        {!loading && messages.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {suggestions.slice(0, 3).map(s => (
              <button key={s} onClick={() => ask(s)}
                className="text-[10px] px-2 py-1 rounded-full border border-border-glass text-text-muted hover:border-accent-cyan/40">
                {s}
              </button>
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="p-4 border-t border-border-glass">
        <div className="flex gap-2">
          <input
            className="flex-1 bg-bg-tertiary border border-border-glass rounded-lg px-3 py-2 text-sm outline-none focus:border-accent-blue/50"
            placeholder="Ask why this moment happened..."
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !loading && ask(question)}
          />
          <button onClick={() => ask(question)} disabled={loading}
            className="p-2 rounded-lg bg-accent-blue text-white disabled:opacity-50">
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
}
