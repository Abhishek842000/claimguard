"use client";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function VerdictCard({
  verdict,
  status,
  policyNumber,
}: {
  verdict: Record<string, unknown> | null;
  status: string;
  policyNumber: string;
}) {
  if (!verdict) {
    return (
      <section className="panel">
        <h2>Verdict</h2>
        <p>
          Status <span className={`pill pill-${status}`}>{status}</span> — pipeline still running.
        </p>
      </section>
    );
  }
  const memo = asRecord(verdict.settlement_memo);
  const coverage = asRecord(verdict.coverage);
  const reasons = Array.isArray(verdict.routing_reasons)
    ? verdict.routing_reasons.map(String)
    : [];
  return (
    <section className="panel">
      <h2>Verdict</h2>
      <div className="stat-row">
        <div>
          <div className="stat-label">Routing</div>
          <div className="stat-value">{String(verdict.routing ?? status)}</div>
        </div>
        <div>
          <div className="stat-label">Fraud</div>
          <div className="stat-value">{String(verdict.fraud_risk_score ?? "—")}</div>
        </div>
        <div>
          <div className="stat-label">Confidence</div>
          <div className="stat-value">{String(verdict.overall_confidence ?? "—")}</div>
        </div>
        <div>
          <div className="stat-label">Policy</div>
          <div className="stat-value">{policyNumber}</div>
        </div>
      </div>
      {typeof memo.summary === "string" ? <p>{memo.summary}</p> : null}
      {typeof coverage.coverage_status === "string" ? (
        <p>Coverage: {coverage.coverage_status}</p>
      ) : null}
      {reasons.length > 0 ? (
        <ul>
          {reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
