// API Types & Schemas

export interface PolicyConfig {
  POLICY_CONFIG: {
    COST_OF_CONTACT_THRESHOLD_PAISE: number;
    MAX_RECOVERY_ATTEMPTS: number;
    COOLDOWN_HOURS: number;
    QUIET_HOURS_START_IST: number;
    QUIET_HOURS_END_IST: number;
    CONFIDENCE_FLOOR: number;
    ASSUMED_CONTACT_COST_INR: number;
  };
  gate_definitions: Array<{
    gate_id: string;
    name: string;
    description: string;
    default_threshold: string;
  }>;
}

export interface StartRunPayload {
  mode: 'agent' | 'baseline';
  seed: number;
  split?: string;
  reseed?: boolean;
  time_multiplier?: number;
  inject_llm_failure?: boolean;
}

export interface StartRunResponse {
  run_id: string;
  status: string;
  mode: string;
  stream_url: string;
  started_at: string;
}

export interface SSEEventData {
  event_type?: string;
  step_number?: number;
  payment_id?: string;
  order_id?: string;
  customer_name?: string;
  customer_city?: string;
  amount_rupees?: number;
  method?: string;
  failure_code?: string;
  failure_reason?: string;
  cart_summary?: string;
  classification?: {
    category: string;
    confidence: number;
    reasoning: string;
  };
  decision?: {
    action: string;
    delay_seconds: number;
    reason: string;
    gates_evaluated?: Array<{
      gate_id: string;
      name: string;
      status: string;
      reason: string;
    }>;
  };
  attempt_number?: number;
  payment_link_url?: string;
  status?: string;
  outcome?: string;
  state?: 'classifying' | 'decided' | 'outcome';
  // Completion metrics
  total_payments?: number;
  recovered_count?: number;
  recovered_value_rupees?: number;
  recovery_rate_pct?: number;
  suppressed_count?: number;
  total_attempts_made?: number;
}

export interface ComparisonReport {
  agent_run_id: string;
  baseline_run_id: string;
  seed: number;
  dataset_split: string;
  total_payments: number;
  value_at_risk_rupees: number;
  agent_recovered_count: number;
  agent_recovered_revenue: number;
  agent_recovery_rate_pct: number;
  baseline_recovered_count: number;
  baseline_recovered_revenue: number;
  baseline_recovery_rate_pct: number;
  net_recovery_rate_lift_pct: number;
  net_revenue_lift_rupees: number;
  relative_lift_multiplier: number;
  total_contacts_sent: number;
  total_contact_cost_rupees: number;
  net_roi_ratio: number;
  suppressed_count: number;
  suppressed_value_rupees: number;
  limitations: Record<string, string>;
}

export interface PaymentAuditTrail {
  payment_id: string;
  order_id: string;
  amount_rupees: number;
  currency: string;
  method: string;
  failure_code: string;
  failure_reason: string;
  failed_at: string;
  cart_summary: string;
  status: string;
  customer: {
    id: string;
    name: string;
    phone: string;
    email: string;
    city: string;
    history_total_payments: number;
    history_failed_payments: number;
    history_avg_days_to_pay: number;
    is_risk_flagged: boolean;
  };
  total_attempts: number;
  recovery_attempts: Array<{
    id: string;
    attempt_number: number;
    channel: string;
    action_taken: string;
    payment_link_id?: string;
    payment_link_url?: string;
    sent_at: string;
    outcome: string;
    outcome_at?: string;
  }>;
  audit_logs: Array<{
    id: string;
    stage: string;
    decision: string;
    reason: string;
    confidence?: number;
    input_summary?: string;
    policy_gates_evaluated?: Array<{
      gate_id: string;
      name: string;
      status: string;
      reason: string;
    }>;
    created_at: string;
  }>;
}

export interface ExceptionsResponse {
  run_id: string;
  total_exceptions: number;
  total_suppressed: number;
  total_suppressed_value_rupees: number;
  total_escalated: number;
  total_escalated_value_rupees: number;
  items: Array<{
    payment_id: string;
    order_id: string;
    customer_name: string;
    amount_rupees: number;
    status: string;
    type: string;
    reason: string;
    gate_triggered?: string;
  }>;
}

export interface SimulatePolicyResponse {
  total_evaluated: number;
  total_cohort_value_rupees: number;
  simulated_suppressed_count: number;
  simulated_suppressed_value_rupees: number;
  simulated_suppression_rate_pct: number;
  simulated_eligible_count: number;
  simulated_eligible_value_rupees: number;
  suppression_breakdown: Array<{
    gate_id: string;
    gate_name: string;
    count: number;
    value_rupees: number;
    percentage_of_batch: number;
  }>;
  action_distribution: Record<string, number>;
  parameters_applied: Record<string, any>;
  notes: string;
}
