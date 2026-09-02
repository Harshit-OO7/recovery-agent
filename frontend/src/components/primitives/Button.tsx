import React from 'react';
import { cn } from '@/utils/cn';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'quiet' | 'subtle' | 'danger' | 'outline';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  loading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  className,
  variant = 'quiet',
  size = 'sm',
  icon,
  iconPosition = 'left',
  loading = false,
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed select-none';

  const variants = {
    primary: 'bg-accent text-white hover:bg-accent-hover active:bg-accent-hover shadow-sm border border-accent-hover',
    quiet: 'bg-surface text-ink border border-border hover:bg-surface-raised active:bg-surface-inset',
    subtle: 'bg-transparent text-ink-muted hover:text-ink hover:bg-surface-inset',
    danger: 'bg-danger-subtle text-danger border border-danger-border hover:bg-danger/10',
    outline: 'bg-transparent text-accent border border-accent-border hover:bg-accent-subtle',
  };

  const sizes = {
    xs: 'text-xxs px-2 py-1 gap-1 h-6 font-mono',
    sm: 'text-xs px-2.5 py-1.5 gap-1.5 h-8',
    md: 'text-sm px-3.5 py-2 gap-2 h-9',
    lg: 'text-base px-4 py-2.5 gap-2 h-10',
  };

  return (
    <button
      className={cn(baseStyles, variants[variant], sizes[size], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        icon && iconPosition === 'left' && <span className="shrink-0">{icon}</span>
      )}
      <span>{children}</span>
      {!loading && icon && iconPosition === 'right' && <span className="shrink-0">{icon}</span>}
    </button>
  );
};
