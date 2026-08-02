import { useEffect, useRef } from "react";
import { listen } from "@tauri-apps/api/event";
import { useTabs } from "../state/TabsContext";
import { useFileOpener } from "./useFileOpener";

/**
 * Reloads whichever open tab's file the Rust-side watcher reports a change to. Subscribes
 * once for the app's lifetime (not per tab); the current tab list is read via a ref so the
 * subscription never needs to be torn down and re-created as tabs open/close.
 */
export function useFileWatcher() {
  const { tabs } = useTabs();
  const { reloadTab } = useFileOpener();

  const tabsRef = useRef(tabs);
  tabsRef.current = tabs;

  useEffect(() => {
    const unlistenPromise = listen<string>("file-changed", (event) => {
      if (tabsRef.current.some((tab) => tab.path === event.payload)) {
        void reloadTab(event.payload);
      }
    });

    return () => {
      void unlistenPromise.then((unlisten) => unlisten());
    };
  }, [reloadTab]);
}
