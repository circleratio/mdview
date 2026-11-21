import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";
import { exists } from "@tauri-apps/plugin-fs";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useFileOpener } from "../hooks/useFileOpener";
import { useTabDocument } from "../state/TabDocumentContext";
import { useTabs } from "../state/TabsContext";
import { decodeLinkPart, linkErrors, resolveLinkTarget, scrollToIdWithin } from "../lib/links";

type MarkdownLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { children?: ReactNode };

export function MarkdownLink({ href, children, ...rest }: MarkdownLinkProps) {
  const { openTab } = useFileOpener();
  const { dir } = useTabDocument();
  const { setAppError } = useTabs();

  if (!href) {
    return <a {...rest}>{children}</a>;
  }

  const handleClick = async (event: MouseEvent<HTMLAnchorElement>) => {
    // Never let the webview navigate on its own: it would leave the app's page.
    event.preventDefault();
    const target = resolveLinkTarget(href, dir);

    // Links that cannot be followed are reported in the error banner, like other failed actions.
    switch (target.kind) {
      case "anchor": {
        const container = (event.currentTarget as HTMLElement).closest<HTMLElement>(".markdown-view");
        if (container && !scrollToIdWithin(container, target.anchor, "smooth")) {
          setAppError(linkErrors.missingAnchor(target.anchor));
        }
        return;
      }
      case "external":
        try {
          await openUrl(target.url);
        } catch {
          setAppError(linkErrors.cannotOpenUrl(target.url));
        }
        return;
      case "file": {
        // exists() rejects for paths outside the fs scope; treat that as "not found" too.
        const found = await exists(target.path).catch(() => false);
        if (found) {
          await openTab(target.path, { anchor: target.anchor });
        } else {
          setAppError(linkErrors.missingFile(target.path));
        }
        return;
      }
      case "unsupported":
        // Show the href as written, not percent-encoded by normalizeUri.
        setAppError(linkErrors.unsupported(decodeLinkPart(href)));
        return;
    }
  };

  return (
    <a href={href} onClick={(e) => void handleClick(e)} {...rest}>
      {children}
    </a>
  );
}
