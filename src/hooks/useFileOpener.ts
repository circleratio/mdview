import { useCallback } from "react";
import { exists, readTextFile } from "@tauri-apps/plugin-fs";
import { open } from "@tauri-apps/plugin-dialog";
import { dirname } from "@tauri-apps/api/path";
import { invoke } from "@tauri-apps/api/core";
import { useDocument } from "../state/DocumentContext";
import { useRecentFiles } from "./useRecentFiles";

export function useFileOpener() {
  const { setDocument, setError, setLoading } = useDocument();
  const { addRecentFile, removeRecentFile } = useRecentFiles();

  const loadFile = useCallback(
    async (path: string) => {
      setLoading(true);
      try {
        const fileExists = await exists(path);
        if (!fileExists) {
          throw new Error(`ファイルが見つかりません: ${path}`);
        }
        const content = await readTextFile(path);
        const dir = await dirname(path);
        setDocument(path, dir, content);
        await addRecentFile(path);
        await invoke("start_watching", { path });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        await removeRecentFile(path);
      } finally {
        setLoading(false);
      }
    },
    [setDocument, setError, setLoading, addRecentFile, removeRecentFile],
  );

  const openViaDialog = useCallback(async () => {
    const selected = await open({
      multiple: false,
      filters: [{ name: "Markdown", extensions: ["md", "markdown"] }],
    });
    if (typeof selected === "string") {
      await loadFile(selected);
    }
  }, [loadFile]);

  return { loadFile, openViaDialog };
}
