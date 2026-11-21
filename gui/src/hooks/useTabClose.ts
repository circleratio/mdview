import { useCallback, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useTabs } from "../state/TabsContext";

/** Closes a tab (drops it from TabsContext and stops its Rust-side file watcher); Ctrl+W closes the active tab. */
export function useTabClose() {
  const { activeTabPath, removeTab } = useTabs();

  const closeTab = useCallback(
    (path: string) => {
      removeTab(path);
      void invoke("stop_watching", { path });
    },
    [removeTab],
  );

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "w") {
        if (!activeTabPath) return;
        event.preventDefault();
        closeTab(activeTabPath);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [activeTabPath, closeTab]);

  return { closeTab };
}
