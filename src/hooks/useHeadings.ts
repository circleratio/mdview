import { useEffect, useState, type RefObject } from "react";
import { buildHeadingTree, type HeadingItem, type HeadingNode } from "../lib/headings";

/**
 * Walks the rendered DOM (after react-markdown + rehype-slug have run) to build the TOC tree
 * and track which heading is currently in view. Reading the DOM directly avoids re-parsing the
 * markdown source just for headings, and guarantees the TOC ids match rehype-slug's ids exactly.
 *
 * Every open tab stays mounted in the DOM at once (see TabPane), and rehype-slug only guarantees
 * unique ids *within* one document — two open files with a same-named heading (or this project's
 * own numbered headings, e.g. "3.1 ...") can end up with identical ids. So heading elements are
 * tracked directly (captured from this hook's own `containerRef`) rather than re-resolved via
 * `document.getElementById`, which would happily return a same-id heading from a different,
 * hidden tab.
 */
export function useHeadings(containerRef: RefObject<HTMLElement | null>, content: string | null) {
  const [tree, setTree] = useState<HeadingNode[]>([]);
  const [headingElements, setHeadingElements] = useState<HTMLElement[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || content === null) {
      setTree([]);
      setHeadingElements([]);
      return;
    }
    const elements = Array.from(
      containerRef.current.querySelectorAll<HTMLElement>("h1, h2, h3, h4, h5, h6"),
    );
    const items: HeadingItem[] = elements.map((el) => ({
      id: el.id,
      text: el.textContent ?? "",
      level: Number(el.tagName[1]),
    }));
    setTree(buildHeadingTree(items));
    setHeadingElements(elements);
  }, [containerRef, content]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || headingElements.length === 0) {
      setActiveId(null);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) {
          setActiveId(visible[0].target.id);
        }
      },
      { root: container, rootMargin: "0px 0px -70% 0px", threshold: 0 },
    );

    headingElements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [containerRef, headingElements]);

  return { tree, activeId };
}
