import { useEffect, useState, type ReactNode } from "react";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { useFileOpener } from "../hooks/useFileOpener";
import { isMarkdownPath } from "../lib/markdownFiles";

export function DropZoneOverlay({ children }: { children: ReactNode }) {
  const { openTab } = useFileOpener();
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let cancelled = false;

    getCurrentWebview()
      .onDragDropEvent((event) => {
        const payload = event.payload;
        if (payload.type === "enter" || payload.type === "over") {
          setIsDraggingOver(true);
        } else if (payload.type === "leave") {
          setIsDraggingOver(false);
        } else if (payload.type === "drop") {
          setIsDraggingOver(false);
          const target = payload.paths.find(isMarkdownPath);
          if (target) {
            void openTab(target);
          }
        }
      })
      .then((fn) => {
        if (cancelled) {
          fn();
        } else {
          unlisten = fn;
        }
      });

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [openTab]);

  return (
    <div className="drop-zone">
      {children}
      {isDraggingOver && (
        <div className="drop-zone__overlay">
          <p>Markdownファイルをドロップして開く</p>
        </div>
      )}
    </div>
  );
}
