import React from 'react';
import { cn } from '@/utils/cn';

export interface StatBlockProps {
  label: string;
  value: string | number;
  subvalue?: string | React.ReactNode;
  secondaryText?: string;
  variant?: 'default' | 'accent' | 'recovered' | 'suppressed';
  className?: string;
}

export const StatBlock: React.FC<StatBlockProps> = ({
  label,
  value,
  subvalue,
  secondaryText,
  variant = 'default',
  className,
}) => {
  const valueColors = {
    default: 'text-ink',
    accent: 'text-accent',
    recovered: 'text-recovered',
    suppressed: 'text-suppressed',
  };

  return (
    <div className={cn('bg-surface p-3.5 rounded border border-border flex flex-col justify-between', className)}>
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-xs text-ink-muted font-medium">{label}</span>
        {subvalue && (
          <span className="text-xxs font-mono font-medium text-ink-muted bg-surface-inset px-1.5 py-0.5 rounded border border-border-subtle">
            {subvalue}
          </span>
        )}
      </div>
      <div className={cn('text-xl font-mono font-semibold tabular-nums tracking-tight', valueColors[variant])}>
        {value}
      </div>
      {secondaryText && (
        <div className="text-xxs text-ink-subtle mt-1 font-sans truncate">
          {secondaryText}
        </div>
      )}
    </div>
  );
};
