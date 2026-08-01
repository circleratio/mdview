import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import Mark from "mark.js";

const MATCH_SELECTOR = "mark[data-markjs]";
const CURRENT_MATCH_CLASS = "search-match--current";

export function useSearch(containerRef: RefObject<HTMLElement | null>) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [matchCount, setMatchCount] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const markInstanceRef = useRef<InstanceType<typeof Mark> | null>(null);

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
    if (!markInstanceRef.current) {
      markInstanceRef.current = new Mark(container);
    }
    markInstanceRef.current.unmark();
    setMatchCount(0);
    setCurrentIndex(0);
  }, [containerRef]);

  useEffect(() => {
    if (!isOpen || query.trim() === "") {
      clearHighlights();
      return;
    }
    const container = containerRef.current;
    if (!container) return;
    if (!markInstanceRef.current) {
      markInstanceRef.current = new Mark(container);
    }
    const mark = markInstanceRef.current;

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
  }, [query, isOpen, containerRef]);

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

  const close = useCallback(() => {
    setIsOpen(false);
    setQuery("");
    clearHighlights();
  }, [clearHighlights]);

  const open = useCallback(() => setIsOpen(true), []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        event.preventDefault();
        open();
      } else if (event.key === "Escape" && isOpen) {
        close();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, close, isOpen]);

  return { isOpen, query, setQuery, matchCount, currentIndex, open, close, goToNext, goToPrev };
}
