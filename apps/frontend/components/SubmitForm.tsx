"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import type { SampleClaim } from "@/lib/api";
import { submitSample, uploadClaim } from "@/lib/api";

export function SubmitForm({ samples }: { samples: SampleClaim[] }) {
  const router = useRouter();
  const [sourceDir, setSourceDir] = useState(samples[0]?.source_dir ?? "");
  const [notes, setNotes] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"sample" | "upload" | null>(null);

  useEffect(() => {
    if (!sourceDir && samples[0]?.source_dir) {
      setSourceDir(samples[0].source_dir);
    }
  }, [samples, sourceDir]);

  async function onSample(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy("sample");
    try {
      const result = await submitSample(sourceDir);
      router.push(`/claims/${result.claim_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy(null);
    }
  }

  async function onUpload(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy("upload");
    try {
      const result = await uploadClaim(files, notes);
      router.push(`/claims/${result.claim_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="panel">
      <h2>Submit a claim</h2>
      <form className="stack" onSubmit={onSample}>
        <label>
          Sample folder
          <select value={sourceDir} onChange={(event) => setSourceDir(event.target.value)}>
            {samples.map((sample) => (
              <option key={sample.claim_id} value={sample.source_dir}>
                {sample.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy !== null || !sourceDir}>
          {busy === "sample" ? "Enqueueing…" : "Run sample claim"}
        </button>
      </form>
      <hr />
      <form className="stack" onSubmit={onUpload}>
        <label>
          Upload docs / images
          <input
            type="file"
            multiple
            accept=".pdf,.txt,.md,.jpg,.jpeg,.png,.webp"
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
        </label>
        <label>
          Adjuster notes
          <textarea
            rows={3}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Optional notes sent through the same PII-redacted path as sample claims."
          />
        </label>
        <button type="submit" disabled={busy !== null || (files.length === 0 && notes.trim() === "")}>
          {busy === "upload" ? "Uploading…" : "Upload and process"}
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}
