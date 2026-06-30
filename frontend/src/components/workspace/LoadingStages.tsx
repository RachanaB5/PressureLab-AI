import { motion, AnimatePresence } from 'motion/react';

const STAGES = [
  'Building Digital Match Twin...',
  'Computing pressure zones...',
  'Reconstructing player positions...',
  'Analysing tactical context...',
  'Consulting IBM Granite...',
  'Preparing coach insights...',
];

export function LoadingStages({ stage }: { stage: number }) {
  const label = STAGES[Math.min(stage, STAGES.length - 1)] ?? STAGES[0];
  return (
    <div className="glass rounded-2xl p-8 flex flex-col items-center justify-center min-h-[280px] gap-4">
      <div className="flex gap-2">
        {STAGES.map((_, i) => (
          <motion.div
            key={i}
            className={`h-1.5 w-8 rounded-full ${i <= stage ? 'bg-accent-cyan' : 'bg-bg-tertiary'}`}
            animate={i === stage ? { opacity: [0.4, 1, 0.4] } : {}}
            transition={{ repeat: Infinity, duration: 1.2 }}
          />
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.p
          key={label}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          className="text-sm text-text-secondary"
        >
          {label}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}
