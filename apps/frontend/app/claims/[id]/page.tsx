type ClaimTracePageProps = {
  params: Promise<{ id: string }>;
};

export default async function ClaimTracePage({ params }: ClaimTracePageProps) {
  const { id } = await params;
  return (
    <main>
      <h1>Claim {id}</h1>
      <p>Agent trace viewer — implemented when the worker persists spans.</p>
      <section className="panel">
        <h2>Expected chain</h2>
        <p>intake → vision / fraud / policy → adjudicator → routing decision</p>
      </section>
    </main>
  );
}
