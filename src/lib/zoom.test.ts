import { describe, expect, it } from "vitest";
import { normalizeZoom, stepZoom, ZOOM_DEFAULT, ZOOM_MAX, ZOOM_MIN } from "./zoom";

describe("stepZoom", () => {
  it("steps by 10 in either direction", () => {
    expect(stepZoom(100, 1)).toBe(110);
    expect(stepZoom(100, -1)).toBe(90);
  });

  it("stops at the upper bound", () => {
    expect(stepZoom(290, 1)).toBe(ZOOM_MAX);
    expect(stepZoom(ZOOM_MAX, 1)).toBe(ZOOM_MAX);
  });

  it("stops at the lower bound", () => {
    expect(stepZoom(60, -1)).toBe(ZOOM_MIN);
    expect(stepZoom(ZOOM_MIN, -1)).toBe(ZOOM_MIN);
  });

  it("reaches 300 from 100 in 20 steps without drift", () => {
    let zoom = 100;
    for (let i = 0; i < 20; i++) zoom = stepZoom(zoom, 1);
    expect(zoom).toBe(300);
  });
});

describe("normalizeZoom", () => {
  it("falls back to the default for non-numeric values", () => {
    expect(normalizeZoom(undefined)).toBe(ZOOM_DEFAULT);
    expect(normalizeZoom(null)).toBe(ZOOM_DEFAULT);
    expect(normalizeZoom("150")).toBe(ZOOM_DEFAULT);
    expect(normalizeZoom(Number.NaN)).toBe(ZOOM_DEFAULT);
    expect(normalizeZoom(Number.POSITIVE_INFINITY)).toBe(ZOOM_DEFAULT);
  });

  it("clamps out-of-range values", () => {
    expect(normalizeZoom(1000)).toBe(ZOOM_MAX);
    expect(normalizeZoom(20)).toBe(ZOOM_MIN);
  });

  it("snaps to the step grid", () => {
    expect(normalizeZoom(123)).toBe(120);
    expect(normalizeZoom(125)).toBe(130);
    expect(normalizeZoom(150)).toBe(150);
  });
});
