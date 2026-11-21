const MARKDOWN_EXTENSIONS = [".md", ".markdown"];

export function isMarkdownPath(path: string): boolean {
  const lower = path.toLowerCase();
  return MARKDOWN_EXTENSIONS.some((ext) => lower.endsWith(ext));
}
