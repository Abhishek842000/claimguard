"use client";

import { useEffect, useState } from "react";
import { ClaimsList } from "@/components/ClaimsList";
import { CostPanel } from "@/components/CostPanel";
import { SubmitForm } from "@/components/SubmitForm";
import { fetchClaims, fetchMetrics, fetchSamples, type ClaimListItem, type CostMetrics, type SampleClaim } from "@/lib/api";

export default function HomePage() {
  const [samples, setSamples] = useState<SampleClaim[]>([]);
  const [claims, setClaims] = useState<ClaimListItem[]>([]);
  const [metrics, setMetrics] = useState<CostMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [sampleRows, claimRows, cost] = await Promise.all([
          fetchSamples(),
          fetchClaims(),
          fetchMetrics(),
        ]);
        if (!cancelled) {
          setSamples(sampleRows);
          setClaims(claimRows);
          setMetrics(cost);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load dashboard");
        }
      }
    }
    void load();
    const timer = window.setInterval(() => {
      void fetchClaims().then(setClaims).catch(() => undefined);
      void fetchMetrics().then(setMetrics).catch(() => undefined);
    }, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <main>
      <h1>ClaimGuard</h1>
      <p>
        Submit a claim, watch the worker process it, then open the trace. Names,
        SSNs, and dates of birth are redacted before logs or Langfuse ever see them.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <SubmitForm samples={samples} />
      <CostPanel metrics={metrics} />
      <ClaimsList claims={claims} />
    </main>
  );
}
