import { useState } from "react";
import { useFileOpener } from "../hooks/useFileOpener";
import { useRecentFiles } from "../hooks/useRecentFiles";
import { useExternalEditor } from "../hooks/useExternalEditor";
import { useDocument } from "../state/DocumentContext";
import { basenameForDisplay } from "../lib/displayPath";

export function Toolbar() {
  const { openViaDialog, loadFile } = useFileOpener();
  const { recentFiles } = useRecentFiles();
  const { editorCommand, setEditorCommand, openInEditor } = useExternalEditor();
  const { path } = useDocument();
  const [isRecentOpen, setIsRecentOpen] = useState(false);
  const [isEditorSettingsOpen, setIsEditorSettingsOpen] = useState(false);
  const [editorCommandDraft, setEditorCommandDraft] = useState(editorCommand);

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
      <button
        type="button"
        disabled={path === null}
        title={`${editorCommand} で開く（Ctrl+E）`}
        onClick={() => void openInEditor()}
      >
        エディタで開く
      </button>
      <div className="toolbar__editor-settings">
        <button
          type="button"
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
      <span className="toolbar__current-path" title={path ?? undefined}>
        {path ? basenameForDisplay(path) : "ファイルが開かれていません"}
      </span>
    </div>
  );
}
