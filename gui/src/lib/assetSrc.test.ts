import { describe, expect, it } from "vitest";
import { resolveAssetPath } from "./assetSrc";

const DIR = "C:\\docs";

describe("resolveAssetPath", () => {
  it("resolves a relative path against the directory", () => {
    expect(resolveAssetPath("img/a.png", DIR)).toBe("C:\\docs\\img\\a.png");
    expect(resolveAssetPath("../a.png", DIR)).toBe("C:\\a.png");
  });

  it("decodes the percent-encoding added by normalizeUri", () => {
    expect(resolveAssetPath("../img/%E5%9B%B3.png", DIR)).toBe("C:\\img\\図.png");
    expect(resolveAssetPath("my%20image.png", DIR)).toBe("C:\\docs\\my image.png");
    expect(resolveAssetPath("100%25.png", DIR)).toBe("C:\\docs\\100%.png");
  });

  it("keeps absolute paths, including backslash paths encoded as %5C", () => {
    expect(resolveAssetPath("C:/pics/a%20b.png", DIR)).toBe("C:/pics/a b.png");
    expect(resolveAssetPath("C:%5Cpics%5C%E7%94%BB%E5%83%8F.png", DIR)).toBe("C:\\pics\\画像.png");
  });

  it("leaves URLs alone", () => {
    expect(resolveAssetPath("https://example.com/a%20b.png", DIR)).toBeNull();
    expect(resolveAssetPath("data:image/png;base64,abc", DIR)).toBeNull();
  });

  it("does not resolve against a missing directory", () => {
    expect(resolveAssetPath("a.png", null)).toBe("a.png");
  });
});
