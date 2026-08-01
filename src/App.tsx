import { useCallback, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Group, Panel, Separator } from "react-resizable-panels";
import { DocumentProvider, useDocument } from "./state/DocumentContext";
import { useFileOpener } from "./hooks/useFileOpener";
import { useFileWatcher } from "./hooks/useFileWatcher";
import { useHeadings } from "./hooks/useHeadings";
import { useSearch } from "./hooks/useSearch";
import { Toolbar } from "./components/Toolbar";
import { DropZoneOverlay } from "./components/DropZoneOverlay";
import { Sidebar } from "./components/Sidebar";
import { MarkdownView } from "./components/MarkdownView";
import "katex/dist/katex.min.css";
import "./App.css";

function AppShell() {
  const { content, dir, error, loading } = useDocument();
  const { loadFile } = useFileOpener();
  useFileWatcher();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const { tree, activeId } = useHeadings(containerRef, content);
  const search = useSearch(containerRef);

  const handleSelectHeading = useCallback((id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  useEffect(() => {
    invoke<string | null>("initial_file_path").then((initialPath) => {
      if (initialPath) {
        void loadFile(initialPath);
      }
    });
  }, []);

  useEffect(() => {
    // See `finish_startup` in commands.rs: WebView2 sometimes fails to paint the
    // right-aligned toolbar item on its first layout. A short delay lets the initial
    // (buggy) paint actually happen before the resize nudge forces a repaint.
    const timer = setTimeout(() => {
      void invoke("finish_startup");
    }, 400);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="app">
      <Toolbar search={search} />
      <DropZoneOverlay>
        {error && <div className="app__error">{error}</div>}
        {loading && <div className="app__loading">読み込み中...</div>}
        {!loading && !error && content === null && (
          <div className="app__empty">
            ファイルを開いてください（「開く」ボタン、ドラッグ&ドロップ、または最近使ったファイルから選択）
          </div>
        )}
        {!loading && content !== null && (
          <Group orientation="horizontal" className="panels">
            <Panel defaultSize="22" minSize="12" maxSize="50" className="panel panel--sidebar">
              <Sidebar nodes={tree} activeId={activeId} onSelect={handleSelectHeading} />
            </Panel>
            <Separator className="resize-handle" />
            <Panel minSize="30" className="panel panel--content">
              <MarkdownView content={content} dir={dir} containerRef={containerRef} />
            </Panel>
          </Group>
        )}
      </DropZoneOverlay>
    </div>
  );
}

function App() {
  return (
    <DocumentProvider>
      <AppShell />
    </DocumentProvider>
  );
}

export default App;
