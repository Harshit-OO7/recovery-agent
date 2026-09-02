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
  onRunBatch: () => void;
  onResetDataset: () => void;
  isRunning: boolean;
  onSimulateSlider: (valueFloor: number) => void;
}

export const PolicyConfigPanel: React.FC<PolicyConfigPanelProps> = ({
  policyConfig,
  mode,
  setMode,
  seed,
  setSeed,
  timeMultiplier,
  setTimeMultiplier,
  onRunBatch,
  onResetDataset,
  isRunning,
  onSimulateSlider,
}) => {
  const [sliderVal, setSliderVal] = useState<number>(100);

  // Time compression calculation helper
  // Real cooldown: 24h (86,400s). At 28,800x -> 3.0s.
  const cooldownRealHours = policyConfig?.POLICY_CONFIG.COOLDOWN_HOURS || 24;
  const cooldownCompressedSecs = (cooldownRealHours * 3600 / timeMultiplier).toFixed(1);

  const handleSliderChange = (newVal: number) => {
    setSliderVal(newVal);
    onSimulateSlider(newVal);
  };

  return (
    <aside className="w-80 border-r border-border bg-surface p-5 flex flex-col gap-5 overflow-y-auto shrink-0 select-none">
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

      {/* 2. Run Parameters (Seed & Demo Clock Speed) */}
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

      {/* 3. Live Deterministic Policy Config Panel */}
      <div className="pt-2 border-t border-border space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-accent" />
            <span>Deterministic Policy Gates</span>
          </div>
          <Badge variant="accent" size="sm">7 Gates</Badge>
        </div>

        <div className="space-y-1.5 text-xs">
          {/* G1 */}
          <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
            <div>
              <div className="font-mono text-xs font-semibold text-ink">G1 do_not_contact</div>
              <div className="text-xxs text-ink-muted font-sans">Risk flagged / opted out</div>
            </div>
            <Badge variant="suppressed" size="sm">Permanent</Badge>
          </div>

          {/* G2 */}
          <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
            <div>
              <div className="font-mono text-xs font-semibold text-ink">G2 value_floor</div>
              <div className="text-xxs text-ink-muted font-sans">Outreach cost floor</div>
            </div>
            <span className="font-mono text-xs font-bold text-ink">
              Rs. {((policyConfig?.POLICY_CONFIG.COST_OF_CONTACT_THRESHOLD_PAISE || 10000) / 100).toFixed(2)}
            </span>
          </div>

          {/* G3 */}
          <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
            <div>
              <div className="font-mono text-xs font-semibold text-ink">G3 max_attempts</div>
              <div className="text-xxs text-ink-muted font-sans">Fatigue stopping rule</div>
            </div>
            <span className="font-mono text-xs font-bold text-ink">
              {policyConfig?.POLICY_CONFIG.MAX_RECOVERY_ATTEMPTS || 2} attempts max
            </span>
          </div>

          {/* G4 */}
          <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
            <div>
              <div className="font-mono text-xs font-semibold text-ink">G4 cooldown</div>
              <div className="text-xxs text-ink-muted font-sans">
                Real: <span className="font-mono font-medium">{cooldownRealHours}h</span> ? Demo: <span className="font-mono font-medium">{cooldownCompressedSecs}s</span>
              </div>
            </div>
            <span className="font-mono text-xs font-bold text-ink">24.0h</span>
          </div>

          {/* G5 */}
          <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
            <div>
              <div className="font-mono text-xs font-semibold text-ink">G5 quiet_hours</div>
              <div className="text-xxs text-ink-muted font-sans">09:00 - 20:00 IST</div>
            </div>
            <Badge variant="neutral" size="sm">Daytime Only</Badge>
          </div>

          {/* G6 */}
          <div className="p-2.5 rounded bg-surface-raised border border-border flex justify-between items-center">
            <div>
              <div className="font-mono text-xs font-semibold text-ink">G6 confidence_floor</div>
              <div className="text-xxs text-ink-muted font-sans">Escalate ambiguous cases</div>
            </div>
            <span className="font-mono text-xs font-bold text-ink">
              {((policyConfig?.POLICY_CONFIG.CONFIDENCE_FLOOR || 0.55) * 100).toFixed(0)}% min
            </span>
          </div>
        </div>
      </div>

      {/* 4. Interactive What-If Parameter Slider */}
      <div className="pt-2 border-t border-border">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xxs text-ink-muted font-mono uppercase tracking-wider flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-ink-muted" />
            <span>What-If Value Floor</span>
          </div>
          <span className="font-mono text-xs font-bold text-accent">
            Rs. {sliderVal}.00
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="500"
          step="25"
          value={sliderVal}
          onChange={(e) => handleSliderChange(Number(e.target.value))}
          className="w-full accent-accent cursor-pointer"
        />
        <div className="flex justify-between text-xxs font-mono text-ink-subtle mt-1">
          <span>Rs. 0</span>
          <span>Rs. 250</span>
          <span>Rs. 500</span>
        </div>
        <div className="text-xxs text-ink-subtle mt-1.5 font-sans">
          Re-runs policy without re-calling LLM APIs.
        </div>
      </div>
    </aside>
  );
};
