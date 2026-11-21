import { isValidElement, type ReactNode } from "react";
import type { Components } from "react-markdown";
import type { PluggableList } from "unified";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeSlug from "rehype-slug";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import { resolveAssetSrc } from "./assetSrc";
import { MermaidBlock } from "../components/MermaidBlock";
import { MarkdownLink } from "../components/MarkdownLink";

export const markdownRemarkPlugins = [remarkGfm, remarkMath];
export const markdownRehypePlugins: PluggableList = [
  rehypeSlug,
  rehypeHighlight,
  [rehypeKatex, { throwOnError: false }],
];

function extractMermaidCode(children: ReactNode): string | null {
  const child = Array.isArray(children) ? children[0] : children;
  if (!isValidElement(child)) return null;
  const codeProps = child.props as { className?: string; children?: ReactNode };
  const match = /language-(\w+)/.exec(codeProps.className ?? "");
  if (!match || match[1] !== "mermaid") return null;
  return String(codeProps.children ?? "").replace(/\n$/, "");
}

export function getMarkdownComponents(dir: string | null): Components {
  return {
    img({ src, alt, ...rest }) {
      if (!src) return null;
      return <img src={resolveAssetSrc(src, dir)} alt={alt ?? ""} {...rest} />;
    },
    a: MarkdownLink,
    pre({ children, ...rest }) {
      const mermaidCode = extractMermaidCode(children);
      if (mermaidCode !== null) {
        return <MermaidBlock code={mermaidCode} />;
      }
      return <pre {...rest}>{children}</pre>;
    },
  };
}
