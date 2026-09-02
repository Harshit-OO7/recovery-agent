import React, { useState } from 'react';
import { ShieldCheck, Sliders, Play, RotateCcw } from 'lucide-react';
import { Button } from '@/components/primitives/Button';
import { Badge } from '@/components/primitives/Badge';
import { PolicyConfig } from '@/api/types';

export interface PolicyConfigPanelProps {
  policyConfig: PolicyConfig | null;
  mode: 'agent' | 'baseline';
  setMode: (mode: 'agent' | 'baseline') => void;
  seed: number;
  setSeed: (seed: number) => void;
  timeMultiplier: number;
  setTimeMultiplier: (multiplier: number) => void;
  injectFailure: boolean;
  setInjectFailure: (inject: boolean) => void;
  onRunBatch: () => void;
  onResetDataset: () => void;
  isRunning: boolean;
  onSimulateSliders: (params: {
    cost_of_contact_threshold_rupees: number;
    max_recovery_attempts: number;
    confidence_floor: number;
  }) => void;
}

export const PolicyConfigPanel: React.FC<PolicyConfigPanelProps> = ({
  policyConfig,
  mode,
  setMode,
  seed,
  setSeed,
  timeMultiplier,
  setTimeMultiplier,
  injectFailure,
  setInjectFailure,
  onRunBatch,
  onResetDataset,
  isRunning,
  onSimulateSliders,
}) => {
  const [valueFloor, setValueFloor] = useState<number>(100);
  const [maxAttempts, setMaxAttempts] = useState<number>(2);
  const [confidenceFloor, setConfidenceFloor] = useState<number>(0.55);

  const cooldownRealHours = policyConfig?.POLICY_CONFIG?.COOLDOWN_HOURS ?? 24;
  const cooldownCompressedSecs = (cooldownRealHours * 3600 / timeMultiplier).toFixed(1);

  const handleParamChange = (newFloor: number, newAttempts: number, newConf: number) => {
    setValueFloor(newFloor);
    setMaxAttempts(newAttempts);
    setConfidenceFloor(newConf);
    onSimulateSliders({
      cost_of_contact_threshold_rupees: newFloor,
      max_recovery_attempts: newAttempts,
      confidence_floor: newConf,
    });
  };

  return (
    <aside className="w-72 border-r border-border bg-surface p-4 flex flex-col gap-4 overflow-y-auto shrink-0 select-none">
      {/* 1. Execution Mode Toggle */}
      <div>
        <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider mb-2">
          Execution Mode
        </div>
        <div className="grid grid-cols-2 gap-1 p-1 bg-surface-inset rounded border border-border-subtle">
          <button
            onClick={() => setMode('agent')}
            disabled={isRunning}
            className={`text-xs font-medium py-1.5 rounded transition-colors ${
              mode === 'agent'
                ? 'bg-surface text-accent font-bold shadow-xs border border-border'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            Agentic (AI)
          </button>
          <button
            onClick={() => setMode('baseline')}
            disabled={isRunning}
            className={`text-xs font-medium py-1.5 rounded transition-colors ${
              mode === 'baseline'
                ? 'bg-surface text-ink font-bold shadow-xs border border-border'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            Baseline
          </button>
        </div>
        <div className="text-xxs text-ink-muted mt-1.5 font-sans leading-tight">
          {mode === 'agent' 
            ? 'Autonomous root cause classification, 7 policy gates, & 1-click test payment links.'
            : 'Counterfactual zero-intervention baseline. No contact dispatched.'}
        </div>
      </div>

      {/* 2. Run Parameters & Failure Injection */}
      <div className="space-y-3 pt-2 border-t border-border">
        <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider">
          Batch Controls
        </div>

        {/* Master Seed */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-ink-muted font-mono">Master Seed:</span>
          <input
            type="number"
            value={seed}
            disabled={isRunning}
            onChange={(e) => setSeed(Number(e.target.value))}
            className="w-20 font-mono text-xs px-2 py-1 bg-surface-inset border border-border rounded text-right text-ink focus-visible:ring-2 focus-visible:ring-accent"
          />
        </div>

        {/* Demo Time Multiplier */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-ink-muted font-mono">Demo Clock:</span>
            <span className="font-mono font-semibold text-accent">{timeMultiplier.toLocaleString()}x</span>
          </div>
          <div className="grid grid-cols-3 gap-1">
            {[1, 28800, 57600].map((speed) => (
              <button
                key={speed}
                onClick={() => setTimeMultiplier(speed)}
                disabled={isRunning}
                className={`text-xxs font-mono py-1 rounded border transition-colors ${
                  timeMultiplier === speed
                    ? 'bg-accent-subtle text-accent border-accent font-semibold'
                    : 'bg-surface text-ink-muted border-border hover:bg-surface-raised'
                }`}
              >
                {speed === 1 ? '1x Real' : `${speed / 1000}k Fast`}
              </button>
            ))}
          </div>
          <div className="text-xxs text-ink-subtle font-mono mt-0.5">
            24h cooldown = <span className="font-semibold text-ink">{cooldownCompressedSecs}s</span> demo duration
          </div>
        </div>

        {/* Controlled Failure Injection Toggle */}
        <div className="p-2.5 rounded bg-surface-inset border border-border-subtle space-y-1.5">
          <label className="flex items-start gap-2 cursor-pointer text-xs">
            <input
              type="checkbox"
              checked={injectFailure}
              disabled={isRunning || mode === 'baseline'}
              onChange={(e) => setInjectFailure(e.target.checked)}
              className="mt-0.5 accent-accent rounded"
            />
            <div className="flex-1">
              <span className="font-semibold text-ink block text-xxs">Inject LLM Malformed JSON</span>
              <span className="text-xxs text-ink-muted font-sans block leading-tight">
                Simulates LLM parse failure on Payment #2 to demonstrate rule-based fallback recovery with 0 crashes.
              </span>
            </div>
          </label>
        </div>

        {/* Trigger Buttons */}
        <div className="space-y-2 pt-1">
          <Button
            variant="primary"
            size="md"
            className="w-full"
            icon={<Play className="w-3.5 h-3.5" />}
            onClick={onRunBatch}
            loading={isRunning}
          >
            {isRunning ? 'Processing Batch...' : `Run ${mode === 'agent' ? 'Agentic' : 'Baseline'} Batch (80 Tx)`}
          </Button>

          <Button
            variant="quiet"
            size="sm"
            className="w-full"
            icon={<RotateCcw className="w-3.5 h-3.5" />}
            onClick={onResetDataset}
            disabled={isRunning}
          >
            Reset & Reseed Dataset
          </Button>
        </div>
      </div>

      {/* 3. Live Policy Config Card */}
      <div className="pt-2 border-t border-border space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-accent" />
            <span>Deterministic Hard Gates</span>
          </div>
          <Badge variant="accent" size="sm">7 Gates</Badge>
        </div>

        <div className="space-y-1.5 text-xs">
          <div className="p-2 rounded bg-surface-raised border border-border flex justify-between items-center">
            <span className="font-mono text-xs text-ink">G1 do_not_contact</span>
            <Badge variant="suppressed" size="sm">Permanent Stop</Badge>
          </div>
          <div className="p-2 rounded bg-surface-raised border border-border flex justify-between items-center">
            <span className="font-mono text-xs text-ink">G4 cooldown</span>
            <span className="font-mono text-xs font-bold text-ink">24.0h</span>
          </div>
          <div className="p-2 rounded bg-surface-raised border border-border flex justify-between items-center">
            <span className="font-mono text-xs text-ink">G5 quiet_hours</span>
            <span className="font-mono text-xxs font-medium text-ink">09:00 - 20:00 IST</span>
          </div>
        </div>
      </div>

      {/* 4. Interactive What-If Policy Parameter Sliders */}
      <div className="pt-2 border-t border-border space-y-3.5">
        <div className="flex items-center justify-between">
          <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-ink-muted" />
            <span>What-If Policy Sliders</span>
          </div>
          <span className="text-xxs font-mono text-accent font-semibold">Instant Sim</span>
        </div>

        {/* Slider 1: Value Floor */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-ink-muted font-mono text-xxs">G2 Value Floor:</span>
            <span className="font-mono font-bold text-xs text-accent">Rs. {valueFloor}.00</span>
          </div>
          <input
            type="range"
            min="0"
            max="500"
            step="25"
            value={valueFloor}
            onChange={(e) => handleParamChange(Number(e.target.value), maxAttempts, confidenceFloor)}
            className="w-full accent-accent cursor-pointer h-1.5"
          />
          <div className="flex justify-between text-xxs font-mono text-ink-subtle">
            <span>Rs. 0</span>
            <span>Rs. 250</span>
            <span>Rs. 500</span>
          </div>
        </div>

        {/* Slider 2: Max Attempts */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-ink-muted font-mono text-xxs">G3 Max Attempts:</span>
            <span className="font-mono font-bold text-xs text-accent">{maxAttempts} attempts</span>
          </div>
          <input
            type="range"
            min="1"
            max="4"
            step="1"
            value={maxAttempts}
            onChange={(e) => handleParamChange(valueFloor, Number(e.target.value), confidenceFloor)}
            className="w-full accent-accent cursor-pointer h-1.5"
          />
          <div className="flex justify-between text-xxs font-mono text-ink-subtle">
            <span>1 attempt</span>
            <span>2</span>
            <span>3</span>
            <span>4</span>
          </div>
        </div>

        {/* Slider 3: Confidence Floor */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-ink-muted font-mono text-xxs">G6 Confidence Floor:</span>
            <span className="font-mono font-bold text-xs text-accent">{(confidenceFloor * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="0.30"
            max="0.95"
            step="0.05"
            value={confidenceFloor}
            onChange={(e) => handleParamChange(valueFloor, maxAttempts, Number(e.target.value))}
            className="w-full accent-accent cursor-pointer h-1.5"
          />
          <div className="flex justify-between text-xxs font-mono text-ink-subtle">
            <span>30%</span>
            <span>55%</span>
            <span>95%</span>
          </div>
        </div>

        <div className="text-xxs text-ink-subtle font-sans leading-tight">
          Adjusting sliders re-evaluates policy restraint against cached classifications without calling LLM endpoints.
        </div>
      </div>
    </aside>
  );
};
