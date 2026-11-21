import { describe, expect, it } from "vitest";
import { hasUriScheme, isAbsolutePath, resolveRelativePath } from "./paths";

describe("isAbsolutePath", () => {
  it("recognizes Windows drive-letter paths", () => {
    expect(isAbsolutePath("C:\\Users\\foo")).toBe(true);
    expect(isAbsolutePath("C:/Users/foo")).toBe(true);
  });

  it("recognizes UNC paths", () => {
    expect(isAbsolutePath("\\\\server\\share")).toBe(true);
  });

  it("recognizes POSIX-style absolute paths", () => {
    expect(isAbsolutePath("/etc/hosts")).toBe(true);
  });

  it("rejects relative paths", () => {
    expect(isAbsolutePath("./foo.md")).toBe(false);
    expect(isAbsolutePath("foo.md")).toBe(false);
    expect(isAbsolutePath("../foo.md")).toBe(false);
  });
});

describe("hasUriScheme", () => {
  it("detects common URI schemes", () => {
    expect(hasUriScheme("https://example.com")).toBe(true);
    expect(hasUriScheme("mailto:a@example.com")).toBe(true);
    expect(hasUriScheme("data:image/png;base64,abc")).toBe(true);
  });

  it("does not mistake a Windows drive letter for a URI scheme", () => {
    expect(hasUriScheme("C:\\Users\\foo")).toBe(false);
  });

  it("returns false for relative paths", () => {
    expect(hasUriScheme("./foo.md")).toBe(false);
  });
});

describe("resolveRelativePath", () => {
  const base = "C:\\Users\\circl\\work\\mdview";

  it("joins a simple relative path", () => {
    expect(resolveRelativePath(base, "foo.md")).toBe("C:\\Users\\circl\\work\\mdview\\foo.md");
  });

  it("resolves a leading ./ segment", () => {
    expect(resolveRelativePath(base, "./foo.md")).toBe("C:\\Users\\circl\\work\\mdview\\foo.md");
  });

  it("resolves ../ by walking up a directory", () => {
    expect(resolveRelativePath(base, "../sibling.md")).toBe(
      "C:\\Users\\circl\\work\\sibling.md",
    );
  });

  it("resolves a nested subdirectory path", () => {
    expect(resolveRelativePath(base, "assets/img.png")).toBe(
      "C:\\Users\\circl\\work\\mdview\\assets\\img.png",
    );
  });

  it("does not walk above the drive root", () => {
    expect(resolveRelativePath("C:\\", "../../foo.md")).toBe("C:\\foo.md");
  });

  it("returns an already-absolute target unchanged", () => {
    expect(resolveRelativePath(base, "D:\\other\\file.md")).toBe("D:\\other\\file.md");
  });
});
