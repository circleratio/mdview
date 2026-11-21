import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useTabs } from "../state/TabsContext";
import { getSettingsStore } from "../lib/settingsStore";

const EDITOR_COMMAND_KEY = "editorCommand";
export const DEFAULT_EDITOR_COMMAND = "emacs";

/** Persisted "open in external editor" command, plus the action to launch it (button or Ctrl+E) against the active tab. */
export function useExternalEditor() {
  const { activeTabPath, setAppError } = useTabs();
  const [editorCommand, setEditorCommandState] = useState(DEFAULT_EDITOR_COMMAND);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const store = await getSettingsStore();
      const value = await store.get<string>(EDITOR_COMMAND_KEY);
      if (!cancelled && value) setEditorCommandState(value);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setEditorCommand = useCallback(async (command: string) => {
    const trimmed = command.trim();
    if (trimmed === "") return;
    const store = await getSettingsStore();
    await store.set(EDITOR_COMMAND_KEY, trimmed);
    setEditorCommandState(trimmed);
  }, []);

  const openInEditor = useCallback(async () => {
    if (!activeTabPath) return;
    try {
      await invoke("open_in_editor", { command: editorCommand, path: activeTabPath });
    } catch (err) {
      setAppError(err instanceof Error ? err.message : String(err));
    }
  }, [activeTabPath, editorCommand, setAppError]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "e") {
        event.preventDefault();
        void openInEditor();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [openInEditor]);

  return { editorCommand, setEditorCommand, openInEditor };
}
