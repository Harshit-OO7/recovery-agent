import { 
  PolicyConfig, 
  StartRunPayload, 
  StartRunResponse, 
  ComparisonReport, 
  PaymentAuditTrail, 
  ExceptionsResponse,
  SimulatePolicyResponse 
} from './types';

const API_BASE = '/api';

export async function fetchPolicyConfig(): Promise<PolicyConfig> {
  const res = await fetch(`${API_BASE}/policy`);
  if (!res.ok) throw new Error('Failed to fetch policy configuration');
  return res.json();
}

export async function startRecoveryRun(payload: StartRunPayload): Promise<StartRunResponse> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to start recovery run');
  return res.json();
}

export async function fetchComparisonReport(seed: number = 42): Promise<ComparisonReport> {
  const res = await fetch(`${API_BASE}/runs/compare?seed=${seed}`);
  if (!res.ok) throw new Error('Failed to fetch comparative uplift report');
  return res.json();
}

export async function fetchPaymentAuditTrail(paymentId: string): Promise<PaymentAuditTrail> {
  const res = await fetch(`${API_BASE}/payments/${paymentId}/audit`);
  if (!res.ok) throw new Error(`Failed to fetch audit trail for payment ${paymentId}`);
  return res.json();
}

export async function fetchRunExceptions(runId: string): Promise<ExceptionsResponse> {
  const res = await fetch(`${API_BASE}/runs/${runId}/exceptions`);
  if (!res.ok) throw new Error('Failed to fetch run exceptions');
  return res.json();
}

export async function simulateWhatIfPolicy(params: {
  cost_of_contact_threshold_rupees?: number;
  max_recovery_attempts?: number;
  confidence_floor?: number;
  cooldown_hours?: number;
}): Promise<SimulatePolicyResponse> {
  const res = await fetch(`${API_BASE}/policy/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error('Failed to simulate policy parameters');
  return res.json();
}
