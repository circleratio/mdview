import { createContext, useContext, type ReactNode } from "react";

export interface TabDocumentValue {
  path: string;
  dir: string | null;
}

const TabDocumentContext = createContext<TabDocumentValue | null>(null);

export function TabDocumentProvider({ value, children }: { value: TabDocumentValue; children: ReactNode }) {
  return <TabDocumentContext.Provider value={value}>{children}</TabDocumentContext.Provider>;
}

export function useTabDocument(): TabDocumentValue {
  const ctx = useContext(TabDocumentContext);
  if (!ctx) {
    throw new Error("useTabDocument must be used within a TabDocumentProvider");
  }
  return ctx;
}
