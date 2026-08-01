import type { RefObject } from "react";
import ReactMarkdown from "react-markdown";
import { getMarkdownComponents, markdownRehypePlugins, markdownRemarkPlugins } from "../lib/markdown";

interface MarkdownViewProps {
  content: string;
  dir: string | null;
  containerRef: RefObject<HTMLDivElement | null>;
}

export function MarkdownView({ content, dir, containerRef }: MarkdownViewProps) {
  return (
    <div ref={containerRef} className="markdown-view">
      <article className="markdown-body">
        <ReactMarkdown
          remarkPlugins={markdownRemarkPlugins}
          rehypePlugins={markdownRehypePlugins}
          components={getMarkdownComponents(dir)}
        >
          {content}
        </ReactMarkdown>
      </article>
    </div>
  );
}
