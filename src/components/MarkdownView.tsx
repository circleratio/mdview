import { useMemo, type RefObject } from "react";
import ReactMarkdown from "react-markdown";
import { getMarkdownComponents, markdownRehypePlugins, markdownRemarkPlugins } from "../lib/markdown";

interface MarkdownViewProps {
  content: string;
  dir: string | null;
  containerRef: RefObject<HTMLDivElement | null>;
}

export function MarkdownView({ content, dir, containerRef }: MarkdownViewProps) {
  // getMarkdownComponents returns fresh `img`/`a`/`pre` function references each call. Without
  // memoizing, every re-render (e.g. from unrelated search state changes) would give react-markdown
  // a "new" component type for those tags, causing React to remount that DOM instead of just
  // updating it — destroying mark.js's in-place highlight markup inside code blocks in the process.
  const components = useMemo(() => getMarkdownComponents(dir), [dir]);

  return (
    <div ref={containerRef} className="markdown-view">
      <article className="markdown-body">
        <ReactMarkdown
          remarkPlugins={markdownRemarkPlugins}
          rehypePlugins={markdownRehypePlugins}
          components={components}
        >
          {content}
        </ReactMarkdown>
      </article>
    </div>
  );
}
