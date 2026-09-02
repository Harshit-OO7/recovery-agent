import React from 'react';
import { cn } from '@/utils/cn';
import { Badge, BadgeVariant } from './Badge';
import { formatRupees } from '@/utils/formatters';

export interface LedgerRowData {
  paymentId: string;
  orderId: string;
  amountRupees: number;
  customerName: string;
  customerCity?: string;
  failureCode: string;
  failureReason: string;
  category?: string;
  decisionAction?: string;
  status: string;
  paymentLinkUrl?: string;
  isSelected?: boolean;
}

export interface RowProps {
  data: LedgerRowData;
  onClick?: (data: LedgerRowData) => void;
  isNew?: boolean;
  className?: string;
}

export const Row: React.FC<RowProps> = ({
  data,
  onClick,
  isNew = false,
  className,
}) => {
  const statusVariantMap: Record<string, BadgeVariant> = {
    recovered: 'recovered',
    suppressed: 'suppressed',
    waiting: 'waiting',
    in_progress: 'waiting',
    escalated: 'escalated',
    abandoned: 'abandoned',
    open: 'open',
  };

  const statusVariant = statusVariantMap[data.status.toLowerCase()] || 'neutral';

  return (
    <div
      onClick={() => onClick?.(data)}
      className={cn(
        'group flex items-center justify-between gap-4 px-4 py-3 bg-surface border-b border-border hover:bg-surface-raised cursor-pointer transition-colors select-none text-xs',
        data.isSelected && 'bg-accent-subtle/50 border-l-2 border-l-accent',
        isNew && 'animate-fadeIn',
        className
      )}
      role="row"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick?.(data)}
    >
      {/* 1. Transaction ID & Customer */}
      <div className="flex flex-col min-w-[150px] w-1/5">
        <span className="font-mono text-xs font-semibold text-ink group-hover:text-accent transition-colors truncate">
          {data.paymentId}
        </span>
        <span className="text-xxs text-ink-muted truncate font-sans">
          {data.customerName} {data.customerCity ? `(${data.customerCity})` : ''}
        </span>
      </div>

      {/* 2. Amount (Monospace Tabular Figured) */}
      <div className="flex flex-col min-w-[100px] w-1/6 text-right">
        <span className="font-mono text-xs font-semibold tabular-nums text-ink">
          {formatRupees(data.amountRupees)}
        </span>
        <span className="text-xxs text-ink-subtle font-mono truncate">
          {data.orderId}
        </span>
      </div>

      {/* 3. Failure Reason */}
      <div className="flex flex-col min-w-[160px] w-1/4">
        <span className="font-mono text-xxs font-medium text-ink-muted truncate">
          {data.failureCode}
        </span>
        <span className="text-xxs text-ink-subtle font-sans truncate" title={data.failureReason}>
          {data.failureReason}
        </span>
      </div>

      {/* 4. Intent Classification & Policy Gate Action */}
      <div className="flex flex-col min-w-[130px] w-1/5">
        {data.category ? (
          <span className="text-xxs font-mono text-accent font-medium truncate">
            {data.category}
          </span>
        ) : (
          <span className="text-xxs text-ink-subtle font-mono">?</span>
        )}
        {data.decisionAction && (
          <span className="text-xxs text-ink-muted font-sans truncate">
            {data.decisionAction.replace(/_/g, ' ')}
          </span>
        )}
      </div>

      {/* 5. Status Badge */}
      <div className="flex items-center justify-end min-w-[90px]">
        <Badge variant={statusVariant} size="sm" pulse={data.status === 'in_progress' || data.status === 'waiting'}>
          {data.status.replace(/_/g, ' ')}
        </Badge>
      </div>
    </div>
  );
};
