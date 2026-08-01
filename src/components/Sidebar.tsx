import type { HeadingNode } from "../lib/headings";
import { TocTree } from "./TocTree";

interface SidebarProps {
  nodes: HeadingNode[];
  activeId: string | null;
  onSelect: (id: string) => void;
}

export function Sidebar({ nodes, activeId, onSelect }: SidebarProps) {
  return (
    <nav className="sidebar" aria-label="目次">
      {nodes.length === 0 ? (
        <p className="sidebar__empty">見出しがありません</p>
      ) : (
        <TocTree nodes={nodes} activeId={activeId} onSelect={onSelect} />
      )}
    </nav>
  );
}
