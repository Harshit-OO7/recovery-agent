import { useState } from 'react';
import { 
  Play, 
  RotateCcw, 
  Sliders, 
  ShieldCheck, 
  Info
} from 'lucide-react';
import { Button } from '@/components/primitives/Button';
import { Badge } from '@/components/primitives/Badge';
import { GateChip } from '@/components/primitives/GateChip';
import { StatBlock } from '@/components/primitives/StatBlock';
import { Row, LedgerRowData } from '@/components/primitives/Row';
import { Drawer, DrawerData } from '@/components/primitives/Drawer';

// Sample realistic transaction ledger entries
const SAMPLE_ROWS: LedgerRowData[] = [
  {
    paymentId: 'pay_1001',
    orderId: 'order_1001',
    amountRupees: 2499.00,
    customerName: 'Harshit Sharma',
    customerCity: 'Bengaluru',
    failureCode: 'GATEWAY_TIMEOUT',
    failureReason: 'Bank gateway timed out during processing',
    category: 'technical_failure',
    decisionAction: 'send_payment_link',
    status: 'recovered',
    paymentLinkUrl: 'https://rzp.io/i/test_rec_pay_1001_att1',
  },
  {
    paymentId: 'pay_1002',
    orderId: 'order_1002',
    amountRupees: 899.00,
    customerName: 'Priya Iyer',
    customerCity: 'Chennai',
    failureCode: 'PAYMENT_FAILED_AUTH',
    failureReason: 'OTP verification expired after 300s',
    category: 'authentication_drop',
    decisionAction: 'send_payment_link',
    status: 'recovered',
    paymentLinkUrl: 'https://rzp.io/i/test_rec_pay_1002_att1',
  },
  {
    paymentId: 'pay_1003',
    orderId: 'order_1003',
    amountRupees: 18450.00,
    customerName: 'Vikram Singh',
    customerCity: 'Jaipur',
    failureCode: 'CARD_LIMIT_EXCEEDED',
    failureReason: 'Customer account flagged for high chargeback risk',
    category: 'do_not_pursue',
    decisionAction: 'suppress',
    status: 'suppressed',
  },
  {
    paymentId: 'pay_1004',
    orderId: 'order_1004',
    amountRupees: 65.00,
    customerName: 'Rohan Gupta',
    customerCity: 'Delhi',
    failureCode: 'CHECKOUT_ABANDONED',
    failureReason: 'User exited checkout at UPI QR screen',
    category: 'intent_hesitation',
    decisionAction: 'suppress',
    status: 'suppressed',
  },
  {
    paymentId: 'pay_1005',
    orderId: 'order_1005',
    amountRupees: 4200.00,
    customerName: 'Ananya Deshmukh',
    customerCity: 'Mumbai',
    failureCode: 'INSUFFICIENT_FUNDS',
    failureReason: 'Account balance below checkout threshold',
    category: 'insufficient_funds',
    decisionAction: 'wait_salary_cycle',
    status: 'waiting',
  },
  {
    paymentId: 'pay_1006',
    orderId: 'order_1006',
    amountRupees: 12500.00,
    customerName: 'Kavita Menon',
    customerCity: 'Kochi',
    failureCode: 'UNKNOWN_SYSTEM_ERROR',
    failureReason: 'Unrecognized edge-case error string from gateway',
    category: 'technical_failure',
    decisionAction: 'escalate_to_human',
    status: 'escalated',
  },
];

const SAMPLE_DRAWER_DATA: Record<string, DrawerData> = {
  pay_1001: {
    paymentId: 'pay_1001',
    orderId: 'order_1001',
    amountRupees: 2499.00,
    status: 'recovered',
    failedAt: '2026-09-02T10:15:00Z',
    cartSummary: 'Mixer Grinder 750W 3-Jar Set',
    failureCode: 'GATEWAY_TIMEOUT',
    failureReason: 'Bank gateway timed out during processing',
    customer: {
      name: 'Harshit Sharma',
      phone: '+91 98765 43210',
      email: 'harshit@example.com',
      city: 'Bengaluru',
      historyTotalPayments: 14,
      historyFailedPayments: 1,
      isRiskFlagged: false,
    },
    classification: {
      category: 'technical_failure',
      confidence: 0.94,
      reasoning: 'Customer has a 93% on-time payment track record and the error was a transient gateway timeout. Clear high-intent transaction.',
      signalsUsed: ['failure_code: GATEWAY_TIMEOUT', 'history: 14/15 paid', 'amount: Rs. 2,499'],
    },
    gatesEvaluated: [
      { gateId: 'G1', name: 'do_not_contact', status: 'passed', reason: 'Customer is in good standing and not risk-flagged.' },
      { gateId: 'G2', name: 'value_floor', status: 'passed', reason: 'Amount (Rs. 2,499.00) exceeds Rs. 100.00 cost threshold.' },
      { gateId: 'G3', name: 'max_attempts', status: 'passed', reason: 'Attempt 1 of 2 max allowed.' },
      { gateId: 'G5', name: 'quiet_hours', status: 'passed', reason: 'Local time (10:15 IST) is within 09:00-20:00 daytime window.' },
    ],
    recoveryAttempts: [
      {
        attemptNumber: 1,
        actionTaken: 'send_payment_link',
        paymentLinkUrl: 'https://rzp.io/i/test_rec_pay_1001_att1',
        outcome: 'paid',
        sentAt: '2026-09-02T10:16:00Z',
      },
    ],
  },
  pay_1003: {
    paymentId: 'pay_1003',
    orderId: 'order_1003',
    amountRupees: 18450.00,
    status: 'suppressed',
    failedAt: '2026-09-02T11:00:00Z',
    cartSummary: 'Flagship Smartphone 128GB',
    failureCode: 'CARD_LIMIT_EXCEEDED',
    failureReason: 'Customer account flagged for high chargeback risk',
    customer: {
      name: 'Vikram Singh',
      phone: '+91 98111 22334',
      email: 'vikram@example.com',
      city: 'Jaipur',
      historyTotalPayments: 2,
      historyFailedPayments: 2,
      isRiskFlagged: true,
    },
    classification: {
      category: 'do_not_pursue',
      confidence: 0.99,
      reasoning: 'Customer profile has an active risk flag and 100% failed payment history. Hard policy suppression required.',
      signalsUsed: ['is_risk_flagged: True', 'history: 2/2 failed'],
    },
    gatesEvaluated: [
      { gateId: 'G1', name: 'do_not_contact', status: 'triggered', reason: 'Customer is marked as high-risk. Outreach permanently blocked.' },
    ],
    recoveryAttempts: [],
  },
};

export default function App() {
  const [selectedRow, setSelectedRow] = useState<LedgerRowData | null>(null);
  const [activeTab, setActiveTab] = useState<'agent' | 'baseline'>('agent');
  const [sliderValue, setSliderValue] = useState<number>(100);

  const drawerData = selectedRow ? (SAMPLE_DRAWER_DATA[selectedRow.paymentId] || {
    paymentId: selectedRow.paymentId,
    orderId: selectedRow.orderId,
    amountRupees: selectedRow.amountRupees,
    status: selectedRow.status,
    failedAt: '2026-09-02T12:00:00Z',
    cartSummary: 'General Merchandise',
    failureCode: selectedRow.failureCode,
    failureReason: selectedRow.failureReason,
    customer: {
      name: selectedRow.customerName,
      phone: '+91 99999 00000',
      email: 'customer@example.com',
      city: selectedRow.customerCity || 'India',
      historyTotalPayments: 5,
      historyFailedPayments: 1,
      isRiskFlagged: selectedRow.status === 'suppressed',
    },
    classification: selectedRow.category ? {
      category: selectedRow.category,
      confidence: 0.92,
      reasoning: 'Classified based on gateway failure signals and customer historical reliability.',
      signalsUsed: [selectedRow.failureCode],
    } : undefined,
    gatesEvaluated: [
      { gateId: 'G1', name: 'do_not_contact', status: selectedRow.status === 'suppressed' ? 'triggered' : 'passed', reason: selectedRow.status === 'suppressed' ? 'Policy suppression gate triggered' : 'Passed safety checks' },
    ],
    recoveryAttempts: selectedRow.paymentLinkUrl ? [
      {
        attemptNumber: 1,
        actionTaken: selectedRow.decisionAction || 'send_payment_link',
        paymentLinkUrl: selectedRow.paymentLinkUrl,
        outcome: selectedRow.status === 'recovered' ? 'paid' : 'pending',
        sentAt: '2026-09-02T12:05:00Z',
      }
    ] : [],
  }) : null;

  return (
    <div className="min-h-screen bg-page text-ink flex flex-col font-sans">
      {/* Top Bar Instrument Header */}
      <header className="h-14 border-b border-border bg-surface px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 rounded bg-accent text-white flex items-center justify-center font-mono text-xs font-bold shadow-xs">
            R
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold text-ink">Razorpay AI Revenue Recovery Agent</h1>
              <Badge variant="accent" size="sm">Track 3</Badge>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5 text-ink-muted bg-surface-inset px-2.5 py-1 rounded border border-border-subtle">
            <span className="w-2 h-2 rounded-full bg-recovered animate-pulse" />
            <span>RZP TEST MODE</span>
          </div>
          <div className="text-ink-muted">
            seed: <span className="text-ink font-semibold">42</span>
          </div>
          <div className="text-ink-muted">
            clock: <span className="text-ink font-semibold">28,800x</span>
          </div>
        </div>
      </header>

      {/* 3-Column Instrument Grid */}
      <div className="flex-1 grid grid-cols-12 gap-0 overflow-hidden">
        {/* LEFT RAIL: Run Controls & Deterministic Policy Config */}
        <aside className="col-span-3 border-r border-border bg-surface p-5 flex flex-col gap-5 overflow-y-auto">
          {/* Mode Switcher */}
          <div>
            <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider mb-2">Execution Mode</div>
            <div className="grid grid-cols-2 gap-1 p-1 bg-surface-inset rounded border border-border-subtle">
              <button
                onClick={() => setActiveTab('agent')}
                className={`text-xs font-medium py-1.5 rounded transition-colors ${
                  activeTab === 'agent'
                    ? 'bg-surface text-accent font-semibold shadow-xs border border-border'
                    : 'text-ink-muted hover:text-ink'
                }`}
              >
                Agentic (AI)
              </button>
              <button
                onClick={() => setActiveTab('baseline')}
                className={`text-xs font-medium py-1.5 rounded transition-colors ${
                  activeTab === 'baseline'
                    ? 'bg-surface text-ink font-semibold shadow-xs border border-border'
                    : 'text-ink-muted hover:text-ink'
                }`}
              >
                Baseline
              </button>
            </div>
          </div>

          {/* Action Triggers */}
          <div className="space-y-2">
            <Button variant="primary" size="md" className="w-full" icon={<Play className="w-3.5 h-3.5" />}>
              Run Recovery Batch (80 Tx)
            </Button>
            <Button variant="quiet" size="sm" className="w-full" icon={<RotateCcw className="w-3.5 h-3.5" />}>
              Reset & Reseed Dataset
            </Button>
          </div>

          {/* Live Deterministic Policy Config */}
          <div className="pt-2 border-t border-border">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-accent" />
                <span>Deterministic Hard Gates</span>
              </div>
              <span className="text-xxs font-mono text-ink-subtle">7 Gates Active</span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
                <div>
                  <div className="font-mono text-xs font-semibold text-ink">G1 do_not_contact</div>
                  <div className="text-xxs text-ink-muted font-sans">Risk flagged or opted out</div>
                </div>
                <Badge variant="suppressed">Hard Stop</Badge>
              </div>

              <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
                <div>
                  <div className="font-mono text-xs font-semibold text-ink">G2 value_floor</div>
                  <div className="text-xxs text-ink-muted font-sans">Outreach cost floor</div>
                </div>
                <span className="font-mono text-xs font-semibold text-ink">Rs. 100.00</span>
              </div>

              <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
                <div>
                  <div className="font-mono text-xs font-semibold text-ink">G3 max_attempts</div>
                  <div className="text-xxs text-ink-muted font-sans">Customer fatigue cap</div>
                </div>
                <span className="font-mono text-xs font-semibold text-ink">2 attempts</span>
              </div>

              <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
                <div>
                  <div className="font-mono text-xs font-semibold text-ink">G4 cooldown</div>
                  <div className="text-xxs text-ink-muted font-sans">Rest between messages</div>
                </div>
                <span className="font-mono text-xs font-semibold text-ink">24.0 hours</span>
              </div>

              <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
                <div>
                  <div className="font-mono text-xs font-semibold text-ink">G5 quiet_hours</div>
                  <div className="text-xxs text-ink-muted font-sans">Local daytime only</div>
                </div>
                <span className="font-mono text-xs font-semibold text-ink">09:00-20:00 IST</span>
              </div>
            </div>
          </div>

          {/* Interactive What-If Parameter Slider */}
          <div className="pt-2 border-t border-border">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-ink-muted" />
                <span>What-If Value Floor</span>
              </div>
              <span className="font-mono text-xs font-semibold text-accent">Rs. {sliderValue}.00</span>
            </div>
            <input
              type="range"
              min="0"
              max="500"
              step="25"
              value={sliderValue}
              onChange={(e) => setSliderValue(Number(e.target.value))}
              className="w-full accent-accent cursor-pointer"
            />
            <div className="flex justify-between text-xxs font-mono text-ink-subtle mt-1">
              <span>Rs. 0</span>
              <span>Rs. 250</span>
              <span>Rs. 500</span>
            </div>
          </div>
        </aside>

        {/* MAIN COLUMN: Live Decision Ledger Feed */}
        <main className="col-span-6 bg-surface flex flex-col border-r border-border overflow-hidden">
          {/* Feed Header */}
          <div className="px-5 py-3 border-b border-border bg-surface-raised flex items-center justify-between">
            <div>
              <h2 className="text-xs font-semibold text-ink">Live Decision Ledger</h2>
              <p className="text-xxs text-ink-muted font-sans">Click any row to inspect deep gate audits and payment links.</p>
            </div>
            <div className="flex items-center gap-1.5">
              <GateChip gateId="G1" status="triggered" compact />
              <GateChip gateId="G2" status="triggered" compact />
              <GateChip gateId="G3" status="passed" compact />
            </div>
          </div>

          {/* Table Column Headers */}
          <div className="flex items-center justify-between gap-4 px-4 py-2 bg-surface-inset border-b border-border text-xxs font-mono uppercase tracking-wider text-ink-muted select-none">
            <div className="w-1/5">Transaction / Customer</div>
            <div className="w-1/6 text-right">Amount / Order</div>
            <div className="w-1/4">Failure Reason</div>
            <div className="w-1/5">Intent & Gate Action</div>
            <div className="min-w-[90px] text-right">Outcome</div>
          </div>

          {/* Ledger Rows */}
          <div className="flex-1 overflow-y-auto divide-y divide-border">
            {SAMPLE_ROWS.map((row) => (
              <Row
                key={row.paymentId}
                data={{
                  ...row,
                  isSelected: selectedRow?.paymentId === row.paymentId,
                }}
                onClick={(data) => setSelectedRow(data)}
              />
            ))}
          </div>

          {/* Feed Footer */}
          <div className="px-4 py-2.5 border-t border-border bg-surface-raised text-xxs font-mono text-ink-muted flex items-center justify-between">
            <span>Showing 6 of 80 transactions in batch</span>
            <span>Seed 42 ? 0 live merchant PII</span>
          </div>
        </main>

        {/* RIGHT COLUMN: Real-Time Recovery & Pitch Metrics */}
        <aside className="col-span-3 bg-surface p-5 flex flex-col gap-5 overflow-y-auto">
          <div>
            <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider mb-2">Performance & Lift vs Baseline</div>
            
            <div className="space-y-3">
              <StatBlock
                label="Recovery Rate"
                value="38.8%"
                subvalue="+27.6% lift"
                secondaryText="31 recovered vs 9 baseline"
                variant="recovered"
              />

              <StatBlock
                label="Recovered Revenue"
                value="Rs. 1,37,669.00"
                subvalue="+Rs. 50,878.00"
                secondaryText="Total at risk: Rs. 4,85,800.00"
                variant="accent"
              />

              <StatBlock
                label="Cost per Recovery"
                value="Rs. 1.35"
                subvalue="1,211x ROI"
                secondaryText="84 WhatsApp/SMS contacts @ Rs. 0.50"
              />

              <StatBlock
                label="Policy Restraint"
                value="24 Suppressed"
                subvalue="30.0% of cohort"
                secondaryText="Rs. 1,25,456.00 value protected"
                variant="suppressed"
              />
            </div>
          </div>

          {/* Suppression Breakdown Card */}
          <div className="pt-3 border-t border-border">
            <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider mb-2">Policy Gate Restraint Breakdown</div>
            <div className="bg-surface-raised rounded border border-border p-3 space-y-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="font-mono text-ink-muted">G1 Risk Flagged</span>
                <span className="font-mono font-semibold text-ink">14 tx (Rs. 97.9k)</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-ink-muted">G2 Under Rs. 100</span>
                <span className="font-mono font-semibold text-ink">9 tx (Rs. 491)</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-ink-muted">G3 Max 2 Attempts</span>
                <span className="font-mono font-semibold text-ink">1 tx (Rs. 26.9k)</span>
              </div>
            </div>
          </div>

          {/* Honest Methodology Box */}
          <div className="p-3 bg-surface-inset rounded border border-border-subtle text-xxs space-y-1.5">
            <div className="font-mono font-semibold text-ink flex items-center gap-1">
              <Info className="w-3 h-3 text-ink-muted" />
              <span>Honest Evaluation Notice</span>
            </div>
            <p className="text-ink-muted leading-relaxed font-sans">
              Evaluated against a seed-locked zero-intervention baseline on synthetic dataset ($N=80$). Customer response is simulated with attempt decay. Zero live customer PII used.
            </p>
          </div>
        </aside>
      </div>

      {/* Slide-over Inspection Drawer */}
      <Drawer
        isOpen={Boolean(selectedRow)}
        onClose={() => setSelectedRow(null)}
        data={drawerData}
      />
    </div>
  );
}
