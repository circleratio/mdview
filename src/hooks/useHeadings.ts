import { useEffect, useState, type RefObject } from "react";
import { buildHeadingTree, type HeadingItem, type HeadingNode } from "../lib/headings";

/**
 * Walks the rendered DOM (after react-markdown + rehype-slug have run) to build the TOC tree
 * and track which heading is currently in view. Reading the DOM directly avoids re-parsing the
 * markdown source just for headings, and guarantees the TOC ids match rehype-slug's ids exactly.
 */
export function useHeadings(containerRef: RefObject<HTMLElement | null>, content: string | null) {
  const [tree, setTree] = useState<HeadingNode[]>([]);
  const [flatIds, setFlatIds] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || content === null) {
      setTree([]);
      setFlatIds([]);
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
    setFlatIds(items.map((item) => item.id));
  }, [containerRef, content]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || flatIds.length === 0) {
      setActiveId(null);
      return;
    }

    const elements = flatIds
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);

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

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [containerRef, flatIds]);

  return { tree, activeId };
}
