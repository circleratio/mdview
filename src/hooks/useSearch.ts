import { useEffect, type RefObject } from "react";
import Mark from "mark.js";
import { useTabs, type TabState } from "../state/TabsContext";

const MATCH_SELECTOR = "mark[data-markjs]";
const CURRENT_MATCH_CLASS = "search-match--current";

/** Ctrl+F focuses (and selects) the toolbar's always-visible search input. */
export function useSearchShortcut(inputRef: RefObject<HTMLInputElement | null>) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        event.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [inputRef]);
}

/**
 * Keeps a tab's mark.js highlights in sync with its `search` state (owned by TabsContext,
 * written to by the Toolbar). The Toolbar and this tab's content DOM are siblings that can't
 * share refs directly, so this hook reacts to state changes instead of being called into
 * imperatively: query changes re-run mark.js and report the match count back; currentIndex
 * changes move the `.search-match--current` highlight and scroll it into view.
 */
export function useTabSearchSync(tab: TabState, containerRef: RefObject<HTMLElement | null>) {
  const { setTabSearchMatches } = useTabs();
  const { path, search } = tab;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (search.query.trim() === "") {
      new Mark(container).unmark();
      return;
    }

    const mark = new Mark(container);
    mark.unmark({
      done: () => {
        mark.mark(search.query, {
          separateWordSearch: false,
          done: () => {
            const count = container.querySelectorAll(MATCH_SELECTOR).length;
            setTabSearchMatches(path, count);
          },
        });
      },
    });
  }, [containerRef, path, search.query, setTabSearchMatches]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const marks = container.querySelectorAll<HTMLElement>(MATCH_SELECTOR);
    marks.forEach((m) => m.classList.remove(CURRENT_MATCH_CLASS));
    const target = marks[search.currentIndex];
    if (target) {
      target.classList.add(CURRENT_MATCH_CLASS);
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [containerRef, search.currentIndex, search.matchCount]);
}
