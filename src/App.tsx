import { useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { TabsProvider, useTabs } from "./state/TabsContext";
import { useFileOpener } from "./hooks/useFileOpener";
import { useFileWatcher } from "./hooks/useFileWatcher";
import { Toolbar } from "./components/Toolbar";
import { TabBar } from "./components/TabBar";
import { TabPane } from "./components/TabPane";
import { DropZoneOverlay } from "./components/DropZoneOverlay";
import "katex/dist/katex.min.css";
import "./App.css";

function AppShell() {
  const { tabs, activeTabPath, appError, setAppError } = useTabs();
  const { openTab } = useFileOpener();
  useFileWatcher();

  useEffect(() => {
    invoke<string | null>("initial_file_path").then((initialPath) => {
      if (initialPath) {
        void openTab(initialPath);
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
      <Toolbar />
      <TabBar />
      {appError && (
        <div className="app__error app__error--banner" onClick={() => setAppError(null)} title="クリックで閉じる">
          {appError}
        </div>
      )}
      <DropZoneOverlay>
        {tabs.length === 0 ? (
          <div className="app__empty">
            ファイルを開いてください（「開く」ボタン、ドラッグ&ドロップ、または最近使ったファイルから選択）
          </div>
        ) : (
          tabs.map((tab) => <TabPane key={tab.path} tab={tab} isActive={tab.path === activeTabPath} />)
        )}
      </DropZoneOverlay>
    </div>
  );
}

function App() {
  return (
    <TabsProvider>
      <AppShell />
    </TabsProvider>
  );
}

export default App;
