import { useEffect, useState, useRef } from 'react';
import { Download, Layers, Moon, Sun } from 'lucide-react';
import { Badge } from '@/components/primitives/Badge';
import { Button } from '@/components/primitives/Button';
import { PolicyConfigPanel } from '@/components/dashboard/PolicyConfigPanel';
import { DecisionFeed } from '@/components/dashboard/DecisionFeed';
import { MetricsPanel } from '@/components/dashboard/MetricsPanel';
import { ExceptionsTable } from '@/components/dashboard/ExceptionsTable';
import { AuditDrawer } from '@/components/dashboard/AuditDrawer';
import { ComparisonModal } from '@/components/dashboard/ComparisonModal';
import { 
  fetchPolicyConfig, 
  startRecoveryRun, 
  fetchComparisonReport, 
  fetchRunExceptions,
  fetchRunEvents,
  simulateWhatIfPolicy 
} from '@/api/client';
import { 
  PolicyConfig, 
  ComparisonReport, 
  ExceptionsResponse, 
  SSEEventData, 
  SimulatePolicyResponse 
} from '@/api/types';

export default function App() {
  // Theme state
  const [isDark, setIsDark] = useState<boolean>(false);

  // Core Data State
  const [policyConfig, setPolicyConfig] = useState<PolicyConfig | null>(null);
  const [comparisonReport, setComparisonReport] = useState<ComparisonReport | null>(null);
  const [exceptions, setExceptions] = useState<ExceptionsResponse | null>(null);
  const [simulationData, setSimulationData] = useState<SimulatePolicyResponse | null>(null);
  const [events, setEvents] = useState<SSEEventData[]>([]);
  const [selectedPaymentId, setSelectedPaymentId] = useState<string | null>(null);
  const [isComparisonOpen, setIsComparisonOpen] = useState<boolean>(false);

  // Run Controls
  const [mode, setMode] = useState<'agent' | 'baseline'>('agent');
  const [seed, setSeed] = useState<number>(42);
  const [timeMultiplier, setTimeMultiplier] = useState<number>(28800);
  const [injectFailure, setInjectFailure] = useState<boolean>(false);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);

  // Live Aggregated Stats
  const [liveStats, setLiveStats] = useState({
    total: 0,
    recovered: 0,
    recoveredRevenue: 0,
    suppressed: 0,
    suppressedRevenue: 0,
    contacts: 0,
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  // 1. Initial Load: Fetch Policy Config & Default Seed Comparison Report
  useEffect(() => {
    fetchPolicyConfig()
      .then((cfg) => setPolicyConfig(cfg))
      .catch((err) => console.error('Error loading policy config:', err));

    fetchComparisonReport(seed)
      .then((report) => setComparisonReport(report))
      .catch((err) => console.error('Error loading initial comparison:', err));

    // Pre-populate events if database already has transactions
    fetchRunEvents('initial', 80)
      .then((evRes) => {
        if (evRes?.items && evRes.items.length > 0) {
          setEvents(evRes.items.map((item: any) => ({
            payment_id: item.payment_id,
            order_id: item.order_id,
            amount_rupees: item.amount_rupees,
            customer_name: item.customer_name,
            customer_city: item.customer_city,
            cart_summary: item.cart_summary,
            status: item.status,
            failure_code: item.failure_code,
            failure_reason: item.failure_reason,
            last_action: item.last_action,
            state: item.status === 'open' ? 'classifying' : 'outcome',
          })));
        }
      })
      .catch((err) => console.error('Error loading initial events:', err));
  }, []);

  // Sync dark class on root
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  // Clean up EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // 2. Start Live Recovery Run
  const handleStartRun = async () => {
    if (isRunning) return;

    setIsRunning(true);
    setEvents([]);
    setSimulationData(null);
    setLiveStats({
      total: 0,
      recovered: 0,
      recoveredRevenue: 0,
      suppressed: 0,
      suppressedRevenue: 0,
      contacts: 0,
    });

    try {
      const res = await startRecoveryRun({
        mode,
        seed,
        split: 'all',
        reseed: true,
        time_multiplier: timeMultiplier,
        inject_llm_failure: injectFailure,
      });

      setCurrentRunId(res.run_id);

      // Connect SSE
      const es = new EventSource(`/api/runs/${res.run_id}/stream`);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const raw = JSON.parse(event.data);
          const data = raw.data ? { ...raw, ...raw.data } : raw;

          if (data.event_type === 'step_processing' || data.event_type === 'step_started') {
            setEvents((prev) => {
              const existingIdx = prev.findIndex((p) => p.payment_id === data.payment_id);
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], ...data, state: 'classifying' };
                return updated;
              }
              return [...prev, { ...data, state: 'classifying' }];
            });
          } else if (data.event_type === 'step_classified') {
            setEvents((prev) => {
              const existingIdx = prev.findIndex((p) => p.payment_id === data.payment_id);
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], ...data, state: 'decided' };
                return updated;
              }
              return [...prev, { ...data, state: 'decided' }];
            });
          } else if (data.event_type === 'step_decided') {
            setEvents((prev) => {
              const existingIdx = prev.findIndex((p) => p.payment_id === data.payment_id);
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], ...data, state: 'decided' };
                return updated;
              }
              return [...prev, { ...data, state: 'decided' }];
            });
          } else if (data.event_type === 'step_outcome' || data.event_type === 'step_processed') {
            setEvents((prev) => {
              const existingIdx = prev.findIndex((p) => p.payment_id === data.payment_id);
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], ...data, state: 'outcome' };
                return updated;
              }
              return [...prev, { ...data, state: 'outcome' }];
            });

            // Update live totals
            setLiveStats((prev) => {
              const amt = data.amount_rupees || 0;
              const isRec = data.status === 'recovered' || data.outcome === 'paid' || data.status === 'RECOVERED';
              const isSupp = data.status === 'suppressed' || data.decision?.action === 'suppress' || data.status === 'SUPPRESSED';
              return {
                total: prev.total + 1,
                recovered: prev.recovered + (isRec ? 1 : 0),
                recoveredRevenue: prev.recoveredRevenue + (isRec ? amt : 0),
                suppressed: prev.suppressed + (isSupp ? 1 : 0),
                suppressedRevenue: prev.suppressedRevenue + (isSupp ? amt : 0),
                contacts: prev.contacts + (data.decision?.action === 'send_payment_link' || data.decision?.action === 'send_reminder_no_link' ? 1 : 0),
              };
            });
          } else if (data.event_type === 'run_completed') {
            es.close();
            setIsRunning(false);

            // Fetch final comparison, exceptions, and events
            fetchComparisonReport(seed).then((rep) => setComparisonReport(rep));
            if (res.run_id) {
              fetchRunExceptions(res.run_id).then((exc) => setExceptions(exc));
              fetchRunEvents(res.run_id, 80).then((evRes) => {
                if (evRes?.items && evRes.items.length > 0) {
                  setEvents(evRes.items.map((item: any) => ({
                    payment_id: item.payment_id,
                    order_id: item.order_id,
                    amount_rupees: item.amount_rupees,
                    customer_name: item.customer_name,
                    customer_city: item.customer_city,
                    cart_summary: item.cart_summary,
                    status: item.status,
                    failure_code: item.failure_code,
                    failure_reason: item.failure_reason,
                    last_action: item.last_action,
                    state: 'outcome',
                  })));
                }
              });
            }
          } else if (data.event_type === 'run_error') {
            es.close();
            setIsRunning(false);
            console.error('Run encountered error:', data);
          }
        } catch (parseErr) {
          // Heartbeat
        }
      };

      es.onerror = () => {
        es.close();
        setIsRunning(false);
        fetchComparisonReport(seed).then((rep) => setComparisonReport(rep));
        if (res.run_id) {
          fetchRunEvents(res.run_id, 80).then((evRes) => {
            if (evRes?.items && evRes.items.length > 0) {
              setEvents(evRes.items.map((item: any) => ({
                payment_id: item.payment_id,
                order_id: item.order_id,
                amount_rupees: item.amount_rupees,
                customer_name: item.customer_name,
                customer_city: item.customer_city,
                cart_summary: item.cart_summary,
                status: item.status,
                failure_code: item.failure_code,
                failure_reason: item.failure_reason,
                last_action: item.last_action,
                state: 'outcome',
              })));
            }
          });
        }
      };

    } catch (err: any) {
      setIsRunning(false);
      alert(`Error starting recovery run: ${err.message}`);
    }
  };

  // 3. Reset Dataset
  const handleResetDataset = async () => {
    if (isRunning) return;
    try {
      await fetch('/api/runs/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'agent', seed, split: 'all', reseed: true }),
      });
      setEvents([]);
      setExceptions(null);
      fetchComparisonReport(seed).then((rep) => setComparisonReport(rep));
    } catch (e: any) {
      console.error(e);
    }
  };

  // 4. What-If Multi-Slider Simulation
  const handleSimulateSliders = async (params: {
    cost_of_contact_threshold_rupees: number;
    max_recovery_attempts: number;
    confidence_floor: number;
  }) => {
    try {
      const sim = await simulateWhatIfPolicy(params);
      setSimulationData(sim);
    } catch (e) {
      console.error('Simulation error:', e);
    }
  };

  // 5. Download Audit CSV
  const handleDownloadAuditCSV = () => {
    const runIdToExport = currentRunId || 'latest_run';
    const downloadUrl = `/api/runs/${runIdToExport}/export/csv`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.setAttribute('download', `recovery_agent_audit_trail_${runIdToExport}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className={`min-h-screen bg-page text-ink flex flex-col font-sans selection:bg-accent-subtle selection:text-accent ${isDark ? 'dark bg-[#0D0F12] text-[#F0F2F5]' : ''}`}>
      {/* Top Bar Instrument Header */}
      <header className="h-14 border-b border-border bg-surface px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 rounded bg-accent text-white flex items-center justify-center font-mono text-xs font-bold shadow-xs">
            R
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-ink">Razorpay AI Revenue Recovery Agent</h1>
              <Badge variant="accent" size="sm">Track 3</Badge>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {/* Audit CSV Download Button */}
          <Button
            variant="quiet"
            size="sm"
            icon={<Download className="w-3.5 h-3.5 text-accent" />}
            onClick={handleDownloadAuditCSV}
            title="Download complete immutable audit trail as CSV"
          >
            Export Audit (CSV)
          </Button>

          {/* Side-by-Side Comparison Button */}
          <Button
            variant="outline"
            size="sm"
            icon={<Layers className="w-3.5 h-3.5 text-accent" />}
            onClick={() => setIsComparisonOpen(true)}
          >
            Compare Uplift
          </Button>

          <div className="h-4 w-[1px] bg-border mx-1" />

          {/* Test Mode & Clock Indicators */}
          <div className="flex items-center gap-1.5 text-ink-muted bg-surface-inset px-2.5 py-1 rounded border border-border-subtle font-mono text-xxs">
            <span className="w-2 h-2 rounded-full bg-recovered animate-pulse" />
            <span>RZP TEST MODE</span>
          </div>

          <div className="text-ink-muted font-mono text-xxs">
            seed: <span className="text-ink font-semibold">{seed}</span>
          </div>

          {/* Dark Mode Toggle */}
          <button
            onClick={() => setIsDark(!isDark)}
            className="p-1.5 rounded text-ink-muted hover:text-ink hover:bg-surface-inset transition-colors"
            aria-label="Toggle Dark Mode"
            title="Toggle theme"
          >
            {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </header>

      {/* Main 3-Column Instrument Grid */}
      <div className="flex-1 flex overflow-x-auto overflow-y-hidden min-w-full">
        {/* LEFT RAIL: Policy Config & Run Controls */}
        <PolicyConfigPanel
          policyConfig={policyConfig}
          mode={mode}
          setMode={setMode}
          seed={seed}
          setSeed={setSeed}
          timeMultiplier={timeMultiplier}
          setTimeMultiplier={setTimeMultiplier}
          injectFailure={injectFailure}
          setInjectFailure={setInjectFailure}
          onRunBatch={handleStartRun}
          onResetDataset={handleResetDataset}
          isRunning={isRunning}
          onSimulateSliders={handleSimulateSliders}
        />

        {/* CENTRE COLUMN: Live Decision Feed & Bottom Exceptions Table */}
        <div className="flex-1 flex flex-col min-w-[480px] overflow-hidden">
          <DecisionFeed
            events={events}
            selectedPaymentId={selectedPaymentId}
            onSelectRow={(id) => setSelectedPaymentId(id)}
            isRunning={isRunning}
            onStartRun={handleStartRun}
            mode={mode}
          />

          {/* Bottom Exceptions & Policy Suppressions Table */}
          <ExceptionsTable
            exceptions={exceptions}
            onSelectPayment={(id) => setSelectedPaymentId(id)}
          />
        </div>

        {/* RIGHT COLUMN: Real-Time Recovery & Pitch Metrics */}
        <MetricsPanel
          comparisonReport={comparisonReport}
          liveStats={liveStats}
          simulationData={simulationData}
        />
      </div>

      {/* Slide-over Tamper-Evident Audit Drawer */}
      <AuditDrawer
        paymentId={selectedPaymentId}
        onClose={() => setSelectedPaymentId(null)}
      />

      {/* Side-by-Side Uplift Comparison Modal */}
      <ComparisonModal
        isOpen={isComparisonOpen}
        onClose={() => setIsComparisonOpen(false)}
        report={comparisonReport}
      />
    </div>
  );
}
