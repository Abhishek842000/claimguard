"use client";

import type { CostMetrics } from "@/lib/api";

export function CostPanel({ metrics }: { metrics: CostMetrics | null }) {
  if (!metrics) {
    return (
      <section className="panel">
        <h2>Model cost</h2>
        <p>Metrics unavailable.</p>
      </section>
    );
  }
  return (
    <section className="panel">
      <h2>Model cost</h2>
      <div className="stat-row">
        <div>
          <div className="stat-label">Running total</div>
          <div className="stat-value">${metrics.total_cost_usd}</div>
        </div>
        <div>
          <div className="stat-label">Avg / claim</div>
          <div className="stat-value">${metrics.average_cost_per_claim}</div>
        </div>
        <div>
          <div className="stat-label">Claims</div>
          <div className="stat-value">{metrics.claim_count}</div>
        </div>
      </div>
      {metrics.by_agent.length > 0 ? (
        <table className="plain-table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Cost</th>
              <th>Tokens</th>
              <th>Steps</th>
            </tr>
          </thead>
          <tbody>
            {metrics.by_agent.map((row) => (
              <tr key={row.agent}>
                <td>{row.agent}</td>
                <td>${row.cost_usd}</td>
                <td>{row.tokens}</td>
                <td>{row.steps}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No agent traces yet — submit a claim to populate this breakdown.</p>
      )}
    </section>
  );
}
