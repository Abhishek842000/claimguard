"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { TraceTimeline } from "@/components/TraceTimeline";
import { VerdictCard } from "@/components/VerdictCard";
import { fetchClaim, type ClaimDetail } from "@/lib/api";

const TERMINAL = new Set(["needs_review", "auto_resolved", "failed"]);

export default function ClaimDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [detail, setDetail] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const next = await fetchClaim(id);
        if (!cancelled) {
          setDetail(next);
          setError(null);
        }
        return TERMINAL.has(next.status);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load claim");
        }
        return false;
      }
    }
    void poll();
    const timer = window.setInterval(() => {
      void poll().then((done) => {
        if (done) {
          window.clearInterval(timer);
        }
      });
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [id]);

  return (
    <main>
      <p>
        <Link href="/">← Claims</Link>
      </p>
      <h1>Claim {id.slice(0, 8)}</h1>
      {error ? <p className="error">{error}</p> : null}
      <VerdictCard
        verdict={detail?.verdict ?? null}
        status={detail?.status ?? "received"}
        policyNumber={detail?.policy_number ?? "—"}
      />
      <section className="panel">
        <h2>Agent trace</h2>
        <p>Each node: what it decided, how confident it was, and how long it took.</p>
        <TraceTimeline steps={detail?.trace ?? []} />
      </section>
    </main>
  );
}
