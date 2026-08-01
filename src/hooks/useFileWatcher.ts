import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { useDocument } from "../state/DocumentContext";
import { useFileOpener } from "./useFileOpener";

/** Reloads the currently open file whenever the Rust-side watcher reports a change to it. */
export function useFileWatcher() {
  const { path } = useDocument();
  const { loadFile } = useFileOpener();

  useEffect(() => {
    if (!path) return;

    const unlistenPromise = listen<string>("file-changed", (event) => {
      if (event.payload === path) {
        void loadFile(path);
      }
    });

    return () => {
      void unlistenPromise.then((unlisten) => unlisten());
    };
  }, [path, loadFile]);
}
