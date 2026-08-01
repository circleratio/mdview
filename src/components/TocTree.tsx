import type { HeadingNode } from "../lib/headings";

interface TocTreeProps {
  nodes: HeadingNode[];
  activeId: string | null;
  onSelect: (id: string) => void;
}

export function TocTree({ nodes, activeId, onSelect }: TocTreeProps) {
  if (nodes.length === 0) {
    return null;
  }

  return (
    <ul className="toc-tree">
      {nodes.map((node) => (
        <li key={node.id}>
          <button
            type="button"
            className={
              "toc-tree__item" + (node.id === activeId ? " toc-tree__item--active" : "")
            }
            onClick={() => onSelect(node.id)}
            title={node.text}
          >
            {node.text}
          </button>
          {node.children.length > 0 && (
            <TocTree nodes={node.children} activeId={activeId} onSelect={onSelect} />
          )}
        </li>
      ))}
    </ul>
  );
}
