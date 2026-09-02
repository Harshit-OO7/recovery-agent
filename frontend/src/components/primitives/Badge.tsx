import React from 'react';
import { cn } from '@/utils/cn';

export type BadgeVariant = 
  | 'recovered' 
  | 'suppressed' 
  | 'waiting' 
  | 'escalated' 
  | 'abandoned' 
  | 'open' 
  | 'neutral' 
  | 'accent';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  pulse?: boolean;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'sm',
  pulse = false,
  className,
}) => {
  const baseStyles = 'inline-flex items-center gap-1 font-mono uppercase font-medium rounded border tracking-wide whitespace-nowrap';

  const variants: Record<BadgeVariant, string> = {
    recovered: 'bg-recovered-subtle text-recovered border-recovered-border',
    suppressed: 'bg-suppressed-subtle text-suppressed border-suppressed-border',
    waiting: 'bg-suppressed-subtle text-suppressed border-suppressed-border',
    escalated: 'bg-dnc-subtle text-dnc border-dnc-border',
    abandoned: 'bg-danger-subtle text-danger border-danger-border',
    open: 'bg-surface-inset text-ink-muted border-border',
    neutral: 'bg-surface-raised text-ink-muted border-border',
    accent: 'bg-accent-subtle text-accent border-accent-border',
  };

  const sizes = {
    sm: 'text-xxs px-1.5 py-0.5',
    md: 'text-xs px-2 py-0.5',
  };

  return (
    <span className={cn(baseStyles, variants[variant], sizes[size], className)}>
      {pulse && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse shrink-0" />
      )}
      {children}
    </span>
  );
};
