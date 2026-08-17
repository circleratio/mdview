import { useRef, useState } from "react";
import { useFileOpener } from "../hooks/useFileOpener";
import { useRecentFiles } from "../hooks/useRecentFiles";
import { useExternalEditor } from "../hooks/useExternalEditor";
import { useWordExport } from "../hooks/useWordExport";
import { useSearchShortcut } from "../hooks/useSearch";
import { useTabs } from "../state/TabsContext";
import { basenameForDisplay } from "../lib/displayPath";
import { FolderIcon, HistoryIcon, PencilIcon, WordSaveIcon } from "./icons";

export function Toolbar() {
  const { openViaDialog, openTab } = useFileOpener();
  const { recentFiles } = useRecentFiles();
  const { editorCommand, setEditorCommand, openInEditor } = useExternalEditor();
  const { exportActiveTabToDocx } = useWordExport();
  const { activeTabPath, activeTab, setTabSearchQuery, searchGoToNext, searchGoToPrev, clearTabSearch } = useTabs();
  const [isRecentOpen, setIsRecentOpen] = useState(false);
  const [isEditorSettingsOpen, setIsEditorSettingsOpen] = useState(false);
  const [editorCommandDraft, setEditorCommandDraft] = useState(editorCommand);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  useSearchShortcut(searchInputRef);

  const search = activeTab?.search ?? { query: "", matchCount: 0, currentIndex: 0 };

  return (
    <div className="toolbar">
      <button
        type="button"
        className="toolbar__icon-btn"
        title="開く"
        aria-label="開く"
        onClick={() => void openViaDialog()}
      >
        <FolderIcon />
      </button>
      <div className="toolbar__recent">
        <button
          type="button"
          className="toolbar__icon-btn"
          title="最近使ったファイル"
          aria-label="最近使ったファイル"
          disabled={recentFiles.length === 0}
          onClick={() => setIsRecentOpen((open) => !open)}
        >
          <HistoryIcon />
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
                    void openTab(recentPath);
                  }}
                >
                  {basenameForDisplay(recentPath)}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <button
        type="button"
        className="toolbar__icon-btn"
        disabled={activeTabPath === null}
        title={`${editorCommand} で開く（Ctrl+E）`}
        aria-label="エディタで開く"
        onClick={() => void openInEditor()}
      >
        <PencilIcon />
      </button>
      <button
        type="button"
        className="toolbar__icon-btn"
        disabled={activeTabPath === null}
        title="Word形式で保存"
        aria-label="Word形式で保存"
        onClick={() => void exportActiveTabToDocx()}
      >
        <WordSaveIcon />
      </button>
      <div className="toolbar__editor-settings">
        <button
          type="button"
          className="toolbar__icon-btn"
          aria-label="エディタ設定"
          title="外部エディタのコマンドを変更"
          onClick={() => {
            setEditorCommandDraft(editorCommand);
            setIsEditorSettingsOpen((open) => !open);
          }}
        >
          ⚙
        </button>
        {isEditorSettingsOpen && (
          <form
            className="toolbar__editor-settings-panel"
            onSubmit={(e) => {
              e.preventDefault();
              void setEditorCommand(editorCommandDraft);
              setIsEditorSettingsOpen(false);
            }}
          >
            <label htmlFor="editor-command-input">エディタコマンド</label>
            <input
              id="editor-command-input"
              type="text"
              value={editorCommandDraft}
              onChange={(e) => setEditorCommandDraft(e.target.value)}
              autoFocus
            />
            <button type="submit">保存</button>
          </form>
        )}
      </div>
      <div className="toolbar__search">
        <input
          ref={searchInputRef}
          type="text"
          value={search.query}
          onChange={(e) => activeTabPath && setTabSearchQuery(activeTabPath, e.target.value)}
          onKeyDown={(e) => {
            if (!activeTabPath) return;
            if (e.key === "Enter") {
              e.preventDefault();
              if (e.shiftKey) searchGoToPrev(activeTabPath);
              else searchGoToNext(activeTabPath);
            } else if (e.key === "Escape") {
              clearTabSearch(activeTabPath);
            }
          }}
          placeholder="本文を検索（Ctrl+F）"
          disabled={activeTabPath === null}
          className="toolbar__search-input"
        />
        <span className="toolbar__search-count">
          {search.matchCount > 0
            ? `${search.currentIndex + 1} / ${search.matchCount}`
            : search.query
              ? "0 / 0"
              : ""}
        </span>
        <button
          type="button"
          className="toolbar__icon-btn"
          title="前へ"
          onClick={() => activeTabPath && searchGoToPrev(activeTabPath)}
          disabled={search.matchCount === 0}
          aria-label="前へ"
        >
          ▲
        </button>
        <button
          type="button"
          className="toolbar__icon-btn"
          title="次へ"
          onClick={() => activeTabPath && searchGoToNext(activeTabPath)}
          disabled={search.matchCount === 0}
          aria-label="次へ"
        >
          ▼
        </button>
      </div>
    </div>
  );
}
