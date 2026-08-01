import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export interface DocumentState {
  path: string | null;
  dir: string | null;
  content: string | null;
  loading: boolean;
  error: string | null;
}

interface DocumentContextValue extends DocumentState {
  setDocument: (path: string, dir: string, content: string) => void;
  setError: (message: string) => void;
  setLoading: (loading: boolean) => void;
}

const DocumentContext = createContext<DocumentContextValue | null>(null);

const initialState: DocumentState = {
  path: null,
  dir: null,
  content: null,
  loading: false,
  error: null,
};

export function DocumentProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DocumentState>(initialState);

  const setDocument = useCallback((path: string, dir: string, content: string) => {
    setState({ path, dir, content, loading: false, error: null });
  }, []);

  const setError = useCallback((message: string) => {
    setState((s) => ({ ...s, loading: false, error: message }));
  }, []);

  const setLoading = useCallback((loading: boolean) => {
    setState((s) => ({ ...s, loading }));
  }, []);

  const value = useMemo<DocumentContextValue>(
    () => ({ ...state, setDocument, setError, setLoading }),
    [state, setDocument, setError, setLoading],
  );

  return <DocumentContext.Provider value={value}>{children}</DocumentContext.Provider>;
}

export function useDocument(): DocumentContextValue {
  const ctx = useContext(DocumentContext);
  if (!ctx) {
    throw new Error("useDocument must be used within a DocumentProvider");
  }
  return ctx;
}
