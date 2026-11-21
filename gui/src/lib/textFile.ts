/** Banner message for a file whose bytes are not valid UTF-8 (doc/common.md 1). */
export const notUtf8Message = (path: string) => `UTF-8 として読み込めないファイルです: ${path}`;

/**
 * Decodes a Markdown file's bytes as UTF-8 and rejects anything else (e.g. Shift_JIS).
 * plugin-fs's readTextFile decodes non-fatally, silently turning invalid bytes into U+FFFD and
 * showing garbage, so the bytes are read with readFile and decoded here with `fatal: true`.
 * A leading BOM is dropped (TextDecoder's default).
 */
export function decodeUtf8(bytes: Uint8Array, path: string): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new Error(notUtf8Message(path));
  }
}
