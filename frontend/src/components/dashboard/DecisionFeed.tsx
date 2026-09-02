import React from 'react';
import { Play, Sparkles } from 'lucide-react';
import { cn } from '@/utils/cn';
import { Badge, BadgeVariant } from '@/components/primitives/Badge';
import { Button } from '@/components/primitives/Button';
import { formatRupees } from '@/utils/formatters';
import { SSEEventData } from '@/api/types';

export interface DecisionFeedProps {
  events: SSEEventData[];
  selectedPaymentId: string | null;
  onSelectRow: (paymentId: string) => void;
  isRunning: boolean;
  onStartRun: () => void;
  mode: 'agent' | 'baseline';
}

export const DecisionFeed: React.FC<DecisionFeedProps> = ({
  events,
  selectedPaymentId,
  onSelectRow,
  isRunning,
  onStartRun,
  mode,
}) => {
  const statusVariantMap: Record<string, BadgeVariant> = {
    recovered: 'recovered',
    paid: 'recovered',
    suppressed: 'suppressed',
    waiting: 'waiting',
    in_progress: 'waiting',
    escalated: 'escalated',
    abandoned: 'abandoned',
    open: 'open',
  };

  const recoveredCount = events.filter((e) => e.status === 'recovered' || e.outcome === 'paid').length;
  const suppressedCount = events.filter((e) => e.status === 'suppressed' || e.decision?.action === 'suppress').length;

  return (
    <main className="flex-1 bg-surface flex flex-col overflow-hidden min-w-0">
      {/* Feed Header with Live Counts */}
      <div className="px-5 py-3 border-b border-border bg-surface-raised flex items-center justify-between shrink-0">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-xs font-semibold text-ink">Live Decision Ledger</h2>
            {events.length > 0 && (
              <span className="font-mono text-xxs font-semibold bg-surface px-2 py-0.5 rounded border border-border text-ink">
                {events.length} / 80 Processed
              </span>
            )}
            {isRunning && (
              <span className="flex items-center gap-1.5 font-mono text-xxs text-accent bg-accent-subtle px-2 py-0.5 rounded border border-accent-border animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                <span>STREAMING SSE</span>
              </span>
            )}
          </div>
          <p className="text-xxs text-ink-muted font-sans mt-0.5">
            Real-time post-checkout evaluation feed. Click any row to inspect tamper-evident audit records.
          </p>
        </div>

        {events.length > 0 && (
          <div className="flex items-center gap-2 text-xxs font-mono">
            <span className="text-recovered font-semibold">{recoveredCount} Recovered</span>
            <span className="text-ink-subtle">?</span>
            <span className="text-suppressed font-semibold">{suppressedCount} Suppressed</span>
          </div>
        )}
      </div>

      {/* Column Headers */}
      <div className="flex items-center justify-between gap-3 px-4 py-2 bg-surface-inset border-b border-border text-xxs font-mono uppercase tracking-wider text-ink-muted select-none shrink-0">
        <div className="w-1/6">Transaction / Customer</div>
        <div className="w-1/6 text-right">Amount / Order</div>
        <div className="w-1/5">Failure Code & Reason</div>
        <div className="w-1/4">Classified Intent & Action</div>
        <div className="w-1/6 text-right">Outcome</div>
      </div>

      {/* Feed Body */}
      <div className="flex-1 overflow-y-auto divide-y divide-border">
        {events.length === 0 ? (
          /* Empty State */
          <div className="h-full flex flex-col items-center justify-center p-8 text-center">
            <div className="max-w-md p-6 bg-surface-raised rounded border border-border space-y-3">
              <div className="w-9 h-9 rounded bg-accent-subtle text-accent flex items-center justify-center mx-auto">
                <Sparkles className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-xs text-ink">Ready to Start Revenue Recovery</h3>
              <p className="text-xs text-ink-muted font-sans leading-relaxed">
                Pressing <span className="font-semibold text-ink font-mono">Run Recovery Batch</span> will autonomously ingest 80 failed post-checkout transactions, diagnose failure causes via LLM intent classification, and evaluate 7 deterministic policy gates before creating 1-click Razorpay test payment links.
              </p>
              <div className="pt-2">
                <Button variant="primary" size="md" onClick={onStartRun} icon={<Play className="w-3.5 h-3.5" />}>
                  Run Recovery Batch (80 Tx)
                </Button>
              </div>
            </div>
          </div>
        ) : (
          events.map((e, idx) => {
            const rawStatus = e.status || e.outcome || 'open';
            const statusVariant = statusVariantMap[rawStatus.toLowerCase()] || 'neutral';
            const isSelected = selectedPaymentId === e.payment_id;

            return (
              <div
                key={e.payment_id || idx}
                onClick={() => e.payment_id && onSelectRow(e.payment_id)}
                className={cn(
                  'group flex items-center justify-between gap-3 px-4 py-2.5 bg-surface border-b border-border hover:bg-surface-raised cursor-pointer transition-colors select-none text-xs',
                  isSelected && 'bg-accent-subtle/50 border-l-2 border-l-accent',
                  e.state === 'classifying' && 'animate-pulse bg-accent-subtle/20',
                  idx === events.length - 1 && 'animate-fadeIn'
                )}
                role="row"
                tabIndex={0}
                onKeyDown={(ev) => ev.key === 'Enter' && e.payment_id && onSelectRow(e.payment_id)}
              >
                {/* 1. Transaction ID & Customer */}
                <div className="flex flex-col w-1/6 truncate">
                  <span className="font-mono text-xs font-bold text-ink group-hover:text-accent transition-colors truncate">
                    {e.payment_id || `pay_${idx + 1000}`}
                  </span>
                  <span className="text-xxs text-ink-muted truncate font-sans">
                    {e.customer_name || 'Customer'} {e.customer_city ? `(${e.customer_city})` : ''}
                  </span>
                </div>

                {/* 2. Amount & Order */}
                <div className="flex flex-col w-1/6 text-right">
                  <span className="font-mono text-xs font-semibold tabular-nums text-ink">
                    {formatRupees(e.amount_rupees || 0)}
                  </span>
                  <div className="flex items-center justify-end gap-1 text-xxs font-mono text-ink-subtle truncate">
                    <span className="bg-surface-inset px-1 rounded border border-border-subtle text-ink-muted">
                      {(e.method || 'UPI').toUpperCase()}
                    </span>
                    <span className="truncate">{e.order_id}</span>
                  </div>
                </div>

                {/* 3. Failure Reason */}
                <div className="flex flex-col w-1/5 truncate">
                  <span className="font-mono text-xxs font-semibold text-ink-muted truncate">
                    {e.failure_code || 'GATEWAY_ERROR'}
                  </span>
                  <span className="text-xxs text-ink-subtle font-sans truncate" title={e.failure_reason}>
                    {e.failure_reason || 'Checkout failure'}
                  </span>
                </div>

                {/* 4. Intent Classification & Gate Action */}
                <div className="flex flex-col w-1/4 truncate">
                  {e.classification?.category ? (
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="font-mono text-xxs text-accent font-semibold truncate">
                        {e.classification.category}
                      </span>
                      {e.classification.confidence !== undefined && (
                        <span className="font-mono text-xxs text-ink-subtle">
                          {(e.classification.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xxs text-ink-subtle font-mono">
                      {mode === 'baseline' ? 'Baseline (No LLM)' : 'Classifying...'}
                    </span>
                  )}

                  {e.decision?.action ? (
                    <span className="text-xxs text-ink-muted font-sans truncate">
                      Action: {e.decision.action.replace(/_/g, ' ')}
                    </span>
                  ) : (
                    <span className="text-xxs text-ink-subtle font-sans truncate">
                      {e.decision?.reason || 'Evaluating gates...'}
                    </span>
                  )}
                </div>

                {/* 5. Outcome Badge */}
                <div className="flex items-center justify-end w-1/6">
                  <Badge 
                    variant={statusVariant} 
                    size="sm"
                    pulse={rawStatus === 'in_progress' || rawStatus === 'waiting' || e.state === 'classifying'}
                  >
                    {rawStatus.replace(/_/g, ' ')}
                  </Badge>
                </div>
              </div>
            );
          })
        )}
      </div>
    </main>
  );
};
