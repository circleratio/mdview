import { useState } from "react";
import { useFileOpener } from "../hooks/useFileOpener";
import { useRecentFiles } from "../hooks/useRecentFiles";
import { useDocument } from "../state/DocumentContext";
import { basenameForDisplay } from "../lib/displayPath";

export function Toolbar() {
  const { openViaDialog, loadFile } = useFileOpener();
  const { recentFiles } = useRecentFiles();
  const { path } = useDocument();
  const [isRecentOpen, setIsRecentOpen] = useState(false);

  return (
    <div className="toolbar">
      <button type="button" onClick={() => void openViaDialog()}>
        開く
      </button>
      <div className="toolbar__recent">
        <button
          type="button"
          disabled={recentFiles.length === 0}
          onClick={() => setIsRecentOpen((open) => !open)}
        >
          最近使ったファイル
        </button>
        {isRecentOpen && recentFiles.length > 0 && (
          <ul className="toolbar__recent-list">
            {recentFiles.map((recentPath) => (
              <li key={recentPath}>
                <button
                  type="button"
                  title={recentPath}
                  onClick={() => {
                    setIsRecentOpen(false);
                    void loadFile(recentPath);
                  }}
                >
                  {basenameForDisplay(recentPath)}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <span className="toolbar__current-path" title={path ?? undefined}>
        {path ? basenameForDisplay(path) : "ファイルが開かれていません"}
      </span>
    </div>
  );
}
