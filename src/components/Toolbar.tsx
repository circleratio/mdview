import { useState } from "react";
import { useFileOpener } from "../hooks/useFileOpener";
import { useRecentFiles } from "../hooks/useRecentFiles";
import { useExternalEditor } from "../hooks/useExternalEditor";
import type { useSearch } from "../hooks/useSearch";
import { useDocument } from "../state/DocumentContext";
import { basenameForDisplay } from "../lib/displayPath";
import { FolderIcon, HistoryIcon, PencilIcon } from "./icons";

interface ToolbarProps {
  search: ReturnType<typeof useSearch>;
}

export function Toolbar({ search }: ToolbarProps) {
  const { openViaDialog, loadFile } = useFileOpener();
  const { recentFiles } = useRecentFiles();
  const { editorCommand, setEditorCommand, openInEditor } = useExternalEditor();
  const { path } = useDocument();
  const [isRecentOpen, setIsRecentOpen] = useState(false);
  const [isEditorSettingsOpen, setIsEditorSettingsOpen] = useState(false);
  const [editorCommandDraft, setEditorCommandDraft] = useState(editorCommand);

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
      <button
        type="button"
        className="toolbar__icon-btn"
        disabled={path === null}
        title={`${editorCommand} で開く（Ctrl+E）`}
        aria-label="エディタで開く"
        onClick={() => void openInEditor()}
      >
        <PencilIcon />
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
          ref={search.inputRef}
          type="text"
          value={search.query}
          onChange={(e) => search.setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (e.shiftKey) search.goToPrev();
              else search.goToNext();
            } else if (e.key === "Escape") {
              search.clear();
            }
          }}
          placeholder="本文を検索（Ctrl+F）"
          disabled={path === null}
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
          onClick={search.goToPrev}
          disabled={search.matchCount === 0}
          aria-label="前へ"
        >
          ▲
        </button>
        <button
          type="button"
          className="toolbar__icon-btn"
          title="次へ"
          onClick={search.goToNext}
          disabled={search.matchCount === 0}
          aria-label="次へ"
        >
          ▼
        </button>
      </div>
      <span className="toolbar__current-path" title={path ?? undefined}>
        {path ? basenameForDisplay(path) : "ファイルが開かれていません"}
      </span>
    </div>
  );
}
