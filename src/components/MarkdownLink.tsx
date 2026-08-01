import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";
import { exists } from "@tauri-apps/plugin-fs";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useFileOpener } from "../hooks/useFileOpener";
import { useDocument } from "../state/DocumentContext";
import { isMarkdownPath } from "../lib/markdownFiles";
import { hasUriScheme, isAbsolutePath, resolveRelativePath } from "../lib/paths";

type MarkdownLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { children?: ReactNode };

export function MarkdownLink({ href, children, ...rest }: MarkdownLinkProps) {
  const { loadFile } = useFileOpener();
  const { dir } = useDocument();

  if (!href) {
    return <a {...rest}>{children}</a>;
  }

  const handleClick = async (event: MouseEvent<HTMLAnchorElement>) => {
    if (href.startsWith("#")) {
      return; // let the browser handle same-document anchor scrolling
    }

    event.preventDefault();

    if (hasUriScheme(href)) {
      await openUrl(href);
      return;
    }

    const target = isAbsolutePath(href) || !dir ? href : resolveRelativePath(dir, href);
    if (isMarkdownPath(target) && (await exists(target))) {
      await loadFile(target);
    }
  };

  return (
    <a href={href} onClick={(e) => void handleClick(e)} {...rest}>
      {children}
    </a>
  );
}
