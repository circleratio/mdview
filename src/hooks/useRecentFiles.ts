import { useCallback, useEffect, useState } from "react";
import { load, type Store } from "@tauri-apps/plugin-store";

const STORE_FILE = "recent-files.json";
const RECENTS_KEY = "recentFiles";
const MAX_RECENTS = 10;

let storePromise: Promise<Store> | null = null;
function getStore(): Promise<Store> {
  if (!storePromise) {
    storePromise = load(STORE_FILE, { autoSave: true });
  }
  return storePromise;
}

export function useRecentFiles() {
  const [recentFiles, setRecentFiles] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const store = await getStore();
      const value = (await store.get<string[]>(RECENTS_KEY)) ?? [];
      if (!cancelled) setRecentFiles(value);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const addRecentFile = useCallback(async (path: string) => {
    const store = await getStore();
    const current = (await store.get<string[]>(RECENTS_KEY)) ?? [];
    const next = [path, ...current.filter((p) => p !== path)].slice(0, MAX_RECENTS);
    await store.set(RECENTS_KEY, next);
    setRecentFiles(next);
  }, []);

  const removeRecentFile = useCallback(async (path: string) => {
    const store = await getStore();
    const current = (await store.get<string[]>(RECENTS_KEY)) ?? [];
    const next = current.filter((p) => p !== path);
    await store.set(RECENTS_KEY, next);
    setRecentFiles(next);
  }, []);

  return { recentFiles, addRecentFile, removeRecentFile };
}
