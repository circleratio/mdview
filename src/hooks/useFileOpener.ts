import { useCallback, useRef } from "react";
import { exists, readTextFile } from "@tauri-apps/plugin-fs";
import { open } from "@tauri-apps/plugin-dialog";
import { dirname } from "@tauri-apps/api/path";
import { invoke } from "@tauri-apps/api/core";
import { useTabs } from "../state/TabsContext";
import { useRecentFiles } from "./useRecentFiles";

export function useFileOpener() {
  const { tabs, addPendingTab, setActiveTab, setTabDocument, setTabError, setTabLoading, removeTab, setAppError } =
    useTabs();
  const { addRecentFile, removeRecentFile } = useRecentFiles();

  // Read via ref (not a dependency) so openTab's identity stays stable across tab-state
  // changes (e.g. every search keystroke) instead of forcing effects that depend on it
  // (like DropZoneOverlay's drag&drop subscription) to tear down and resubscribe constantly.
  const tabsRef = useRef(tabs);
  tabsRef.current = tabs;

  const openTab = useCallback(
    async (path: string) => {
      if (tabsRef.current.some((tab) => tab.path === path)) {
        setActiveTab(path);
        return;
      }
      addPendingTab(path);
      try {
        const fileExists = await exists(path);
        if (!fileExists) {
          throw new Error(`ファイルが見つかりません: ${path}`);
        }
        const content = await readTextFile(path);
        const dir = await dirname(path);
        setTabDocument(path, dir, content);
        setAppError(null);
        await addRecentFile(path);
        await invoke("start_watching", { path });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        removeTab(path);
        setAppError(message);
        await removeRecentFile(path);
      }
    },
    [addPendingTab, setActiveTab, setTabDocument, removeTab, setAppError, addRecentFile, removeRecentFile],
  );

  const reloadTab = useCallback(
    async (path: string) => {
      setTabLoading(path, true);
      try {
        const fileExists = await exists(path);
        if (!fileExists) {
          throw new Error(`ファイルが見つかりません: ${path}`);
        }
        const content = await readTextFile(path);
        const dir = await dirname(path);
        setTabDocument(path, dir, content);
        await invoke("start_watching", { path });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setTabError(path, message);
        await removeRecentFile(path);
      }
    },
    [setTabLoading, setTabDocument, setTabError, removeRecentFile],
  );

  const openViaDialog = useCallback(async () => {
    const selected = await open({
      multiple: false,
      filters: [{ name: "Markdown", extensions: ["md", "markdown"] }],
    });
    if (typeof selected === "string") {
      await openTab(selected);
    }
  }, [openTab]);

  return { openTab, reloadTab, openViaDialog };
}
