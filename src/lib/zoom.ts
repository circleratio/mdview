/**
 * Content zoom level, held as an integer percentage (not a float factor) so repeated
 * steps never drift (e.g. 1.1 + 0.1 + ...). Converted to a CSS `zoom` factor only at the
 * point of applying it (see spec.md 11.2).
 */
export const ZOOM_MIN = 50;
export const ZOOM_MAX = 300;
export const ZOOM_STEP = 10;
export const ZOOM_DEFAULT = 100;

function clamp(value: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, value));
}

/** One zoom step in the given direction (+1 = in, -1 = out), clamped to the allowed range. */
export function stepZoom(current: number, direction: 1 | -1): number {
  return clamp(normalizeZoom(current) + direction * ZOOM_STEP);
}

/** Validates a persisted/untrusted value: non-numbers fall back to the default, others are clamped and snapped to the step grid. */
export function normalizeZoom(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return ZOOM_DEFAULT;
  return clamp(Math.round(value / ZOOM_STEP) * ZOOM_STEP);
}
