export default function HomePage() {
  return (
    <main>
      <h1>ClaimGuard</h1>
      <p>
        Multi-agent insurance claims triage. This dashboard will show per-claim
        severity, fraud risk, cited policy clauses, and the full agent trace —
        not just the final verdict.
      </p>
      <section className="panel">
        <h2>Phase 0</h2>
        <p>
          Frontend scaffold only. Submit + trace views land with the API in later
          phases. API health lives at <code>GET http://localhost:8000/health</code>.
        </p>
      </section>
    </main>
  );
}
