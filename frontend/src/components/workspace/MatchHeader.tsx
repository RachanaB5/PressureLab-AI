import { motion } from 'motion/react';
import type { MatchOverviewState } from '../../utils/matchOverview';
import { formatScore } from '../../utils/matchOverview';

export function MatchHeader({
  overview,
  loading,
}: {
  overview: MatchOverviewState | null;
  loading?: boolean;
}) {
  if (!overview) {
    return (
      <div className="glass rounded-2xl px-5 py-4 border border-border-glass animate-pulse h-[88px]" />
    );
  }

  const home = overview.home_team;
  const away = overview.away_team;
  const score = overview.score || formatScore(overview.home_score, overview.away_score);
  const clock = overview.clock ?? `${overview.minute}'`;

  return (
    <div className="glass rounded-2xl px-5 py-4 flex flex-wrap items-center justify-between gap-4 border border-border-glass">
      <div>
        <div className="text-[10px] uppercase tracking-widest text-text-muted">{overview.competition}</div>
        <div className="text-xl font-bold mt-0.5">
          {home} <span className="text-text-muted font-normal">vs</span> {away}
        </div>
      </div>
      <motion.div
        key={`${score}-${clock}-${overview.minute}`}
        initial={{ scale: 0.95 }}
        animate={{ scale: 1 }}
        className="text-center"
      >
        <div className={`text-3xl font-mono font-bold text-accent-cyan ${loading ? 'opacity-60' : ''}`}>
          {score}
        </div>
        <div className="text-xs text-accent-cyan/80 font-mono mt-0.5">{clock}</div>
      </motion.div>
      <div className="flex flex-wrap gap-4 min-w-[200px]">
        {overview.momentum && (
          <div className="flex-1 min-w-[120px]">
            <div className="text-[10px] text-text-muted mb-1">Momentum</div>
            <div className="h-1.5 rounded-full bg-bg-secondary overflow-hidden flex">
              <div className="h-full bg-blue-500" style={{ width: `${overview.momentum.home}%` }} />
              <div className="h-full bg-red-500" style={{ width: `${overview.momentum.away}%` }} />
            </div>
            <div className="flex justify-between text-[10px] text-text-muted mt-1">
              <span>{overview.momentum.home}%</span>
              <span>{overview.momentum.away}%</span>
            </div>
          </div>
        )}
        {overview.possession && (
          <div className="flex-1 min-w-[100px]">
            <div className="text-[10px] text-text-muted mb-1">Possession</div>
            <div className="flex justify-between text-[10px] font-mono">
              <span className="text-blue-400">{overview.possession.home}%</span>
              <span className="text-red-400">{overview.possession.away}%</span>
            </div>
          </div>
        )}
        {overview.pressure_index != null && (
          <div>
            <div className="text-[10px] text-text-muted mb-1">Pressure</div>
            <div className="text-sm font-mono font-semibold text-accent-cyan">{overview.pressure_index}</div>
          </div>
        )}
      </div>
    </div>
  );
}
