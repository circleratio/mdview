import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import Mark from "mark.js";

const MATCH_SELECTOR = "mark[data-markjs]";
const CURRENT_MATCH_CLASS = "search-match--current";

/** Drives the always-visible toolbar search field: live highlight-as-you-type plus Ctrl+F to focus it. */
export function useSearch(containerRef: RefObject<HTMLElement | null>) {
  const [query, setQuery] = useState("");
  const [matchCount, setMatchCount] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const focusMatch = useCallback(
    (index: number) => {
      const container = containerRef.current;
      if (!container) return;
      const marks = container.querySelectorAll<HTMLElement>(MATCH_SELECTOR);
      marks.forEach((m) => m.classList.remove(CURRENT_MATCH_CLASS));
      const target = marks[index];
      if (target) {
        target.classList.add(CURRENT_MATCH_CLASS);
        target.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    },
    [containerRef],
  );

  const clearHighlights = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    new Mark(container).unmark();
    setMatchCount(0);
    setCurrentIndex(0);
  }, [containerRef]);

  useEffect(() => {
    if (query.trim() === "") {
      clearHighlights();
      return;
    }
    const container = containerRef.current;
    if (!container) return;
    const mark = new Mark(container);

    mark.unmark({
      done: () => {
        mark.mark(query, {
          separateWordSearch: false,
          done: () => {
            const count = container.querySelectorAll(MATCH_SELECTOR).length;
            setMatchCount(count);
            setCurrentIndex(0);
            if (count > 0) focusMatch(0);
          },
        });
      },
    });
  }, [query, containerRef, clearHighlights, focusMatch]);

  const goToNext = useCallback(() => {
    if (matchCount === 0) return;
    setCurrentIndex((current) => {
      const next = (current + 1) % matchCount;
      focusMatch(next);
      return next;
    });
  }, [matchCount, focusMatch]);

  const goToPrev = useCallback(() => {
    if (matchCount === 0) return;
    setCurrentIndex((current) => {
      const prev = (current - 1 + matchCount) % matchCount;
      focusMatch(prev);
      return prev;
    });
  }, [matchCount, focusMatch]);

  const clear = useCallback(() => {
    setQuery("");
    clearHighlights();
  }, [clearHighlights]);

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
  }, []);

  return { query, setQuery, matchCount, currentIndex, goToNext, goToPrev, clear, inputRef };
}
