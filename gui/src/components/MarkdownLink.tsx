import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";
import { exists } from "@tauri-apps/plugin-fs";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useFileOpener } from "../hooks/useFileOpener";
import { useTabDocument } from "../state/TabDocumentContext";
import { resolveLinkTarget, scrollToIdWithin } from "../lib/links";

type MarkdownLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { children?: ReactNode };

export function MarkdownLink({ href, children, ...rest }: MarkdownLinkProps) {
  const { openTab } = useFileOpener();
  const { dir } = useTabDocument();

  if (!href) {
    return <a {...rest}>{children}</a>;
  }

  const handleClick = async (event: MouseEvent<HTMLAnchorElement>) => {
    // Never let the webview navigate on its own: it would leave the app's page.
    event.preventDefault();
    const target = resolveLinkTarget(href, dir);

    switch (target.kind) {
      case "anchor": {
        const container = (event.currentTarget as HTMLElement).closest<HTMLElement>(".markdown-view");
        if (container) scrollToIdWithin(container, target.anchor, "smooth");
        return;
      }
      case "external":
        await openUrl(target.url);
        return;
      case "file":
        if (await exists(target.path)) {
          await openTab(target.path, { anchor: target.anchor });
        }
        return;
      case "unsupported":
        return;
    }
  };

  return (
    <a href={href} onClick={(e) => void handleClick(e)} {...rest}>
      {children}
    </a>
  );
}
