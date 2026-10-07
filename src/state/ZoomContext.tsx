import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getSettingsStore } from "../lib/settingsStore";
import { normalizeZoom, stepZoom, ZOOM_DEFAULT } from "../lib/zoom";
import { useTabs } from "./TabsContext";

const CONTENT_ZOOM_KEY = "contentZoom";
const SAVE_DEBOUNCE_MS = 300;

/** Viewport point (clientX/clientY) that should stay visually fixed across a zoom change. */
export interface ZoomAnchor {
  x: number;
  y: number;
}

interface ZoomContextValue {
  zoomPercent: number;
  zoomIn: () => void;
  zoomOut: () => void;
  resetZoom: () => void;
  /** Wheel zoom: like zoomIn/zoomOut, but keeps the content under `anchor` (the cursor) in place. */
  zoomBy: (direction: 1 | -1, anchor: ZoomAnchor) => void;
  /** Returns and clears the anchor of the pending zoom change; null means "use the pane's top edge". */
  consumeAnchor: () => ZoomAnchor | null;
}

const ZoomContext = createContext<ZoomContextValue | null>(null);

/**
 * App-wide content zoom (requirements.md 3.11): one level shared by every tab, persisted to
 * settings.json, plus the Ctrl +/-/0 shortcuts. Each TabPane applies the level to its own DOM
 * via usePaneZoom; this context only owns the number and the anchor hand-off (spec.md 11.3).
 */
export function ZoomProvider({ children }: { children: ReactNode }) {
  const { activeTabPath } = useTabs();
  const [zoomPercent, setZoomPercent] = useState(ZOOM_DEFAULT);
  const [loaded, setLoaded] = useState(false);
  // Mirrors of state read from event handlers without re-subscribing them on every change.
  const zoomRef = useRef(ZOOM_DEFAULT);
  const changedByUserRef = useRef(false);
  // Held in a ref, not state: handing over the anchor must not trigger a re-render of its own.
  const anchorRef = useRef<ZoomAnchor | null>(null);

  const changeZoom = useCallback((next: number, anchor: ZoomAnchor | null) => {
    // A clamped no-op (already at the min/max) must not leave a stale anchor behind for a
    // later, unrelated zoom change to pick up.
    if (next === zoomRef.current) return;
    changedByUserRef.current = true;
    anchorRef.current = anchor;
    zoomRef.current = next;
    setZoomPercent(next);
  }, []);

  const zoomIn = useCallback(() => changeZoom(stepZoom(zoomRef.current, 1), null), [changeZoom]);
  const zoomOut = useCallback(() => changeZoom(stepZoom(zoomRef.current, -1), null), [changeZoom]);
  const resetZoom = useCallback(() => changeZoom(ZOOM_DEFAULT, null), [changeZoom]);
  const zoomBy = useCallback(
    (direction: 1 | -1, anchor: ZoomAnchor) => changeZoom(stepZoom(zoomRef.current, direction), anchor),
    [changeZoom],
  );
  const consumeAnchor = useCallback(() => {
    const anchor = anchorRef.current;
    anchorRef.current = null;
    return anchor;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const store = await getSettingsStore();
        const value = await store.get<unknown>(CONTENT_ZOOM_KEY);
        // Don't clobber a zoom change the user already made while the store was loading.
        if (!cancelled && !changedByUserRef.current && value !== undefined) {
          const restored = normalizeZoom(value);
          zoomRef.current = restored;
          setZoomPercent(restored);
        }
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // Skip until the persisted value has been read, so startup never writes the default back.
    if (!loaded) return;
    const timer = setTimeout(() => {
      void getSettingsStore().then((store) => store.set(CONTENT_ZOOM_KEY, zoomPercent));
    }, SAVE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [loaded, zoomPercent]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || activeTabPath === null) return;
      // ";" is the "+" key on JIS keyboards (Chrome treats Ctrl+; as zoom in too).
      if (event.key === "+" || event.key === "=" || event.key === ";" || event.code === "NumpadAdd") {
        event.preventDefault();
        zoomIn();
      } else if (event.key === "-" || event.code === "NumpadSubtract") {
        event.preventDefault();
        zoomOut();
      } else if (event.key === "0" || event.code === "Numpad0") {
        event.preventDefault();
        resetZoom();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [activeTabPath, zoomIn, zoomOut, resetZoom]);

  const value = useMemo<ZoomContextValue>(
    () => ({ zoomPercent, zoomIn, zoomOut, resetZoom, zoomBy, consumeAnchor }),
    [zoomPercent, zoomIn, zoomOut, resetZoom, zoomBy, consumeAnchor],
  );

  return <ZoomContext.Provider value={value}>{children}</ZoomContext.Provider>;
}

export function useZoom(): ZoomContextValue {
  const ctx = useContext(ZoomContext);
  if (!ctx) {
    throw new Error("useZoom must be used within a ZoomProvider");
  }
  return ctx;
}
