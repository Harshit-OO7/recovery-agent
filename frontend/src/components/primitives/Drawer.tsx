import React, { useEffect } from 'react';
import { X, ExternalLink, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { cn } from '@/utils/cn';
import { Badge } from './Badge';
import { Button } from './Button';
import { formatRupees } from '@/utils/formatters';

export interface DrawerData {
  paymentId: string;
  orderId: string;
  amountRupees: number;
  status: string;
  failedAt: string;
  cartSummary: string;
  failureCode: string;
  failureReason: string;
  customer: {
    name: string;
    phone: string;
    email: string;
    city: string;
    historyTotalPayments: number;
    historyFailedPayments: number;
    isRiskFlagged: boolean;
  };
  classification?: {
    category: string;
    confidence: number;
    reasoning: string;
    signalsUsed: string[];
  };
  gatesEvaluated?: Array<{
    gateId: string;
    name: string;
    status: string;
    reason: string;
  }>;
  recoveryAttempts?: Array<{
    attemptNumber: number;
    actionTaken: string;
    paymentLinkUrl?: string;
    outcome: string;
    sentAt: string;
  }>;
}

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  data: DrawerData | null;
}

export const Drawer: React.FC<DrawerProps> = ({ isOpen, onClose, data }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !data) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-ink/30 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-surface border-l border-border flex flex-col shadow-xl">
          {/* Header */}
          <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface-raised">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold text-ink">{data.paymentId}</span>
                <Badge variant={data.status === 'recovered' ? 'recovered' : (data.status === 'suppressed' ? 'suppressed' : 'neutral')}>
                  {data.status}
                </Badge>
              </div>
              <div className="text-xxs text-ink-muted font-mono mt-0.5">Order: {data.orderId}</div>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded text-ink-muted hover:text-ink hover:bg-surface-inset focus-visible:ring-2 focus-visible:ring-accent"
              aria-label="Close drawer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs">
            {/* Amount & Cart */}
            <div className="bg-surface-inset p-3.5 rounded border border-border-subtle">
              <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-1">Amount & Cart</div>
              <div className="text-xl font-mono font-bold text-ink tabular-nums">{formatRupees(data.amountRupees)}</div>
              <div className="text-xs text-ink-muted mt-1 font-sans">{data.cartSummary}</div>
            </div>

            {/* Customer Profile */}
            <div>
              <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2">Customer Profile (Non-Sensitive)</div>
              <div className="bg-surface rounded border border-border p-3 space-y-1.5">
                <div className="flex justify-between"><span className="text-ink-muted">Name</span><span className="font-medium text-ink">{data.customer.name}</span></div>
                <div className="flex justify-between"><span className="text-ink-muted">Contact</span><span className="font-mono text-ink">{data.customer.phone}</span></div>
                <div className="flex justify-between"><span className="text-ink-muted">City</span><span className="text-ink">{data.customer.city}</span></div>
                <div className="flex justify-between"><span className="text-ink-muted">Payment History</span><span className="font-mono text-ink">{data.customer.historyTotalPayments} total / {data.customer.historyFailedPayments} failed</span></div>
                <div className="flex justify-between items-center">
                  <span className="text-ink-muted">Risk Flagged</span>
                  <span className={cn('font-mono text-xxs px-1.5 py-0.5 rounded font-medium', data.customer.isRiskFlagged ? 'bg-danger-subtle text-danger' : 'bg-surface-inset text-ink-muted')}>
                    {data.customer.isRiskFlagged ? 'YES (Suppressed)' : 'NO'}
                  </span>
                </div>
              </div>
            </div>

            {/* Failure Reason */}
            <div>
              <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2">Failure Reason</div>
              <div className="bg-surface rounded border border-border p-3">
                <div className="font-mono text-xxs text-ink font-semibold">{data.failureCode}</div>
                <div className="text-xs text-ink-muted mt-0.5 font-sans">{data.failureReason}</div>
              </div>
            </div>

            {/* Intent Diagnosis */}
            {data.classification && (
              <div>
                <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2">LLM Intent Diagnosis</div>
                <div className="bg-surface rounded border border-border p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-accent font-semibold">{data.classification.category}</span>
                    <span className="font-mono text-xxs text-ink-muted">Confidence: {(data.classification.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <p className="text-xs text-ink-muted leading-relaxed font-sans">{data.classification.reasoning}</p>
                </div>
              </div>
            )}

            {/* Policy Gates Evaluation */}
            {data.gatesEvaluated && data.gatesEvaluated.length > 0 && (
              <div>
                <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2">Deterministic Gates Evaluated</div>
                <div className="space-y-1.5">
                  {data.gatesEvaluated.map((g) => (
                    <div key={g.gateId} className={cn('p-2.5 rounded border text-xs flex items-start gap-2', g.status === 'triggered' ? 'bg-suppressed-subtle/50 border-suppressed-border' : 'bg-surface border-border')}>
                      {g.status === 'triggered' ? (
                        <ShieldAlert className="w-3.5 h-3.5 text-suppressed shrink-0 mt-0.5" />
                      ) : (
                        <CheckCircle2 className="w-3.5 h-3.5 text-recovered shrink-0 mt-0.5" />
                      )}
                      <div>
                        <span className="font-mono font-semibold mr-1.5">{g.gateId} ({g.name}):</span>
                        <span className="text-ink-muted">{g.reason}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Generated Payment Link */}
            {data.recoveryAttempts && data.recoveryAttempts.length > 0 && (
              <div>
                <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2">Outreach & Payment Links</div>
                <div className="space-y-2">
                  {data.recoveryAttempts.map((att) => (
                    <div key={att.attemptNumber} className="bg-surface rounded border border-border p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold">Attempt #{att.attemptNumber}</span>
                        <Badge variant={att.outcome === 'paid' ? 'recovered' : 'neutral'}>{att.outcome}</Badge>
                      </div>
                      {att.paymentLinkUrl && (
                        <a
                          href={att.paymentLinkUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 font-mono text-xs text-accent hover:underline bg-accent-subtle px-2 py-1 rounded border border-accent-border truncate w-full"
                        >
                          <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{att.paymentLinkUrl}</span>
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-border bg-surface-raised flex justify-end">
            <Button variant="quiet" onClick={onClose}>Close Inspector</Button>
          </div>
        </div>
      </div>
    </div>
  );
};
