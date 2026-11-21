import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";
import { useZoom, type ZoomAnchor } from "../state/ZoomContext";

const ZOOM_VAR = "--content-zoom";
/** Accumulated pixel delta per zoom step: a mouse notch (~100px) is one step; touchpad pinches send many small deltas. */
const WHEEL_STEP_THRESHOLD = 50;

interface CapturedAnchor {
  element: Element;
  /** Where the anchor point fell within the element, as a fraction of its height. */
  ratio: number;
  /** Viewport y the anchor point must stay at. */
  y: number;
}

/** Default anchor for keyboard/toolbar zoom: the pane's top edge, horizontally centered. */
function topAnchor(container: HTMLElement): ZoomAnchor {
  const rect = container.getBoundingClientRect();
  return { x: rect.left + rect.width / 2, y: rect.top + 1 };
}

function captureAnchor(container: HTMLElement, point: ZoomAnchor): CapturedAnchor | null {
  let element = document.elementFromPoint(point.x, point.y);
  // Outside the rendered article (pane padding, or a point covered by something else): fall
  // back to the article itself, which degrades to "keep the same fraction of the document".
  if (!element || element === container || !container.contains(element)) {
    element = container.querySelector(".markdown-body");
  }
  if (!element) return null;
  const rect = element.getBoundingClientRect();
  const ratio = rect.height > 0 ? (point.y - rect.top) / rect.height : 0;
  return { element, ratio, y: point.y };
}

function restoreAnchor(container: HTMLElement, anchor: CapturedAnchor) {
  const rect = anchor.element.getBoundingClientRect();
  const currentY = rect.top + anchor.ratio * rect.height;
  container.scrollTop += currentY - anchor.y;
}

/**
 * Applies the shared content zoom to one tab's `.markdown-view` (the scroll container) by
 * setting the `--content-zoom` variable that `.markdown-body`'s CSS `zoom` reads (spec.md 11.4).
 *
 * The variable is written imperatively inside a layout effect rather than through React's
 * `style` prop: the scroll correction needs to measure the *old* layout first, then apply the
 * new zoom, then measure again — all before the browser paints.
 *
 * Hidden (display:none) tabs can't be measured or scrolled, so they keep their last applied
 * zoom and catch up the next time they become active.
 */
export function usePaneZoom(containerRef: RefObject<HTMLElement | null>, isActive: boolean, hasContent: boolean) {
  const { zoomPercent, zoomBy, consumeAnchor } = useZoom();
  const appliedZoomRef = useRef<number | null>(null);
  const wheelAccumRef = useRef(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!hasContent || !container) return;
    const handler = (event: WheelEvent) => {
      if (!event.ctrlKey) return; // plain wheel keeps scrolling
      event.preventDefault();
      if (event.deltaY === 0) return;
      const direction: 1 | -1 = event.deltaY < 0 ? 1 : -1;
      const anchor = { x: event.clientX, y: event.clientY };
      if (event.deltaMode !== WheelEvent.DOM_DELTA_PIXEL) {
        zoomBy(direction, anchor);
        return;
      }
      // Reversing direction discards whatever was accumulated the other way.
      if (Math.sign(wheelAccumRef.current) !== Math.sign(event.deltaY)) wheelAccumRef.current = 0;
      wheelAccumRef.current += event.deltaY;
      if (Math.abs(wheelAccumRef.current) >= WHEEL_STEP_THRESHOLD) {
        wheelAccumRef.current = 0;
        zoomBy(direction, anchor);
      }
    };
    // Registered natively: React's onWheel is passive, so it couldn't preventDefault the scroll.
    container.addEventListener("wheel", handler, { passive: false });
    return () => container.removeEventListener("wheel", handler);
  }, [containerRef, hasContent, zoomBy]);

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!isActive || !hasContent || !container) {
      // The view is unmounted while (re)loading, so whatever was applied to it is gone too.
      if (!hasContent) appliedZoomRef.current = null;
      return;
    }

    const anchorPoint = consumeAnchor();
    if (appliedZoomRef.current === zoomPercent) return;

    const factor = String(zoomPercent / 100);
    if (appliedZoomRef.current === null) {
      // Freshly rendered content starts scrolled to the top: nothing to keep in place.
      container.style.setProperty(ZOOM_VAR, factor);
    } else {
      const anchor = captureAnchor(container, anchorPoint ?? topAnchor(container));
      container.style.setProperty(ZOOM_VAR, factor);
      if (anchor) restoreAnchor(container, anchor);
    }
    appliedZoomRef.current = zoomPercent;
  }, [containerRef, isActive, hasContent, zoomPercent, consumeAnchor]);
}
