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

/**
 * Scrolls to the element with the given id inside `container` only. Every open tab stays mounted
 * (hidden) at once, so a document-wide lookup could hit a same-id heading in another tab.
 */
export function scrollToIdWithin(container: ParentNode, id: string, behavior: ScrollBehavior): boolean {
  const target = Array.from(container.querySelectorAll<HTMLElement>("[id]")).find((el) => el.id === id);
  target?.scrollIntoView({ behavior, block: "start" });
  return target !== undefined;
}
