import { isMarkdownPath } from "./markdownFiles";
import { hasUriScheme, isAbsolutePath, resolveRelativePath } from "./paths";

/** What clicking a link in the rendered Markdown should do (doc/common.md 4). */
export type LinkTarget =
  | { kind: "anchor"; anchor: string }
  | { kind: "external"; url: string }
  | { kind: "file"; path: string; anchor: string | null }
  | { kind: "unsupported" };

/**
 * Decodes percent-encoding, keeping the raw text when it is malformed (e.g. a lone `%`).
 * Needed even for links written with plain non-ASCII text: mdast-util-to-hast percent-encodes
 * every link href (`normalizeUri`), so `[x](#概要)` reaches the DOM as `#%E6%A6%82%E8%A6%81`.
 */
export function decodeLinkPart(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/**
 * Converts a `file:` URL to a local path, or null when it cannot be parsed.
 * `file:///C:/a/b.md` -> `C:\a\b.md`, `file://server/share/b.md` -> `\\server\share\b.md`,
 * `file:///home/b.md` -> `/home/b.md`. Windows paths use backslashes like the rest of the app.
 */
export function fileUrlToPath(url: string): { path: string; anchor: string | null } | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  const pathname = decodeLinkPart(parsed.pathname);
  const anchor = decodeLinkPart(parsed.hash.replace(/^#/, ""));
  let path: string;
  if (parsed.host !== "") {
    path = `\\\\${parsed.host}${pathname.replace(/\//g, "\\")}`;
  } else if (/^\/[a-zA-Z]:([\/]|$)/.test(pathname)) {
    path = pathname.slice(1).replace(/\//g, "\\");
  } else {
    path = pathname;
  }
  return { path, anchor: anchor === "" ? null : anchor };
}

/**
 * Classifies a link href and, for local Markdown files, resolves it against `dir` (the directory
 * of the file the link appears in). Pure, so it can be unit tested without Tauri.
 */
export function resolveLinkTarget(href: string, dir: string | null): LinkTarget {
  const trimmed = href.trim();
  if (trimmed === "") {
    return { kind: "unsupported" };
  }
  if (trimmed.startsWith("#")) {
    return { kind: "anchor", anchor: decodeLinkPart(trimmed.slice(1)) };
  }
  // `file:` URLs are local paths, never handed to the OS: that could launch any program
  // (`file:///C:/Windows/System32/calc.exe`). Same rule as the TUI (doc/common.md 4).
  if (/^file:/i.test(trimmed)) {
    const local = fileUrlToPath(trimmed);
    if (local === null || !isMarkdownPath(local.path)) return { kind: "unsupported" };
    return { kind: "file", path: local.path, anchor: local.anchor };
  }
  // Check the scheme on the decoded form: normalizeUri turns `C:\docs\x.md` into `C:%5Cdocs%5Cx.md`,
  // which would otherwise look like a URL with the scheme `C:`. URLs are passed on as written.
  if (hasUriScheme(decodeLinkPart(trimmed))) {
    return { kind: "external", url: trimmed };
  }

  const hashIndex = trimmed.indexOf("#");
  const rawPath = hashIndex === -1 ? trimmed : trimmed.slice(0, hashIndex);
  const rawAnchor = hashIndex === -1 ? "" : trimmed.slice(hashIndex + 1);
  const decodedPath = decodeLinkPart(rawPath);
  const path = isAbsolutePath(decodedPath) || !dir ? decodedPath : resolveRelativePath(dir, decodedPath);
  if (!isMarkdownPath(path)) {
    return { kind: "unsupported" };
  }
  const anchor = decodeLinkPart(rawAnchor);
  return { kind: "file", path, anchor: anchor === "" ? null : anchor };
}

/** Banner messages for links that cannot be followed (doc/common.md 4; same wording as the TUI). */
export const linkErrors = {
  unsupported: (href: string) => `サポートしていないリンク: ${href}`,
  missingFile: (path: string) => `ファイルが見つかりません: ${path}`,
  missingAnchor: (anchor: string) => `見出しが見つかりません: #${anchor}`,
  cannotOpenUrl: (url: string) => `ブラウザを開けませんでした: ${url}`,
};

/**
 * Scrolls to the element with the given id inside `container` only. Every open tab stays mounted
 * (hidden) at once, so a document-wide lookup could hit a same-id heading in another tab.
 */
export function scrollToIdWithin(container: ParentNode, id: string, behavior: ScrollBehavior): boolean {
  const target = Array.from(container.querySelectorAll<HTMLElement>("[id]")).find((el) => el.id === id);
  target?.scrollIntoView({ behavior, block: "start" });
  return target !== undefined;
}
