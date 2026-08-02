import { useCallback, useRef } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { TabDocumentProvider } from "../state/TabDocumentContext";
import { useHeadings } from "../hooks/useHeadings";
import { useTabSearchSync } from "../hooks/useSearch";
import type { TabState } from "../state/TabsContext";
import { Sidebar } from "./Sidebar";
import { MarkdownView } from "./MarkdownView";

interface TabPaneProps {
  tab: TabState;
  isActive: boolean;
}

/**
 * One per open tab, mounted for as long as the tab stays open (even while inactive) so its
 * search highlights, scroll position and heading tracking survive switching away and back,
 * and its content keeps auto-reloading in the background. Inactive panes are hidden with
 * `display:none` rather than unmounted (see spec.md 4.4).
 */
export function TabPane({ tab, isActive }: TabPaneProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { tree, activeId } = useHeadings(containerRef, tab.content);
  useTabSearchSync(tab, containerRef);

  const handleSelectHeading = useCallback((id: string) => {
    // Scoped to this tab's own container, not document.getElementById: other open tabs stay
    // mounted (hidden) with their own rehype-slug ids, which can collide with this tab's.
    const container = containerRef.current;
    if (!container) return;
    const target = Array.from(container.querySelectorAll<HTMLElement>("h1, h2, h3, h4, h5, h6")).find(
      (el) => el.id === id,
    );
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <div className="tab-pane" style={{ display: isActive ? "flex" : "none" }}>
      <TabDocumentProvider value={{ path: tab.path, dir: tab.dir }}>
        {tab.error && <div className="app__error">{tab.error}</div>}
        {tab.loading && <div className="app__loading">読み込み中...</div>}
        {!tab.loading && tab.content !== null && (
          <Group orientation="horizontal" className="panels">
            <Panel defaultSize="22" minSize="12" maxSize="50" className="panel panel--sidebar">
              <Sidebar nodes={tree} activeId={activeId} onSelect={handleSelectHeading} />
            </Panel>
            <Separator className="resize-handle" />
            <Panel minSize="30" className="panel panel--content">
              <MarkdownView content={tab.content} dir={tab.dir} containerRef={containerRef} />
            </Panel>
          </Group>
        )}
      </TabDocumentProvider>
    </div>
  );
}
