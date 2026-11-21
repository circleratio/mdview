import { describe, expect, it } from "vitest";
import { formatValue, parseFrontMatter, toFrontMatterView } from "./frontMatter";

describe("parseFrontMatter", () => {
  it("returns the content untouched when there is no front matter", () => {
    const content = "# Title\n\nbody";
    expect(parseFrontMatter(content)).toEqual({ kind: "none", body: content });
  });

  it("treats a leading rule without a closing fence as plain content", () => {
    const content = "---\n\n# Title";
    expect(parseFrontMatter(content)).toEqual({ kind: "none", body: content });
  });

  it("splits front matter closed by ---", () => {
    const result = parseFrontMatter("---\ntitle: Memo\n---\n# Heading\n");
    expect(result).toEqual({ kind: "ok", body: "# Heading\n", data: { title: "Memo" } });
  });

  it("accepts ... as the closing fence", () => {
    const result = parseFrontMatter("---\ntitle: Memo\n...\nbody");
    expect(result).toEqual({ kind: "ok", body: "body", data: { title: "Memo" } });
  });

  it("handles CRLF line endings, a BOM and trailing spaces on the fences", () => {
    const result = parseFrontMatter("﻿--- \r\ntitle: Memo\r\n---  \r\nbody\r\n");
    expect(result).toEqual({ kind: "ok", body: "body\n", data: { title: "Memo" } });
  });

  it("leaves later --- lines in the body", () => {
    const result = parseFrontMatter("---\ntitle: Memo\n---\nabove\n\n---\n\nbelow");
    expect(result.body).toBe("above\n\n---\n\nbelow");
  });

  it("keeps scalars exactly as written", () => {
    const result = parseFrontMatter("---\ndate: 2026-10-08\nversion: 1.10\ndraft: true\n---\n");
    expect(result).toMatchObject({ kind: "ok", data: { date: "2026-10-08", version: "1.10", draft: "true" } });
  });

  it("strips an empty front matter block with no data", () => {
    expect(parseFrontMatter("---\n---\nbody")).toEqual({ kind: "ok", body: "body", data: {} });
    expect(parseFrontMatter("---\n  \n---\nbody")).toEqual({ kind: "ok", body: "body", data: {} });
  });

  it("reports YAML syntax errors with the raw block, still stripping it from the body", () => {
    const result = parseFrontMatter("---\ntags: [a,\n---\nbody");
    expect(result.kind).toBe("error");
    expect(result.body).toBe("body");
    if (result.kind === "error") {
      expect(result.raw).toBe("tags: [a,");
      expect(result.message).not.toBe("");
    }
  });

  it("reports a top-level value that is not a mapping", () => {
    for (const raw of ["- a\n- b", "just text"]) {
      const result = parseFrontMatter(`---\n${raw}\n---\nbody`);
      expect(result).toMatchObject({ kind: "error", raw, message: "フロントマターがキーと値の形式ではありません" });
    }
  });
});

describe("formatValue", () => {
  it("flattens strings, arrays, objects and empty values", () => {
    expect(formatValue("text")).toBe("text");
    expect(formatValue(["a", "b"])).toBe("a, b");
    expect(formatValue({ name: "x", url: "y" })).toBe("name: x, url: y");
    expect(formatValue([{ k: "v" }, "z"])).toBe("k: v, z");
    expect(formatValue("")).toBe("");
    expect(formatValue(null)).toBe("");
  });
});

describe("toFrontMatterView", () => {
  it("separates title, author and date from the other fields, keeping their order", () => {
    const view = toFrontMatterView({ tags: ["a", "b"], title: "Memo", status: "draft", date: "2026-10-08", author: "Fujiwara" });
    expect(view).toEqual({
      title: "Memo",
      byline: ["Fujiwara", "2026-10-08"],
      others: [
        ["tags", "a, b"],
        ["status", "draft"],
      ],
    });
  });

  it("joins multiple authors with 、", () => {
    expect(toFrontMatterView({ author: ["A", "B"] }).byline).toEqual(["A、B"]);
  });

  it("omits missing or empty prominent fields", () => {
    expect(toFrontMatterView({ title: "", date: "2026-10-08" })).toEqual({
      title: null,
      byline: ["2026-10-08"],
      others: [],
    });
    expect(toFrontMatterView({})).toEqual({ title: null, byline: [], others: [] });
  });

  it("is case-sensitive about the prominent keys", () => {
    expect(toFrontMatterView({ Title: "X" })).toEqual({ title: null, byline: [], others: [["Title", "X"]] });
  });
});
