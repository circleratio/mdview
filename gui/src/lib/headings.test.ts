import { describe, expect, it } from "vitest";
import { buildHeadingTree, type HeadingItem } from "./headings";

describe("buildHeadingTree", () => {
  it("returns an empty tree for no headings", () => {
    expect(buildHeadingTree([])).toEqual([]);
  });

  it("nests headings under their nearest preceding lower-level heading", () => {
    const headings: HeadingItem[] = [
      { id: "a", text: "A", level: 1 },
      { id: "b", text: "B", level: 2 },
      { id: "c", text: "C", level: 3 },
      { id: "d", text: "D", level: 2 },
    ];

    const tree = buildHeadingTree(headings);

    expect(tree).toHaveLength(1);
    expect(tree[0].id).toBe("a");
    expect(tree[0].children.map((n) => n.id)).toEqual(["b", "d"]);
    expect(tree[0].children[0].children.map((n) => n.id)).toEqual(["c"]);
  });

  it("treats a heading level jump (e.g. h1 to h3) as a direct child", () => {
    const headings: HeadingItem[] = [
      { id: "a", text: "A", level: 1 },
      { id: "b", text: "B", level: 3 },
    ];

    const tree = buildHeadingTree(headings);

    expect(tree[0].children.map((n) => n.id)).toEqual(["b"]);
  });

  it("starts a new root when a heading is not deeper than the current root", () => {
    const headings: HeadingItem[] = [
      { id: "a", text: "A", level: 2 },
      { id: "b", text: "B", level: 1 },
    ];

    const tree = buildHeadingTree(headings);

    expect(tree.map((n) => n.id)).toEqual(["a", "b"]);
  });
});
