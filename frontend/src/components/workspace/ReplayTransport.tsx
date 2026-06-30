import { Play, Pause, SkipBack, SkipForward, RotateCcw } from 'lucide-react';
import type { ReplayControls } from '../../hooks/useMomentEngine';

export function ReplayTransport({
  replayProgress,
  replayPlaying,
  slowMotion = false,
  controls,
  onResetSlowMo,
}: {
  replayProgress: number;
  replayPlaying: boolean;
  slowMotion?: boolean;
  controls: ReplayControls;
  onResetSlowMo?: () => void;
}) {
  const { togglePlay, stepFrame, seekReplay, playReplay } = controls;

  return (
    <div className="glass rounded-xl p-3 flex items-center gap-3 border border-border-glass/80">
      <button
        onClick={() => stepFrame(-0.08)}
        className="p-2 rounded-lg hover:bg-bg-tertiary transition-colors"
        title="Previous frame (←)"
        type="button"
      >
        <SkipBack size={16} />
      </button>
      <button
        onClick={togglePlay}
        className="p-2.5 rounded-full bg-accent-cyan text-bg-primary hover:opacity-90 transition-opacity"
        title="Play / Pause (Space)"
        type="button"
      >
        {replayPlaying ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
      </button>
      <button
        onClick={() => stepFrame(0.08)}
        className="p-2 rounded-lg hover:bg-bg-tertiary transition-colors"
        title="Next frame (→)"
        type="button"
      >
        <SkipForward size={16} />
      </button>
      <button
        onClick={() => playReplay({ fromStart: true })}
        className="p-2 rounded-lg hover:bg-bg-tertiary transition-colors"
        title="Restart replay"
        type="button"
      >
        <RotateCcw size={16} />
      </button>
      <input
        type="range"
        min={0}
        max={100}
        value={Math.round(replayProgress * 100)}
        onChange={e => {
          seekReplay(Number(e.target.value) / 100, false);
        }}
        className="flex-1 accent-accent-cyan h-1.5"
        aria-label="Replay progress"
      />
      <span className="text-xs font-mono text-text-muted w-10 text-right">
        {Math.round(replayProgress * 100)}%
      </span>
      <span className="hidden md:inline text-[10px] text-text-muted">
        Space · ← → {slowMotion ? '· slow-mo' : ''}
      </span>
      {slowMotion && onResetSlowMo && (
        <button
          onClick={onResetSlowMo}
          className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30"
          type="button"
        >
          Slow-mo
        </button>
      )}
    </div>
  );
}
