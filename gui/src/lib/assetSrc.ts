import { convertFileSrc } from "@tauri-apps/api/core";
import { decodeLinkPart, fileUrlToPath } from "./links";
import { hasUriScheme, isAbsolutePath, resolveRelativePath } from "./paths";

/**
 * Resolves an image src from Markdown to an absolute local path, or returns null when it is a URL
 * (`https:`, `data:`, ...) to be used as is. `file:` URLs are turned into local paths too. Pure, so it can be unit tested without Tauri.
 *
 * The src is percent-decoded first: mdast-util-to-hast percent-encodes every `src` (`normalizeUri`),
 * so `![](図.png)` arrives as `%E5%9B%B3.png`, and `convertFileSrc` encodes the path again. The asset
 * protocol only decodes once, so without this the file name would never match.
 */
export function resolveAssetPath(src: string, dir: string | null): string | null {
  if (/^file:/i.test(src)) {
    // The webview cannot load file: URLs; serve the local file through the asset protocol instead.
    return fileUrlToPath(src)?.path ?? null;
  }
  const decoded = decodeLinkPart(src);
  if (hasUriScheme(decoded)) {
    return null;
  }
  return isAbsolutePath(decoded) || !dir ? decoded : resolveRelativePath(dir, decoded);
}

/** Resolves an `<img>` src from markdown into a URL the webview can actually load. */
export function resolveAssetSrc(src: string, dir: string | null): string {
  const path = resolveAssetPath(src, dir);
  return path === null ? src : convertFileSrc(path);
}
