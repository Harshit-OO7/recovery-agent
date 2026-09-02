import React, { useState } from 'react';
import { ShieldAlert, ChevronDown, ChevronUp } from 'lucide-react';
import { Badge } from '@/components/primitives/Badge';
import { formatRupees } from '@/utils/formatters';
import { ExceptionsResponse } from '@/api/types';

export interface ExceptionsTableProps {
  exceptions: ExceptionsResponse | null;
  onSelectPayment: (paymentId: string) => void;
}

export const ExceptionsTable: React.FC<ExceptionsTableProps> = ({
  exceptions,
  onSelectPayment,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);

  if (!exceptions || exceptions.items.length === 0) {
    return null;
  }

  return (
    <div className="border-t border-border bg-surface shrink-0 select-none">
      {/* Expandable Section Header */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-5 py-2.5 bg-surface-raised flex items-center justify-between cursor-pointer hover:bg-surface-inset transition-colors border-b border-border"
      >
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-3.5 h-3.5 text-suppressed" />
          <h3 className="text-xs font-semibold text-ink">
            Exceptions & Suppressions ({exceptions.total_exceptions})
          </h3>
          <span className="text-xxs font-mono text-ink-muted bg-surface px-1.5 py-0.5 rounded border border-border">
            Protected: {formatRupees(exceptions.total_suppressed_value_rupees)}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xxs font-mono text-ink-muted">
          <span>{exceptions.total_suppressed} Suppressed ? {exceptions.total_escalated} Escalated</span>
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
        </div>
      </div>

      {/* Table Content */}
      {isExpanded && (
        <div className="max-h-48 overflow-y-auto divide-y divide-border-subtle text-xs">
          {exceptions.items.map((item) => (
            <div
              key={item.payment_id}
              onClick={() => onSelectPayment(item.payment_id)}
              className="flex items-center justify-between gap-3 px-5 py-2 hover:bg-surface-raised cursor-pointer transition-colors"
            >
              <div className="flex items-center gap-2.5 w-1/5 truncate">
                <span className="font-mono text-xs font-semibold text-ink truncate">{item.payment_id}</span>
                <Badge variant={item.type === 'SUPPRESSION' ? 'suppressed' : 'escalated'} size="sm">
                  {item.type}
                </Badge>
              </div>

              <div className="w-1/6 font-mono text-xs font-medium text-ink tabular-nums text-right">
                {formatRupees(item.amount_rupees)}
              </div>

              <div className="w-1/6 font-mono text-xxs text-ink-muted truncate">
                {item.gate_triggered || 'Policy Gate'}
              </div>

              <div className="flex-1 text-xxs text-ink-muted font-sans truncate" title={item.reason}>
                {item.reason}
              </div>

              <div className="text-xxs font-mono text-accent hover:underline shrink-0">
                Inspect Audit ?
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
