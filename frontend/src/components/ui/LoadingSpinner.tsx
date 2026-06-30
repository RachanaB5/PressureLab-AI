import type React from 'react';
import { motion } from 'motion/react';

interface LoadingSpinnerProps {
  size?: number;
  text?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ size = 40, text }) => {
  return (
    <div className="flex flex-col items-center gap-3">
      <motion.div
        className="rounded-full border-2 border-bg-tertiary"
        style={{
          width: size,
          height: size,
          borderTopColor: 'var(--color-accent-cyan)',
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      />
      {text && <span className="text-sm text-text-secondary">{text}</span>}
    </div>
  );
};
