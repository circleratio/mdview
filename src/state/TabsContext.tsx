import { createContext, useCallback, useContext, useMemo, useReducer, useState, type ReactNode } from "react";

export interface TabSearchState {
  query: string;
  matchCount: number;
  currentIndex: number;
}

export interface TabState {
  path: string;
  dir: string | null;
  content: string | null;
  loading: boolean;
  error: string | null;
  search: TabSearchState;
}

interface TabsState {
  tabs: TabState[];
  activeTabPath: string | null;
}

type TabsAction =
  | { type: "add_pending"; path: string }
  | { type: "set_document"; path: string; dir: string; content: string }
  | { type: "set_error"; path: string; message: string }
  | { type: "set_loading"; path: string; loading: boolean }
  | { type: "remove"; path: string }
  | { type: "set_active"; path: string }
  | { type: "set_search_query"; path: string; query: string }
  | { type: "set_search_matches"; path: string; count: number }
  | { type: "search_next"; path: string }
  | { type: "search_prev"; path: string }
  | { type: "clear_search"; path: string };

const initialSearch: TabSearchState = { query: "", matchCount: 0, currentIndex: 0 };

function createPendingTab(path: string): TabState {
  return { path, dir: null, content: null, loading: true, error: null, search: { ...initialSearch } };
}

function updateTab(tabs: TabState[], path: string, updater: (tab: TabState) => TabState): TabState[] {
  return tabs.map((tab) => (tab.path === path ? updater(tab) : tab));
}

function reducer(state: TabsState, action: TabsAction): TabsState {
  switch (action.type) {
    case "add_pending": {
      if (state.tabs.some((tab) => tab.path === action.path)) {
        return { ...state, activeTabPath: action.path };
      }
      return { tabs: [...state.tabs, createPendingTab(action.path)], activeTabPath: action.path };
    }
    case "set_document":
      return {
        ...state,
        tabs: updateTab(state.tabs, action.path, (tab) => ({
          ...tab,
          dir: action.dir,
          content: action.content,
          loading: false,
          error: null,
        })),
      };
    case "set_error":
      return {
        ...state,
        tabs: updateTab(state.tabs, action.path, (tab) => ({ ...tab, loading: false, error: action.message })),
      };
    case "set_loading":
      return {
        ...state,
        tabs: updateTab(state.tabs, action.path, (tab) => ({ ...tab, loading: action.loading })),
      };
    case "remove": {
      const index = state.tabs.findIndex((tab) => tab.path === action.path);
      if (index === -1) return state;
      const tabs = [...state.tabs.slice(0, index), ...state.tabs.slice(index + 1)];
      let activeTabPath = state.activeTabPath;
      if (activeTabPath === action.path) {
        activeTabPath = tabs.length === 0 ? null : tabs[Math.max(0, index - 1)].path;
      }
      return { tabs, activeTabPath };
    }
    case "set_active":
      return { ...state, activeTabPath: action.path };
    case "set_search_query":
      return {
        ...state,
        tabs: updateTab(state.tabs, action.path, (tab) => ({
          ...tab,
          search: { ...tab.search, query: action.query },
        })),
      };
    case "set_search_matches":
      return {
        ...state,
        tabs: updateTab(state.tabs, action.path, (tab) => ({
          ...tab,
          search: { ...tab.search, matchCount: action.count, currentIndex: 0 },
        })),
      };
    case "search_next":
      return {
        ...state,
        tabs: updateTab(state.tabs, action.path, (tab) => {
          if (tab.search.matchCount === 0) return tab;
          const currentIndex = (tab.search.currentIndex + 1) % tab.search.matchCount;
          return { ...tab, search: { ...tab.search, currentIndex } };
        }),
      };
    case "search_prev":
      return {
        ...state,
        tabs: updateTab(state.tabs, action.path, (tab) => {
          if (tab.search.matchCount === 0) return tab;
          const currentIndex = (tab.search.currentIndex - 1 + tab.search.matchCount) % tab.search.matchCount;
          return { ...tab, search: { ...tab.search, currentIndex } };
        }),
      };
    case "clear_search":
      return {
        ...state,
        tabs: updateTab(state.tabs, action.path, (tab) => ({ ...tab, search: { ...initialSearch } })),
      };
    default:
      return state;
  }
}

interface TabsContextValue {
  tabs: TabState[];
  activeTabPath: string | null;
  activeTab: TabState | null;
  appError: string | null;
  addPendingTab: (path: string) => void;
  setTabDocument: (path: string, dir: string, content: string) => void;
  setTabError: (path: string, message: string) => void;
  setTabLoading: (path: string, loading: boolean) => void;
  removeTab: (path: string) => void;
  setActiveTab: (path: string) => void;
  setAppError: (message: string | null) => void;
  setTabSearchQuery: (path: string, query: string) => void;
  setTabSearchMatches: (path: string, count: number) => void;
  searchGoToNext: (path: string) => void;
  searchGoToPrev: (path: string) => void;
  clearTabSearch: (path: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

const initialState: TabsState = { tabs: [], activeTabPath: null };

export function TabsProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [appError, setAppError] = useState<string | null>(null);

  const addPendingTab = useCallback((path: string) => dispatch({ type: "add_pending", path }), []);
  const setTabDocument = useCallback(
    (path: string, dir: string, content: string) => dispatch({ type: "set_document", path, dir, content }),
    [],
  );
  const setTabError = useCallback((path: string, message: string) => dispatch({ type: "set_error", path, message }), []);
  const setTabLoading = useCallback((path: string, loading: boolean) => dispatch({ type: "set_loading", path, loading }), []);
  const removeTab = useCallback((path: string) => dispatch({ type: "remove", path }), []);
  const setActiveTab = useCallback((path: string) => dispatch({ type: "set_active", path }), []);
  const setTabSearchQuery = useCallback((path: string, query: string) => dispatch({ type: "set_search_query", path, query }), []);
  const setTabSearchMatches = useCallback((path: string, count: number) => dispatch({ type: "set_search_matches", path, count }), []);
  const searchGoToNext = useCallback((path: string) => dispatch({ type: "search_next", path }), []);
  const searchGoToPrev = useCallback((path: string) => dispatch({ type: "search_prev", path }), []);
  const clearTabSearch = useCallback((path: string) => dispatch({ type: "clear_search", path }), []);

  const activeTab = useMemo(
    () => state.tabs.find((tab) => tab.path === state.activeTabPath) ?? null,
    [state.tabs, state.activeTabPath],
  );

  const value = useMemo<TabsContextValue>(
    () => ({
      tabs: state.tabs,
      activeTabPath: state.activeTabPath,
      activeTab,
      appError,
      addPendingTab,
      setTabDocument,
      setTabError,
      setTabLoading,
      removeTab,
      setActiveTab,
      setAppError,
      setTabSearchQuery,
      setTabSearchMatches,
      searchGoToNext,
      searchGoToPrev,
      clearTabSearch,
    }),
    [
      state.tabs,
      state.activeTabPath,
      activeTab,
      appError,
      addPendingTab,
      setTabDocument,
      setTabError,
      setTabLoading,
      removeTab,
      setActiveTab,
      setTabSearchQuery,
      setTabSearchMatches,
      searchGoToNext,
      searchGoToPrev,
      clearTabSearch,
    ],
  );

  return <TabsContext.Provider value={value}>{children}</TabsContext.Provider>;
}

export function useTabs(): TabsContextValue {
  const ctx = useContext(TabsContext);
  if (!ctx) {
    throw new Error("useTabs must be used within a TabsProvider");
  }
  return ctx;
}
