import { convertFileSrc } from "@tauri-apps/api/core";
import { hasUriScheme, isAbsolutePath, resolveRelativePath } from "./paths";

/** Resolves an `<img>` src from markdown into a URL the webview can actually load. */
export function resolveAssetSrc(src: string, dir: string | null): string {
  if (hasUriScheme(src)) {
    return src;
  }

  const absolute = isAbsolutePath(src) || !dir ? src : resolveRelativePath(dir, src);
  return convertFileSrc(absolute);
}
