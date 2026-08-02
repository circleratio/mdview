import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";
import { exists } from "@tauri-apps/plugin-fs";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useFileOpener } from "../hooks/useFileOpener";
import { useTabDocument } from "../state/TabDocumentContext";
import { isMarkdownPath } from "../lib/markdownFiles";
import { hasUriScheme, isAbsolutePath, resolveRelativePath } from "../lib/paths";

type MarkdownLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { children?: ReactNode };

export function MarkdownLink({ href, children, ...rest }: MarkdownLinkProps) {
  const { openTab } = useFileOpener();
  const { dir } = useTabDocument();

  if (!href) {
    return <a {...rest}>{children}</a>;
  }

  const handleClick = async (event: MouseEvent<HTMLAnchorElement>) => {
    if (href.startsWith("#")) {
      // Every open tab stays mounted (hidden) in the DOM at once, so the browser's default
      // same-document anchor scrolling (a document-wide id lookup) could jump to a same-id
      // heading in a different, hidden tab. Scope the lookup to this link's own tab instead.
      event.preventDefault();
      const id = href.slice(1);
      const container = (event.currentTarget as HTMLElement).closest<HTMLElement>(".markdown-view");
      const target = container
        ? Array.from(container.querySelectorAll<HTMLElement>("[id]")).find((el) => el.id === id)
        : null;
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    event.preventDefault();

    if (hasUriScheme(href)) {
      await openUrl(href);
      return;
    }

    const target = isAbsolutePath(href) || !dir ? href : resolveRelativePath(dir, href);
    if (isMarkdownPath(target) && (await exists(target))) {
      await openTab(target);
    }
  };

  return (
    <a href={href} onClick={(e) => void handleClick(e)} {...rest}>
      {children}
    </a>
  );
}
