import { describe, expect, it } from "vitest";
import { decodeLinkPart, resolveLinkTarget } from "./links";

const DIR = "C:\\docs";

describe("decodeLinkPart", () => {
  it("decodes percent-encoding", () => {
    expect(decodeLinkPart("%E6%A6%82%E8%A6%81")).toBe("概要");
    expect(decodeLinkPart("my%20doc.md")).toBe("my doc.md");
  });

  it("keeps malformed input as is", () => {
    expect(decodeLinkPart("100%")).toBe("100%");
    expect(decodeLinkPart("%E6%A6")).toBe("%E6%A6");
  });
});

describe("resolveLinkTarget", () => {
  it("treats a leading # as an in-document anchor and decodes it", () => {
    expect(resolveLinkTarget("#overview", DIR)).toEqual({ kind: "anchor", anchor: "overview" });
    expect(resolveLinkTarget("#%E6%A6%82%E8%A6%81", DIR)).toEqual({ kind: "anchor", anchor: "概要" });
  });

  it("treats URLs with a scheme as external", () => {
    expect(resolveLinkTarget("https://example.com/a#b", DIR)).toEqual({
      kind: "external",
      url: "https://example.com/a#b",
    });
    expect(resolveLinkTarget("mailto:a@example.com", DIR)).toEqual({ kind: "external", url: "mailto:a@example.com" });
  });

  it("resolves a relative Markdown path against the directory", () => {
    expect(resolveLinkTarget("other.md", DIR)).toEqual({ kind: "file", path: "C:\\docs\\other.md", anchor: null });
    expect(resolveLinkTarget("../spec/a.markdown", DIR)).toEqual({ kind: "file", path: "C:\\spec\\a.markdown", anchor: null });
  });

  it("splits off the anchor of a Markdown file link", () => {
    expect(resolveLinkTarget("other.md#setup", DIR)).toEqual({ kind: "file", path: "C:\\docs\\other.md", anchor: "setup" });
    expect(resolveLinkTarget("other.md#", DIR)).toEqual({ kind: "file", path: "C:\\docs\\other.md", anchor: null });
  });

  it("decodes percent-encoded paths and anchors", () => {
    expect(resolveLinkTarget("my%20doc.md", DIR)).toEqual({ kind: "file", path: "C:\\docs\\my doc.md", anchor: null });
    expect(resolveLinkTarget("%E8%B3%87%E6%96%99.md#%E6%A6%82%E8%A6%81", DIR)).toEqual({
      kind: "file",
      path: "C:\\docs\\資料.md",
      anchor: "概要",
    });
  });

  it("keeps absolute paths as they are", () => {
    expect(resolveLinkTarget("D:/notes/x.md", DIR)).toEqual({ kind: "file", path: "D:/notes/x.md", anchor: null });
    // normalizeUri encodes backslashes, so a Windows path must not be mistaken for a `C:` URL.
    expect(resolveLinkTarget("D:%5Cnotes%5Cx.md#a", DIR)).toEqual({ kind: "file", path: "D:\\notes\\x.md", anchor: "a" });
  });

  it("does not resolve against a missing directory", () => {
    expect(resolveLinkTarget("other.md", null)).toEqual({ kind: "file", path: "other.md", anchor: null });
  });

  it("rejects non-Markdown local files and empty links", () => {
    expect(resolveLinkTarget("image.png", DIR)).toEqual({ kind: "unsupported" });
    expect(resolveLinkTarget("other.md.bak#x", DIR)).toEqual({ kind: "unsupported" });
    expect(resolveLinkTarget("  ", DIR)).toEqual({ kind: "unsupported" });
  });
});
