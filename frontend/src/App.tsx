import { useEffect, useState, useRef } from 'react';
import { Badge } from '@/components/primitives/Badge';
import { PolicyConfigPanel } from '@/components/dashboard/PolicyConfigPanel';
import { DecisionFeed } from '@/components/dashboard/DecisionFeed';
import { MetricsPanel } from '@/components/dashboard/MetricsPanel';
import { ExceptionsTable } from '@/components/dashboard/ExceptionsTable';
import { AuditDrawer } from '@/components/dashboard/AuditDrawer';
import { 
  fetchPolicyConfig, 
  startRecoveryRun, 
  fetchComparisonReport, 
  fetchRunExceptions,
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
  // State
  const [policyConfig, setPolicyConfig] = useState<PolicyConfig | null>(null);
  const [comparisonReport, setComparisonReport] = useState<ComparisonReport | null>(null);
  const [exceptions, setExceptions] = useState<ExceptionsResponse | null>(null);
  const [simulationData, setSimulationData] = useState<SimulatePolicyResponse | null>(null);
  const [events, setEvents] = useState<SSEEventData[]>([]);
  const [selectedPaymentId, setSelectedPaymentId] = useState<string | null>(null);

  // Run Controls
  const [mode, setMode] = useState<'agent' | 'baseline'>('agent');
  const [seed, setSeed] = useState<number>(42);
  const [timeMultiplier, setTimeMultiplier] = useState<number>(28800);
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
  }, []);

  // Clean up EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // 2. Start Recovery Run & Connect to SSE Stream
  const handleStartRun = async () => {
    if (isRunning) return;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setIsRunning(true);
    setEvents([]);
    setExceptions(null);
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
      });

      setCurrentRunId(res.run_id);

      // Connect SSE
      const es = new EventSource(`/api/runs/${res.run_id}/stream`);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const data: SSEEventData = JSON.parse(event.data);

          if (data.event_type === 'step_processing') {
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
              const isRec = data.status === 'recovered' || data.outcome === 'paid';
              const isSupp = data.status === 'suppressed' || data.decision?.action === 'suppress';
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

            // Fetch final comparison and exceptions
            fetchComparisonReport(seed).then((rep) => setComparisonReport(rep));
            if (res.run_id) {
              fetchRunExceptions(res.run_id).then((exc) => setExceptions(exc));
            }
          } else if (data.event_type === 'run_error') {
            es.close();
            setIsRunning(false);
            console.error('Run encountered error:', data);
          }
        } catch (parseErr) {
          // Heartbeat or malformed frame
        }
      };

      es.onerror = () => {
        es.close();
        setIsRunning(false);
        // On stream close, refresh comparison
        fetchComparisonReport(seed).then((rep) => setComparisonReport(rep));
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

  // 4. What-If Parameter Simulation Slider
  const handleSimulateSlider = async (valueFloor: number) => {
    try {
      const sim = await simulateWhatIfPolicy({
        cost_of_contact_threshold_rupees: valueFloor,
      });
      setSimulationData(sim);
    } catch (e) {
      console.error('Simulation error:', e);
    }
  };

  return (
    <div className="min-h-screen bg-page text-ink flex flex-col font-sans selection:bg-accent-subtle selection:text-accent">
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
            seed: <span className="text-ink font-semibold">{seed}</span>
          </div>
          <div className="text-ink-muted">
            clock: <span className="text-ink font-semibold">{timeMultiplier.toLocaleString()}x</span>
          </div>
          {currentRunId && (
            <div className="text-ink-subtle truncate max-w-[140px]" title={currentRunId}>
              {currentRunId}
            </div>
          )}
        </div>
      </header>

      {/* Main 3-Column Instrument Grid */}
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT RAIL: Policy Config & Run Controls */}
        <PolicyConfigPanel
          policyConfig={policyConfig}
          mode={mode}
          setMode={setMode}
          seed={seed}
          setSeed={setSeed}
          timeMultiplier={timeMultiplier}
          setTimeMultiplier={setTimeMultiplier}
          onRunBatch={handleStartRun}
          onResetDataset={handleResetDataset}
          isRunning={isRunning}
          onSimulateSlider={handleSimulateSlider}
        />

        {/* CENTRE COLUMN: Live Decision Feed & Bottom Exceptions Table */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
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
    </div>
  );
}
