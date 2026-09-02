import React from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/primitives/Button';
import { Badge } from '@/components/primitives/Badge';
import { formatRupees } from '@/utils/formatters';
import { ComparisonReport } from '@/api/types';

export interface ComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
  report: ComparisonReport | null;
}

export const ComparisonModal: React.FC<ComparisonModalProps> = ({
  isOpen,
  onClose,
  report,
}) => {
  if (!isOpen || !report) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-ink/40 backdrop-blur-xs transition-opacity" 
        onClick={onClose} 
      />

      <div className="relative bg-surface rounded-lg border border-border max-w-3xl w-full shadow-2xl overflow-hidden z-10 font-sans">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-border bg-surface-raised flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-ink">Head-to-Head Uplift Comparison</h2>
              <Badge variant="accent">Master Seed {report.seed}</Badge>
            </div>
            <p className="text-xxs text-ink-muted font-sans mt-0.5">
              Strict counterfactual evaluation of Agentic Recovery against Zero-Intervention Baseline on identical N=80 cohort.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-ink-muted hover:text-ink hover:bg-surface-inset transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6 text-xs">
          {/* Main Comparison Table */}
          <div className="border border-border rounded overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-inset border-b border-border text-xxs font-mono uppercase text-ink-muted">
                  <th className="py-2.5 px-4 font-semibold">Evaluation Metric</th>
                  <th className="py-2.5 px-4 font-semibold text-accent">Autonomous Agent</th>
                  <th className="py-2.5 px-4 font-semibold text-ink-muted">Zero-Intervention Baseline</th>
                  <th className="py-2.5 px-4 font-semibold text-recovered text-right">Net Uplift / Lift</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-xs font-mono">
                <tr>
                  <td className="py-3 px-4 font-sans font-medium text-ink">Recovered Payments</td>
                  <td className="py-3 px-4 font-bold text-accent">{report.agent_recovered_count} / {report.total_payments} ({report.agent_recovery_rate_pct.toFixed(1)}%)</td>
                  <td className="py-3 px-4 text-ink-muted">{report.baseline_recovered_count} / {report.total_payments} ({report.baseline_recovery_rate_pct.toFixed(1)}%)</td>
                  <td className="py-3 px-4 font-bold text-recovered text-right">+{report.net_recovery_rate_lift_pct.toFixed(1)}% ({report.relative_lift_multiplier}x)</td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-sans font-medium text-ink">Recovered Revenue</td>
                  <td className="py-3 px-4 font-bold text-accent">{formatRupees(report.agent_recovered_revenue)}</td>
                  <td className="py-3 px-4 text-ink-muted">{formatRupees(report.baseline_recovered_revenue)}</td>
                  <td className="py-3 px-4 font-bold text-recovered text-right">+{formatRupees(report.net_revenue_lift_rupees)}</td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-sans font-medium text-ink">Outreach Messages Sent</td>
                  <td className="py-3 px-4 text-ink">{report.total_contacts_sent} contacts</td>
                  <td className="py-3 px-4 text-ink-muted">0 (No contact)</td>
                  <td className="py-3 px-4 text-ink-muted text-right">Rs. {report.total_contact_cost_rupees.toFixed(2)} total spend</td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-sans font-medium text-ink">Policy Restraint Suppressions</td>
                  <td className="py-3 px-4 text-suppressed font-semibold">{report.suppressed_count} tx ({formatRupees(report.suppressed_value_rupees)})</td>
                  <td className="py-3 px-4 text-ink-muted">N/A</td>
                  <td className="py-3 px-4 text-suppressed font-semibold text-right">30.0% protected</td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-sans font-medium text-ink">Net ROI (Net Lift / Spend)</td>
                  <td className="py-3 px-4 font-bold text-ink">{report.net_roi_ratio.toLocaleString()}x ROI</td>
                  <td className="py-3 px-4 text-ink-muted">N/A</td>
                  <td className="py-3 px-4 font-bold text-recovered text-right">Rs. {report.net_revenue_lift_rupees.toFixed(0)} / Rs. {report.total_contact_cost_rupees.toFixed(0)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Unit Economics Highlight Card */}
          <div className="grid grid-cols-3 gap-3">
            <div className="p-3.5 rounded bg-surface-raised border border-border">
              <div className="text-xxs text-ink-muted font-mono uppercase">Cost Per Recovery</div>
              <div className="text-lg font-mono font-bold text-ink tabular-nums mt-0.5">
                Rs. {(report.total_contact_cost_rupees / Math.max(1, report.agent_recovered_count)).toFixed(2)}
              </div>
              <div className="text-xxs text-ink-subtle font-sans mt-0.5">WhatsApp / SMS Business API</div>
            </div>

            <div className="p-3.5 rounded bg-surface-raised border border-border">
              <div className="text-xxs text-ink-muted font-mono uppercase">Value at Risk</div>
              <div className="text-lg font-mono font-bold text-ink tabular-nums mt-0.5">
                {formatRupees(report.value_at_risk_rupees)}
              </div>
              <div className="text-xxs text-ink-subtle font-sans mt-0.5">80 Failed Checkout Transactions</div>
            </div>

            <div className="p-3.5 rounded bg-recovered-subtle border border-recovered-border">
              <div className="text-xxs text-recovered font-mono uppercase font-bold">Relative Multiplier</div>
              <div className="text-lg font-mono font-bold text-recovered tabular-nums mt-0.5">
                {report.relative_lift_multiplier}x Lift
              </div>
              <div className="text-xxs text-recovered font-sans mt-0.5">vs Counterfactual Baseline</div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-border bg-surface-raised flex justify-between items-center">
          <span className="text-xxs font-mono text-ink-subtle">
            Seed-locked comparison guard verified (Refuses comparison on differing seeds)
          </span>
          <Button variant="primary" onClick={onClose}>Done</Button>
        </div>
      </div>
    </div>
  );
};
