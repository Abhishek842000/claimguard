"use client";

import type { AgentTraceStep } from "@/lib/api";

const AGENT_LABEL: Record<string, string> = {
  intake_agent: "Intake",
  vision_agent: "Vision",
  fraud_agent: "Fraud",
  policy_agent: "Policy",
  adjudicator_agent: "Adjudicator",
  route_to_human: "Human review",
  auto_resolve: "Auto-resolve",
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function keyOutput(step: AgentTraceStep): string {
  const output = asRecord(step.output);
  const nested = asRecord(output.output ?? output);
  if (step.agent.includes("intake") && !nested.policy_number) {
    return "Parsed FNOL, notes, and entities.";
  }
  if (step.agent.includes("intake") && typeof nested.policy_number === "string") {
    const missing = Array.isArray(nested.missing_fields) ? nested.missing_fields.length : 0;
    return missing
      ? `Policy ${nested.policy_number} · ${missing} missing field(s)`
      : `Policy ${nested.policy_number}`;
  }
  if (step.agent.includes("route") || step.agent.includes("human")) {
    return "Routed to a human because a confidence or fraud gate fired.";
  }
  if (typeof nested.summary === "string") {
    return nested.summary;
  }
  if (typeof nested.justification === "string") {
    return nested.justification;
  }
  if (typeof nested.rationale === "string") {
    return nested.rationale;
  }
  if (typeof nested.narrative === "string") {
    return nested.narrative;
  }
  if (typeof nested.policy_number === "string") {
    return `Policy ${nested.policy_number}`;
  }
  if (typeof nested.coverage_status === "string") {
    return `Coverage: ${nested.coverage_status}`;
  }
  if (typeof nested.fraud_risk_score === "number") {
    return `Fraud score ${nested.fraud_risk_score.toFixed(2)}`;
  }
  if (typeof nested.overall_severity === "string") {
    return `Severity ${nested.overall_severity}`;
  }
  if (typeof nested.error === "string") {
    return nested.error;
  }
  if (step.status === "error") {
    return "Node failed — routed to human review.";
  }
  const keys = Object.keys(nested).filter((key) => key !== "claim_id").slice(0, 3);
  return keys.length ? keys.map((key) => `${key}: ${stringify(nested[key])}`).join(" · ") : "Completed.";
}

function confidence(step: AgentTraceStep): string | null {
  const output = asRecord(step.output);
  const nested = asRecord(output.output ?? output);
  const value = nested.confidence ?? nested.overall_confidence ?? nested.intake_confidence;
  return typeof value === "number" ? value.toFixed(2) : null;
}

function stringify(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value).slice(0, 80);
}

export function TraceTimeline({ steps }: { steps: AgentTraceStep[] }) {
  if (steps.length === 0) {
    return <p>Waiting for agent spans…</p>;
  }
  return (
    <ol className="timeline">
      {steps.map((step, index) => (
        <li key={`${step.agent}-${index}`} className={`timeline-item status-${step.status}`}>
          <div className="timeline-marker" aria-hidden />
          <div className="timeline-body">
            <div className="timeline-head">
              <strong>{AGENT_LABEL[step.agent] ?? step.agent}</strong>
              <span className={`pill pill-${step.status}`}>{step.status}</span>
            </div>
            <p className="timeline-output">{keyOutput(step)}</p>
            <div className="timeline-meta">
              <span>{step.latency_ms ?? 0} ms</span>
              {confidence(step) ? <span>confidence {confidence(step)}</span> : null}
              <span>${step.cost_usd}</span>
              {step.model ? <span>{step.model}</span> : null}
              {step.prompt_version ? <span>{step.prompt_version}</span> : null}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
