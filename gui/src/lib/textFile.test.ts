import { describe, expect, it } from "vitest";
import { decodeUtf8, notUtf8Message } from "./textFile";

const bytes = (...values: number[]) => new Uint8Array(values);
const utf8 = (text: string) => new TextEncoder().encode(text);

describe("decodeUtf8", () => {
  it("decodes UTF-8 text", () => {
    expect(decodeUtf8(utf8("# 日本語\r\n"), "a.md")).toBe("# 日本語\r\n");
  });

  it("drops a leading BOM", () => {
    expect(decodeUtf8(bytes(0xef, 0xbb, 0xbf, ...utf8("# BOM")), "a.md")).toBe("# BOM");
  });

  it("rejects Shift_JIS bytes instead of showing replacement characters", () => {
    // "# 日本語" in Shift_JIS
    const sjis = bytes(0x23, 0x20, 0x93, 0xfa, 0x96, 0x7b, 0x8c, 0xea);
    expect(() => decodeUtf8(sjis, "C:\\docs\\sjis.md")).toThrow(notUtf8Message("C:\\docs\\sjis.md"));
  });

  it("rejects a truncated multi-byte sequence", () => {
    expect(() => decodeUtf8(bytes(0xe6, 0x97), "a.md")).toThrow(notUtf8Message("a.md"));
  });

  it("accepts an empty file", () => {
    expect(decodeUtf8(bytes(), "a.md")).toBe("");
  });
});
