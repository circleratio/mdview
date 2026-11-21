import { load, type Store } from "@tauri-apps/plugin-store";

const STORE_FILE = "settings.json";

let storePromise: Promise<Store> | null = null;

/** Shared handle to `settings.json` (editor command, content zoom), loaded once and reused. */
export function getSettingsStore(): Promise<Store> {
  if (!storePromise) {
    storePromise = load(STORE_FILE, { autoSave: true });
  }
  return storePromise;
}
