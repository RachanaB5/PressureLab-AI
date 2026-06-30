import { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { Crosshair, Loader2 } from 'lucide-react';
import { useMatchState } from '../../context/MatchStateContext';
import { MomentPitch } from './MomentPitch';
import { matchApi } from '../../services/api';
import {
  INVESTIGATION_LABELS,
  resolveInvestigation,
  type InvestigationKey,
} from '../../utils/visualInvestigation';

const KEYS: InvestigationKey[] = [
  'why',
  'best_passing_option',
  'missed_opportunity',
  'defensive_mistake',
  'tactical_pattern',
];

type CoachRec = {
  id: string;
  name: string;
  action: string;
  action_id: string;
  reason: string;
  expected_success: number;
  expected_threat: number;
  explanation: string;
};

export function TacticalDetective({
  onSeekReplay,
}: {
  onSeekReplay?: (progress: number, autoPlay?: boolean) => void;
}) {
  const {
    momentData, selectedPlayerId, pitchCamera, replayProgress, pitchFrom,
    matchId, selectedEventId,
    setWhyHighlight,
    coachComparison, setCoachComparison,
  } = useMatchState();
  const [activeKey, setActiveKey] = useState<InvestigationKey>('why');
  const [userChoice, setUserChoice] = useState<string | null>(null);
  const [loadingChoice, setLoadingChoice] = useState(false);

  useEffect(() => {
    setUserChoice(null);
    setActiveKey('why');
    setLoadingChoice(false);
  }, [matchId, selectedEventId]);

  const inv = resolveInvestigation(momentData);
  const brief = momentData?.tactical_brief ?? momentData?.why_brief?.bullets ?? [];
  const coachData = coachComparison?.coach_recommendations ?? momentData?.coach_recommendations;
  const options = coachData?.options ?? [];

  if (!momentData?.pitch || momentData.match_id !== matchId || momentData.event_id !== selectedEventId) {
    return null;
  }

  const selectInsight = (key: InvestigationKey) => {
    setActiveKey(key);
    const hl = inv.highlights?.[key] ?? 'half-space';
    setWhyHighlight(hl);
    onSeekReplay?.(0.25, false);
  };

  const submitDecision = async (choiceId: string) => {
    setUserChoice(choiceId);
    if (!matchId || !selectedEventId) return;
    setLoadingChoice(true);
    try {
      const result = await matchApi.detectiveChoice(matchId, selectedEventId, choiceId);
      setCoachComparison(result);
    } catch {
      const base = momentData?.coach_recommendations;
      if (base) {
        const opts = Object.fromEntries((base.options ?? []).map((o: any) => [o.id, o]));
        const pick = opts[choiceId];
        const recs: CoachRec[] = [
          {
            id: 'user',
            name: 'Your Decision',
            action_id: choiceId,
            action: pick?.label ?? choiceId,
            reason: 'Your selected tactical approach for this freeze-frame.',
            expected_success: Math.round(30 + (pick?.xG ?? 0.15) * 95 + (pick?.xT ?? 0.12) * 22),
            expected_threat: Math.round((pick?.xT ?? 0.12) * 115 + (pick?.xG ?? 0.15) * 18),
            explanation: 'Your read on the current tactical picture.',
          },
          ...(base.recommendations ?? []),
        ];
        setCoachComparison({ coach_recommendations: { ...base, recommendations: recs }, verdict: '' });
      }
    } finally {
      setLoadingChoice(false);
    }
  };

  const recommendations: CoachRec[] = coachComparison?.coach_recommendations?.recommendations
    ?? (userChoice ? [] : coachData?.recommendations ?? []);

  const displayRecs = coachComparison?.coach_recommendations?.recommendations ?? recommendations;

  return (
    <div className="glass rounded-2xl p-5 space-y-5 border border-accent-purple/25">
      <div className="flex items-center gap-2 flex-wrap">
        <Crosshair className="text-accent-purple" size={18} />
        <h3 className="font-bold">Tactical Detective</h3>
        <span className="text-xs text-text-muted ml-auto">Why did this moment happen?</span>
      </div>

      {brief.length > 0 && (
        <ul className="space-y-2 text-sm">
          {brief.map((b: { label?: string; text?: string; key?: string }) => (
            <li key={b.key ?? b.label} className="flex gap-2">
              <span className="text-accent-purple shrink-0">•</span>
              <span>
                {b.label && <span className="text-text-muted text-xs uppercase tracking-wide mr-2">{b.label}</span>}
                {b.text}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="grid lg:grid-cols-[1fr_280px] gap-4">
        <MomentPitch
          frame={momentData.pitch}
          pitchFrom={pitchFrom}
          selectedPlayerId={selectedPlayerId}
          compact
          animateKey={`detective-${activeKey}`}
          highlight={inv.highlights?.[activeKey] ?? 'half-space'}
          replayProgress={replayProgress}
          camera={pitchCamera}
          showHeatmap
          enhancedPlayerFocus
          showPlayerMetrics={false}
        />
        <div className="space-y-2">
          {KEYS.map(key => (
            <button
              key={key}
              onClick={() => selectInsight(key)}
              className={`w-full text-left p-3 rounded-xl border transition-all ${
                activeKey === key
                  ? 'border-accent-purple bg-accent-purple/10'
                  : 'border-border-glass hover:border-accent-purple/40'
              }`}
            >
              <div className="text-[10px] uppercase tracking-wide text-text-muted">{INVESTIGATION_LABELS[key]}</div>
              <div className="text-sm mt-1 leading-snug line-clamp-2">{inv[key]}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-border-glass pt-4 space-y-3">
        <h4 className="text-sm font-semibold">What would you do?</h4>
        <p className="text-xs text-text-muted">{coachData?.prompt ?? 'Choose your tactical decision, then compare with elite coaches.'}</p>
        <div className="flex flex-wrap gap-2">
          {options.map((opt: { id: string; label: string }) => (
            <button
              key={opt.id}
              onClick={() => submitDecision(opt.id)}
              disabled={loadingChoice}
              className={`px-3 py-2 rounded-lg text-xs border transition ${
                userChoice === opt.id
                  ? 'border-accent-purple bg-accent-purple/15 text-accent-purple'
                  : 'border-border-glass hover:border-accent-purple/40'
              }`}
            >
              {opt.label}
            </button>
          ))}
          {loadingChoice && <Loader2 size={16} className="animate-spin text-accent-purple self-center" />}
        </div>
      </div>

      {displayRecs.length > 0 && userChoice && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="border-t border-border-glass pt-4 space-y-3"
        >
          <h4 className="text-sm font-semibold">Coach Recommendations</h4>
          {coachComparison?.verdict && (
            <p className="text-xs text-accent-cyan">{coachComparison.verdict}</p>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            {displayRecs.map((rec: CoachRec) => (
              <CoachCard key={rec.id} rec={rec} highlight={rec.id === 'user'} />
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}

function CoachCard({ rec, highlight }: { rec: CoachRec; highlight?: boolean }) {
  return (
    <div className={`rounded-xl p-3 border text-xs space-y-2 ${
      highlight ? 'border-accent-purple bg-accent-purple/10' : 'border-border-glass'
    }`}>
      <div className="font-semibold text-sm">{rec.name}</div>
      <div className="text-accent-cyan font-medium">{rec.action}</div>
      <p className="text-text-secondary leading-relaxed">{rec.explanation || rec.reason}</p>
      <div className="flex gap-4 text-[10px] font-mono">
        <span>Success <strong className="text-text-primary">{rec.expected_success}%</strong></span>
        <span>Threat <strong className="text-text-primary">{rec.expected_threat}%</strong></span>
      </div>
    </div>
  );
}
