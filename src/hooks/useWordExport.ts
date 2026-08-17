import { useCallback } from "react";
import { save } from "@tauri-apps/plugin-dialog";
import { writeFile } from "@tauri-apps/plugin-fs";
import { useTabs } from "../state/TabsContext";
import { convertMarkdownToDocx } from "../lib/docxExport";
import { basenameForDisplay } from "../lib/displayPath";

function defaultDocxPath(tab: { path: string; dir: string | null }): string {
  const fileName = basenameForDisplay(tab.path).replace(/\.(md|markdown)$/i, "") + ".docx";
  return tab.dir ? `${tab.dir}\\${fileName}` : fileName;
}

/**
 * Finds the active tab's rendered container by its `data-tab-path` attribute (set in TabPane),
 * not `document.getElementById`: every open tab stays mounted (see spec.md 4.4), so this keeps
 * the Mermaid/KaTeX lookup scoped to the correct tab even if other tabs share DOM structure.
 */
function findTabContainer(path: string): HTMLElement | null {
  const panes = document.querySelectorAll<HTMLElement>(".tab-pane");
  for (const pane of panes) {
    if (pane.dataset.tabPath === path) return pane;
  }
  return null;
}

/** Converts the active tab to a `.docx` file and saves it via a native save dialog (requirements.md 3.10, spec.md 6). */
export function useWordExport() {
  const { activeTab, setAppError } = useTabs();

  const exportActiveTabToDocx = useCallback(async () => {
    if (!activeTab || activeTab.content === null) return;
    try {
      const destination = await save({
        title: "Word形式で保存",
        defaultPath: defaultDocxPath(activeTab),
        filters: [{ name: "Word Document", extensions: ["docx"] }],
      });
      if (!destination) return;
      const container = findTabContainer(activeTab.path);
      const bytes = await convertMarkdownToDocx({ content: activeTab.content, dir: activeTab.dir, container });
      await writeFile(destination, bytes);
      setAppError(null);
    } catch (err) {
      setAppError(err instanceof Error ? err.message : String(err));
    }
  }, [activeTab, setAppError]);

  return { exportActiveTabToDocx };
}
