import { useMemo, type RefObject } from "react";
import ReactMarkdown from "react-markdown";
import { getMarkdownComponents, markdownRehypePlugins, markdownRemarkPlugins } from "../lib/markdown";
import type { ParsedDocument } from "../lib/frontMatter";
import { FrontMatterHeader } from "./FrontMatterHeader";

interface MarkdownViewProps {
  /** The parsed document; only its `body` (front matter stripped) goes to react-markdown. */
  parsed: ParsedDocument;
  dir: string | null;
  containerRef: RefObject<HTMLDivElement | null>;
}

export function MarkdownView({ parsed, dir, containerRef }: MarkdownViewProps) {
  // getMarkdownComponents returns fresh `img`/`a`/`pre` function references each call. Without
  // memoizing, every re-render (e.g. from unrelated search state changes) would give react-markdown
  // a "new" component type for those tags, causing React to remount that DOM instead of just
  // updating it — destroying mark.js's in-place highlight markup inside code blocks in the process.
  const components = useMemo(() => getMarkdownComponents(dir), [dir]);

  return (
    <div ref={containerRef} className="markdown-view">
      <article className="markdown-body">
        <FrontMatterHeader parsed={parsed} />
        <ReactMarkdown
          remarkPlugins={markdownRemarkPlugins}
          rehypePlugins={markdownRehypePlugins}
          components={components}
        >
          {parsed.body}
        </ReactMarkdown>
      </article>
    </div>
  );
}
