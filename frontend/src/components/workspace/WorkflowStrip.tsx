import { Search, Play, Monitor, Brain, GraduationCap } from 'lucide-react';

const STEPS = [
  { icon: Search, label: 'Choose match' },
  { icon: Play, label: 'Choose event' },
  { icon: Monitor, label: 'Replay moment' },
  { icon: Brain, label: 'Understand why' },
  { icon: GraduationCap, label: 'Learn from coaches' },
];

export function WorkflowStrip({ active = 2 }: { active?: number }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {STEPS.map((s, i) => (
        <div key={s.label} className="flex items-center gap-2">
          <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-colors ${
            i === active
              ? 'border-accent-cyan bg-accent-cyan/10 text-accent-cyan'
              : i < active
                ? 'border-accent-blue/30 text-text-secondary'
                : 'border-border-glass text-text-muted'
          }`}>
            <s.icon size={12} />
            {s.label}
          </span>
          {i < STEPS.length - 1 && <span className="text-text-muted hidden sm:inline">→</span>}
        </div>
      ))}
    </div>
  );
}
