import { motion } from 'motion/react';
import { Radio, MousePointer2 } from 'lucide-react';
import { MomentPitch } from './MomentPitch';
import type { PitchPlayer } from './MomentPitch';

export function DigitalMatchTwin({
  pitchFrame,
  pitchFrom = null,
  selectedPlayerId,
  onSelectPlayer,
  animateKey,
  replayProgress,
  camera,
  crowdIntensity,
  highlightedPlayerIds,
  highlights,
  whyHighlight,
  narrationText,
  replayPlaying,
  loading,
}: {
  pitchFrame: any;
  pitchFrom?: any;
  selectedPlayerId: string | null;
  onSelectPlayer: (id: string | null) => void;
  animateKey: number;
  replayProgress: number;
  camera: any;
  crowdIntensity: number;
  highlightedPlayerIds: string[];
  highlights: string[];
  whyHighlight: string | null;
  narrationText: string;
  replayPlaying: boolean;
  loading: boolean;
}) {
  const selected = pitchFrame?.players?.find((p: PitchPlayer) => p.id === selectedPlayerId);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold flex items-center gap-2">
            <MousePointer2 size={18} className="text-accent-cyan" />
            Digital Match Twin
          </h2>
          <p className="text-xs text-text-muted mt-0.5">Watch the moment replay — players, ball, lanes, and pressure zones update live.</p>
        </div>
        <span className="text-[10px] px-2 py-1 rounded-full bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30">Replay Engine</span>
      </div>

      {narrationText && replayPlaying && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex items-center gap-2 text-xs text-accent-cyan glass rounded-lg px-3 py-2 border border-accent-cyan/20">
          <Radio size={12} className="animate-pulse shrink-0" />
          <span className="line-clamp-2">{narrationText}</span>
        </motion.div>
      )}

      <div className="grid lg:grid-cols-[1fr_280px] gap-4">
        <MomentPitch
          frame={pitchFrame}
          pitchFrom={pitchFrom}
          selectedPlayerId={selectedPlayerId}
          onSelectPlayer={onSelectPlayer}
          highlight={whyHighlight}
          extraHighlights={highlights}
          animateKey={animateKey}
          replayProgress={replayProgress}
          camera={camera}
          crowdIntensity={crowdIntensity}
          highlightedPlayerIds={highlightedPlayerIds}
          showHeatmap
          enhancedPlayerFocus
          showPlayerMetrics={false}
          loading={loading}
        />
        <PlayerIntelRail player={selected} pitch={pitchFrame} />
      </div>
    </div>
  );
}

function PlayerIntelRail({ player, pitch }: { player?: PitchPlayer; pitch: any }) {
  if (!player) {
    return (
      <div className="glass rounded-xl p-4 border border-dashed border-border-glass text-center text-xs text-text-muted flex flex-col justify-center min-h-[200px]">
        <MousePointer2 size={24} className="mx-auto mb-2 opacity-40" />
        Select a player on the pitch to inspect pressure, lanes, and decision metrics.
      </div>
    );
  }

  const lanes = (pitch?.passing_lanes ?? []).length;
  const opts = player.pass_options ?? [];

  return (
    <motion.div
      key={player.id}
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      className="glass rounded-xl p-4 space-y-3 border border-accent-cyan/25 text-xs"
    >
      <div>
        <div className="font-bold text-sm">{player.name}</div>
        <div className="text-text-muted">{player.role}</div>
      </div>
      <IntelRow label="Pressure" value={`${player.pressure_index ?? player.pressure ?? 50}/100`} accent />
      <IntelRow label="xThreat" value={player.xthreat != null ? String(player.xthreat) : '—'} />
      <IntelRow label="Decision" value={`${player.decision_score ?? '—'}/100`} />
      <IntelRow label="Expected" value={player.expected_action ?? '—'} />
      <IntelRow label="Pass lanes" value={String(lanes)} />
      {player.speed_kmh != null && <IntelRow label="Speed" value={`${player.speed_kmh} km/h`} />}
      {opts.slice(0, 2).map((o, i) => (
        <div key={i} className="text-[10px] text-text-secondary pl-2 border-l border-accent-green/40">
          {o.type} · {o.success_prob != null ? `${Math.round(o.success_prob * 100)}%` : '—'}
        </div>
      ))}
    </motion.div>
  );
}

function IntelRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-text-muted">{label}</span>
      <span className={`font-mono font-semibold ${accent ? 'text-accent-cyan' : ''}`}>{value}</span>
    </div>
  );
}
