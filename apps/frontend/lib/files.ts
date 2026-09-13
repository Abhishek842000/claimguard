/** Append picker results instead of replacing. HTML file inputs only expose the last open. */
export function mergeSelectedFiles(current: File[], incoming: File[]): File[] {
  const next = [...current];
  const seen = new Set(current.map(fileKey));
  for (const file of incoming) {
    const key = fileKey(file);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    next.push(file);
  }
  return next;
}

export function fileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}
