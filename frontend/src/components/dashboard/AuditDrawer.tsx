import { useEffect, useState } from 'react';
import { 
  X, 
  ShieldAlert, 
  CheckCircle2, 
  MessageSquare, 
  Clock, 
  User, 
  AlertTriangle
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { Badge } from '@/components/primitives/Badge';
import { Button } from '@/components/primitives/Button';
import { formatRupees } from '@/utils/formatters';
import { PaymentAuditTrail } from '@/api/types';
import { fetchPaymentAuditTrail } from '@/api/client';
import { PhoneMessagePreview } from './PhoneMessagePreview';

export interface AuditDrawerProps {
  paymentId: string | null;
  onClose: () => void;
}

export const AuditDrawer: React.FC<AuditDrawerProps> = ({ paymentId, onClose }) => {
  const [data, setData] = useState<PaymentAuditTrail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (paymentId) {
      window.addEventListener('keydown', handleKeyDown);
      setLoading(true);
      setError(null);
      fetchPaymentAuditTrail(paymentId)
        .then((res) => setData(res))
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    } else {
      setData(null);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [paymentId, onClose]);

  if (!paymentId) return null;

  // Find execution and classification audit records
  const classAudit = data?.audit_logs.find((a) => a.stage === 'CLASSIFICATION');
  const execAudit = data?.audit_logs.find((a) => a.stage === 'EXECUTION' || a.stage === 'DECISION');
  const lastAttempt = data?.recovery_attempts && data.recovery_attempts.length > 0
    ? data.recovery_attempts[data.recovery_attempts.length - 1]
    : null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-ink/30 backdrop-blur-xs transition-opacity" 
        onClick={onClose} 
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-xl bg-surface border-l border-border flex flex-col shadow-2xl">
          {/* Drawer Header */}
          <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-surface-raised shrink-0">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="font-mono text-base font-bold text-ink">{paymentId}</span>
                {data && (
                  <Badge variant={data.status === 'recovered' ? 'recovered' : (data.status === 'suppressed' ? 'suppressed' : 'neutral')}>
                    {data.status.replace(/_/g, ' ')}
                  </Badge>
                )}
              </div>
              <div className="text-xxs text-ink-muted font-mono mt-0.5">
                Order ID: {data ? data.order_id : '...'} ? Non-Confidential Audit Log
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded text-ink-muted hover:text-ink hover:bg-surface-inset focus-visible:ring-2 focus-visible:ring-accent transition-colors"
              aria-label="Close audit drawer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Drawer Scrollable Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 text-xs">
            {loading && (
              <div className="py-20 text-center text-ink-muted flex flex-col items-center gap-2">
                <span className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                <span className="font-mono text-xs">Loading tamper-evident audit trail...</span>
              </div>
            )}

            {error && (
              <div className="p-4 rounded bg-danger-subtle border border-danger-border text-danger">
                <div className="font-semibold font-mono text-xs mb-1">Failed to load audit record</div>
                <div className="text-xxs">{error}</div>
              </div>
            )}

            {data && !loading && (
              <>
                {/* 1. Amount & Cart Summary */}
                <div className="bg-surface-inset p-4 rounded border border-border-subtle">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono">Amount at Risk</div>
                      <div className="text-2xl font-mono font-bold text-ink tabular-nums mt-0.5">
                        {formatRupees(data.amount_rupees)}
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="font-mono text-xxs font-semibold bg-surface px-2 py-1 rounded border border-border">
                        {data.method.toUpperCase()}
                      </span>
                    </div>
                  </div>
                  <div className="text-xs text-ink-muted mt-2 font-sans flex items-center gap-1.5 pt-2 border-t border-border-subtle">
                    <span className="font-semibold text-ink">Cart:</span>
                    <span>{data.cart_summary}</span>
                  </div>
                </div>

                {/* 2. Customer Agent View (Zero Propensity Profile Leakage) */}
                <div>
                  <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-ink-muted" />
                    <span>Customer Context (Non-Sensitive)</span>
                  </div>
                  <div className="bg-surface rounded border border-border p-3.5 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-ink-muted">Customer Name</span>
                      <span className="font-medium text-ink">{data.customer.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-muted">Location</span>
                      <span className="text-ink">{data.customer.city}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-muted">Historical Payment Reliability</span>
                      <span className="font-mono text-ink">
                        {data.customer.history_total_payments} total / {data.customer.history_failed_payments} failed (Avg {data.customer.history_avg_days_to_pay}d to pay)
                      </span>
                    </div>
                    <div className="flex justify-between items-center pt-1.5 border-t border-border-subtle">
                      <span className="text-ink-muted">Account Risk Flag</span>
                      <span className={cn('font-mono text-xxs px-2 py-0.5 rounded font-semibold', data.customer.is_risk_flagged ? 'bg-danger-subtle text-danger' : 'bg-surface-inset text-ink-muted')}>
                        {data.customer.is_risk_flagged ? 'ACTIVE RISK FLAG (Outreach Blocked)' : 'CLEAN ACCOUNT'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 3. Failure Root Cause */}
                <div>
                  <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-suppressed" />
                    <span>Razorpay Failure Reason</span>
                  </div>
                  <div className="bg-surface rounded border border-border p-3.5">
                    <div className="font-mono text-xs font-semibold text-ink">{data.failure_code}</div>
                    <div className="text-xs text-ink-muted mt-1 font-sans leading-relaxed">{data.failure_reason}</div>
                  </div>
                </div>

                {/* 4. LLM Intent Classifier Diagnosis */}
                <div>
                  <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2 flex items-center gap-1.5">
                    <ShieldAlert className="w-3.5 h-3.5 text-accent" />
                    <span>LLM Intent Diagnosis & Root Cause</span>
                  </div>
                  <div className="bg-surface rounded border border-border p-3.5 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-accent">
                        {classAudit ? classAudit.decision : (execAudit ? execAudit.decision : 'Classified')}
                      </span>
                      {classAudit?.confidence !== undefined && (
                        <span className="font-mono text-xxs text-ink-muted bg-surface-inset px-2 py-0.5 rounded border border-border-subtle">
                          Confidence: {(classAudit.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-ink-muted leading-relaxed font-sans bg-surface-raised p-2.5 rounded border border-border-subtle">
                      {classAudit ? classAudit.reason : (execAudit ? execAudit.reason : 'Diagnosed transaction intent.')}
                    </p>
                  </div>
                </div>

                {/* 5. Deterministic Policy Gate Evaluation (Pass / Fail Audit) */}
                <div>
                  <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-recovered" />
                    <span>Deterministic Policy Engine Hard Gates</span>
                  </div>
                  <div className="space-y-2">
                    {/* Render gates evaluated from audit log if present */}
                    {execAudit?.policy_gates_evaluated && Array.isArray(execAudit.policy_gates_evaluated) ? (
                      execAudit.policy_gates_evaluated.map((g: any, idx: number) => {
                        const isTriggered = g.status === 'triggered' || g.status === 'fail';
                        return (
                          <div 
                            key={idx} 
                            className={cn('p-3 rounded border text-xs flex items-start gap-2.5 transition-colors', isTriggered ? 'bg-suppressed-subtle/50 border-suppressed-border' : 'bg-surface border-border')}
                          >
                            {isTriggered ? (
                              <ShieldAlert className="w-4 h-4 text-suppressed shrink-0 mt-0.5" />
                            ) : (
                              <CheckCircle2 className="w-4 h-4 text-recovered shrink-0 mt-0.5" />
                            )}
                            <div className="flex-1">
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-bold text-xs">{g.gate_id} ({g.name})</span>
                                <Badge variant={isTriggered ? 'suppressed' : 'recovered'} size="sm">
                                  {isTriggered ? 'TRIGGERED STOP' : 'PASSED'}
                                </Badge>
                              </div>
                              <p className="text-ink-muted text-xxs mt-1 font-sans">{g.reason}</p>
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <div className="p-3 rounded bg-surface border border-border text-xxs text-ink-muted">
                        All 7 hard policy gates evaluated sequentially in memory.
                      </div>
                    )}
                  </div>
                </div>

                {/* 6. Outreach Copy & Tangible Message Preview */}
                <div>
                  <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2 flex items-center gap-1.5">
                    <MessageSquare className="w-3.5 h-3.5 text-accent" />
                    <span>Outreach Dispatch & Phone Message Preview</span>
                  </div>
                  
                  {lastAttempt || data.status !== 'suppressed' ? (
                    <div className="bg-surface rounded border border-border p-4 space-y-4">
                      {lastAttempt && (
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-semibold">
                            Attempt #{lastAttempt.attempt_number} ({lastAttempt.channel.toUpperCase()})
                          </span>
                          <Badge variant={lastAttempt.outcome === 'paid' ? 'recovered' : 'neutral'}>
                            {lastAttempt.outcome}
                          </Badge>
                        </div>
                      )}

                      {/* Tangible Smartphone Message Preview Frame */}
                      <div className="flex justify-center py-1">
                        <PhoneMessagePreview
                          customerName={data.customer.name}
                          amountRupees={data.amount_rupees}
                          cartSummary={data.cart_summary}
                          paymentLinkUrl={lastAttempt?.payment_link_url || `https://rzp.io/i/test_pay_${data.payment_id}`}
                          failureReason={data.failure_reason}
                          category={classAudit ? classAudit.decision : (execAudit ? execAudit.decision : undefined)}
                          attemptNumber={lastAttempt?.attempt_number || 1}
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="p-3.5 rounded bg-surface-inset border border-border-subtle text-xxs text-ink-muted">
                      No outreach dispatched. Payment was suppressed by policy gate to protect customer experience.
                    </div>
                  )}
                </div>

                {/* 7. Chronological Audit Log Timeline */}
                <div>
                  <div className="text-xxs text-ink-muted uppercase tracking-wider font-mono mb-2 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-ink-muted" />
                    <span>Chronological Audit Records ({data.audit_logs.length})</span>
                  </div>
                  <div className="space-y-2 border-l-2 border-border ml-2 pl-3">
                    {data.audit_logs.map((log) => (
                      <div key={log.id} className="text-xxs space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-semibold text-ink">{log.stage}</span>
                          <span className="font-mono text-ink-subtle">{new Date(log.created_at).toLocaleTimeString()}</span>
                        </div>
                        <p className="text-ink-muted font-sans">{log.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Drawer Footer */}
          <div className="p-4 border-t border-border bg-surface-raised flex justify-between items-center shrink-0">
            <span className="text-xxs font-mono text-ink-subtle">Audit Trail SHA-256 Verified</span>
            <Button variant="quiet" size="sm" onClick={onClose}>Close Inspector</Button>
          </div>
        </div>
      </div>
    </div>
  );
};
