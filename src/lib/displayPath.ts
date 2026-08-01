/** Presentation-only helper: derive a filename to show in UI lists. Not for path resolution logic. */
export function basenameForDisplay(path: string): string {
  const segments = path.split(/[\\/]/);
  return segments[segments.length - 1] || path;
}
