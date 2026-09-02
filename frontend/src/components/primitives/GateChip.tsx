import React from 'react';
import { cn } from '@/utils/cn';

export interface GateChipProps {
  gateId: string;
  name?: string;
  status: 'passed' | 'triggered' | 'skipped' | 'pending';
  compact?: boolean;
  className?: string;
}

export const GateChip: React.FC<GateChipProps> = ({
  gateId,
  name,
  status,
  compact = false,
  className,
}) => {
  const statusConfig = {
    passed: {
      bg: 'bg-surface text-ink-muted border-border',
      indicator: 'bg-recovered',
    },
    triggered: {
      bg: 'bg-suppressed-subtle text-suppressed border-suppressed-border font-semibold',
      indicator: 'bg-suppressed',
    },
    skipped: {
      bg: 'bg-surface-inset text-ink-subtle border-border-subtle opacity-60',
      indicator: 'bg-ink-subtle',
    },
    pending: {
      bg: 'bg-surface text-ink-subtle border-border',
      indicator: 'bg-border-strong',
    },
  };

  const current = statusConfig[status];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded border font-mono text-xxs px-1.5 py-0.5 transition-colors',
        current.bg,
        className
      )}
      title={name ? `${gateId}: ${name} (${status})` : `${gateId} (${status})`}
    >
      <span className={cn('w-1 h-1 rounded-full shrink-0', current.indicator)} />
      <span className="tracking-tight">{gateId}</span>
      {!compact && name && (
        <span className="font-sans font-normal text-ink-muted truncate max-w-[100px]">
          {name}
        </span>
      )}
    </span>
  );
};
