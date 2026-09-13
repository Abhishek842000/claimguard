export type SampleClaim = {
  claim_id: string;
  source_dir: string;
  label: string;
};

export type ClaimListItem = {
  claim_id: string;
  status: string;
  policy_number: string;
  incident_type: string | null;
  created_at: string | null;
};

export type AgentTraceStep = {
  agent: string;
  status: string;
  prompt_version: string | null;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: string;
  latency_ms: number | null;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
};

export type ClaimDetail = {
  claim_id: string;
  status: string;
  policy_number: string;
  incident_type: string | null;
  error: string | null;
  intake: Record<string, unknown> | null;
  verdict: Record<string, unknown> | null;
  trace: AgentTraceStep[];
};

export type CostMetrics = {
  total_cost_usd: string;
  claim_count: number;
  average_cost_per_claim: string;
  by_agent: { agent: string; cost_usd: string; tokens: number; steps: number }[];
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/claimguard${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    let message = detail || `${response.status} ${response.statusText}`;
    try {
      const parsed = JSON.parse(detail) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        message = parsed.detail;
      }
    } catch {
      // keep the raw body
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export function fetchSamples(): Promise<SampleClaim[]> {
  return api("/v1/claims/samples");
}

export function fetchClaims(): Promise<ClaimListItem[]> {
  return api("/v1/claims");
}

export function fetchClaim(id: string): Promise<ClaimDetail> {
  return api(`/v1/claims/${id}`, { cache: "no-store" });
}

export function fetchMetrics(): Promise<CostMetrics> {
  return api("/v1/metrics");
}

export function submitSample(sourceDir: string): Promise<{ claim_id: string; status: string }> {
  return api("/v1/claims", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ source_dir: sourceDir }),
  });
}

export function uploadClaim(files: File[], notes: string): Promise<{ claim_id: string; status: string }> {
  const body = new FormData();
  for (const file of files) {
    body.append("files", file);
  }
  if (notes.trim()) {
    body.append("notes", notes);
  }
  return api("/v1/claims/upload", { method: "POST", body });
}
