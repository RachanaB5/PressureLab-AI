import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { Target, Zap, Crosshair, Circle, ChevronLeft, ChevronRight } from 'lucide-react';

const EVENT_ICONS: Record<string, typeof Target> = {
  Goal: Target,
  Shot: Crosshair,
  Card: Circle,
  Substitution: Circle,
  Press: Zap,
};

type Event = {
  id: number;
  minute: number;
  type: string;
  player: string;
  xg?: number;
  pressure?: number;
  momentum?: number;
  confidence?: number;
};

export function InteractiveTimeline({
  events,
  selectedId,
  onSelect,
  onHover,
  onSlowMotion,
}: {
  events: Event[];
  selectedId: number | null;
  onSelect: (ev: Event) => void;
  onHover?: (ev: Event | null) => void;
  onSlowMotion?: (ev: Event) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);
  const [hoverId, setHoverId] = useState<number | null>(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }, [selectedId]);

  const idx = events.findIndex(e => e.id === selectedId);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>Click replay · Double-click slow-mo · ← → scrub</span>
        <span>{idx >= 0 ? `${idx + 1} / ${events.length}` : ''}</span>
      </div>
      <div ref={scrollRef} className="flex gap-3 overflow-x-auto pb-3 scrollbar-thin snap-x">
        {events.map(ev => {
          const Icon = EVENT_ICONS[ev.type] ?? Target;
          const active = selectedId === ev.id;
          const hovered = hoverId === ev.id;
          return (
            <motion.button
              key={ev.id}
              ref={active ? selectedRef : undefined}
              onClick={() => onSelect(ev)}
              onDoubleClick={() => {
                onSelect(ev);
                onSlowMotion?.(ev);
              }}
              onMouseEnter={() => { setHoverId(ev.id); onHover?.(ev); }}
              onMouseLeave={() => { setHoverId(null); onHover?.(null); }}
              whileHover={{ scale: 1.03, y: -4 }}
              className={`snap-center flex-shrink-0 w-36 rounded-xl border text-left overflow-hidden transition-shadow ${
                active
                  ? 'border-accent-cyan bg-accent-cyan/15 shadow-lg shadow-accent-cyan/25'
                  : hovered
                    ? 'border-accent-blue/50 glass shadow-md'
                    : 'border-border-glass glass glass-hover'
              }`}
            >
              <div className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs text-text-muted">{ev.minute}'</span>
                  <Icon size={14} className={active ? 'text-accent-cyan' : 'text-text-muted'} />
                </div>
                <div className="font-semibold text-sm">{ev.type}</div>
                <div className="text-xs text-text-secondary truncate mt-0.5">{ev.player}</div>
                <motion.div animate={{ height: active || hovered ? 'auto' : 0, opacity: active || hovered ? 1 : 0 }}
                  className="overflow-hidden">
                  <div className="grid grid-cols-2 gap-1 mt-2 pt-2 border-t border-border-glass/50 text-[10px]">
                    {ev.xg != null && <span>xG {ev.xg}</span>}
                    {ev.pressure != null && <span>Press {ev.pressure}</span>}
                  </div>
                </motion.div>
              </div>
              {(active || hovered) && (
                <motion.div layoutId={active ? 'tl-active' : undefined}
                  className="h-0.5 bg-gradient-to-r from-accent-cyan to-accent-blue" />
              )}
            </motion.button>
          );
        })}
      </div>
      <div className="flex gap-2 justify-center">
        <button disabled={idx <= 0} onClick={() => idx > 0 && onSelect(events[idx - 1])}
          className="p-2 rounded-lg glass disabled:opacity-30"><ChevronLeft size={16} /></button>
        <button disabled={idx >= events.length - 1} onClick={() => idx < events.length - 1 && onSelect(events[idx + 1])}
          className="p-2 rounded-lg glass disabled:opacity-30"><ChevronRight size={16} /></button>
      </div>
    </div>
  );
}
