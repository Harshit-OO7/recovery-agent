"""
CLI Entrypoint for Orchestrator Recovery Runs.

Usage:
  python -m app.orchestrator.run --mode agent --seed 42
  python -m app.orchestrator.run --mode baseline --seed 42
"""

import argparse
import sys
from typing import Optional

from app.config import settings
from app.data.generate import generate_dataset
from app.orchestrator.runner import run_batch, RunSummary


def print_comparison_table(agent_summary: RunSummary, baseline_summary: Optional[RunSummary] = None):
    sep = "=" * 82
    print("\n" + sep)
    print("  RAZORPAY AI REVENUE RECOVERY AGENT — BATCH ORCHESTRATION RUN")
    print(sep)
    print(f" Run ID:          {agent_summary.run_id}")
    print(f" Mode:            {agent_summary.mode.upper()}")
    print(f" Dataset Split:   {agent_summary.dataset_split.upper()}")
    print(f" Total Payments:  {agent_summary.total_payments} transactions (Total Value: Rs. {agent_summary.total_value_rupees:,.2f})")
    print(f" Total Attempts:  {agent_summary.total_attempts_made} outreach contacts")
    print(f" Audit Records:   {agent_summary.total_audit_logs} decision logs generated")

    print("\n" + "-" * 82)
    print(f" {'METRIC':<28} | {'AGENTIC RECOVERY':<22} | {'NO-INTERVENTION BASELINE':<24}")
    print("-" * 82)

    ag_rec = f"{agent_summary.recovered_count} ({agent_summary.recovery_rate_pct:.1f}%)"
    ag_val = f"Rs. {agent_summary.recovered_value_rupees:,.2f}"

    if baseline_summary:
        base_rec = f"{baseline_summary.recovered_count} ({baseline_summary.recovery_rate_pct:.1f}%)"
        base_val = f"Rs. {baseline_summary.recovered_value_rupees:,.2f}"
        lift_pct = agent_summary.recovery_rate_pct - baseline_summary.recovery_rate_pct
        lift_val = agent_summary.recovered_value_rupees - baseline_summary.recovered_value_rupees
    else:
        base_rec = "N/A"
        base_val = "N/A"
        lift_pct = 0.0
        lift_val = 0.0

    print(f" {'Recovered Transactions':<28} | {ag_rec:<22} | {base_rec:<24}")
    print(f" {'Recovered Revenue':<28} | {ag_val:<22} | {base_val:<24}")
    if baseline_summary:
        print(f" {'Net Recovery Lift':<28} | {f'+{lift_pct:.1f}% (+Rs. {lift_val:,.2f})':<22} | {'(Benchmark Baseline)':<24}")

    print(f" {'Suppressed (Restraint)':<28} | {f'{agent_summary.suppressed_count} ({agent_summary.suppression_rate_pct:.1f}%)':<22} | {'0 (N/A)':<24}")
    print(f" {'Abandoned / Unrecovered':<28} | {f'{agent_summary.abandoned_count} ({agent_summary.abandoned_rate_pct:.1f}%)':<22} | {f'{baseline_summary.abandoned_count if baseline_summary else 0}':<24}")

    # Time Audit Transparency
    ta = agent_summary.time_audit
    print("\n [Time-Compression Demo Clock Audit]")
    print(f"   * Real Policy Duration:     {ta.get('real_duration_hours', 0)} hours ({ta.get('real_duration_days', 0)} days)")
    print(f"   * Demo Accelerated Time:    {ta.get('compressed_duration_seconds', 0):.2f} seconds (Multiplier: {ta.get('demo_time_multiplier')}x)")
    print(f"   * Actual Wall-Clock Time:   {agent_summary.wall_clock_duration_seconds:.2f} seconds")

    if agent_summary.category_breakdown:
        print("\n [Root Cause Classification Breakdown]")
        for cat, cnt in sorted(agent_summary.category_breakdown.items(), key=lambda x: x[1], reverse=True):
            print(f"   * {cat:<24}: {cnt} items")

    print(sep + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run batch revenue recovery loop")
    parser.add_argument("--mode", choices=["agent", "baseline"], default="agent", help="Execution mode (agent or baseline)")
    parser.add_argument("--seed", type=int, default=settings.RANDOM_SEED, help="Random seed for data & simulation reproducibility")
    parser.add_argument("--split", choices=["train", "held_out", "all"], default="all", help="Dataset split filter")
    parser.add_argument("--no-reseed", action="store_true", help="Do not regenerate synthetic dataset before run")
    parser.add_argument("--compare-baseline", action="store_true", default=True, help="Also run baseline to print side-by-side lift")
    args = parser.parse_args()

    split_arg = None if args.split == "all" else args.split

    if not args.no_reseed:
        print(f"\n[1/3] Generating synthetic dataset (Seed={args.seed})...")
        generate_dataset(seed=args.seed, wipe_db=True)

    baseline_summary = None
    if args.mode == "agent" and args.compare_baseline:
        print(f"[2/3] Running counterfactual baseline on identical cohort...")
        baseline_summary = run_batch(mode="baseline", seed=args.seed, split=split_arg, sleep_between_steps=False)
        # Reseed so the agent runs on the clean database state
        generate_dataset(seed=args.seed, wipe_db=True)

    print(f"[3/3] Executing agentic recovery run loop (Mode={args.mode})...")
    agent_summary = run_batch(
        mode=args.mode,
        seed=args.seed,
        split=split_arg,
        sleep_between_steps=False,
    )

    print_comparison_table(agent_summary, baseline_summary)


if __name__ == "__main__":
    main()
