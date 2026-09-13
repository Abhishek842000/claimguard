"use client";

import Link from "next/link";
import type { ClaimListItem } from "@/lib/api";

export function ClaimsList({ claims }: { claims: ClaimListItem[] }) {
  if (claims.length === 0) {
    return (
      <section className="panel">
        <h2>Claims</h2>
        <p>No claims yet. Submit a sample or upload documents above.</p>
      </section>
    );
  }
  return (
    <section className="panel">
      <h2>Claims</h2>
      <table className="plain-table">
        <thead>
          <tr>
            <th>Policy</th>
            <th>Status</th>
            <th>Incident</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.claim_id}>
              <td>{claim.policy_number}</td>
              <td>
                <span className={`pill pill-${claim.status}`}>{claim.status}</span>
              </td>
              <td>{claim.incident_type ?? "—"}</td>
              <td>
                <Link href={`/claims/${claim.claim_id}`}>Trace →</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
