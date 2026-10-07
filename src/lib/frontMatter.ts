import { parse } from "yaml";

/** A parsed front matter value. The failsafe schema keeps every scalar as its literal string. */
export type FrontMatterValue = string | null | FrontMatterValue[] | { [key: string]: FrontMatterValue };

export type FrontMatterData = Record<string, FrontMatterValue>;

export type ParsedDocument =
  | { kind: "none"; body: string }
  | { kind: "ok"; body: string; data: FrontMatterData }
  | { kind: "error"; body: string; raw: string; message: string };

export interface FrontMatterView {
  title: string | null;
  /** `author` then `date`, each only if present and non-empty. */
  byline: string[];
  /** Every other key, in the order written. */
  others: [string, string][];
}

const OPEN_FENCE = /^---[ \t]*$/;
const CLOSE_FENCE = /^(---|\.\.\.)[ \t]*$/;
const NOT_A_MAPPING_MESSAGE = "フロントマターがキーと値の形式ではありません";

/**
 * Splits a leading YAML front matter block off the Markdown source (requirements.md 3.12,
 * spec.md 12.2). Done before any Markdown parsing so the block never reaches react-markdown or
 * the docx converter as an `<hr>` + setext heading.
 *
 * Parsed with the failsafe schema on purpose: scalars stay exactly as written, so `2026-10-08`
 * isn't turned into a Date and `1.10` isn't turned into the number 1.1.
 */
export function parseFrontMatter(content: string): ParsedDocument {
  const source = content.startsWith("﻿") ? content.slice(1) : content;
  const lines = source.split(/\r?\n/);
  if (lines.length === 0 || !OPEN_FENCE.test(lines[0])) return { kind: "none", body: content };

  const closeIndex = lines.findIndex((line, i) => i > 0 && CLOSE_FENCE.test(line));
  // No closing fence: not front matter after all, just a document that starts with a rule.
  if (closeIndex === -1) return { kind: "none", body: content };

  const raw = lines.slice(1, closeIndex).join("\n");
  const body = lines.slice(closeIndex + 1).join("\n");

  let parsed: unknown;
  try {
    parsed = parse(raw, { schema: "failsafe" });
  } catch (err) {
    return { kind: "error", body, raw, message: err instanceof Error ? err.message : String(err) };
  }

  // An empty or whitespace-only block parses to null/"": nothing to show, but still not body text.
  if (parsed === null || parsed === undefined || parsed === "") return { kind: "ok", body, data: {} };
  if (typeof parsed !== "object" || Array.isArray(parsed)) {
    return { kind: "error", body, raw, message: NOT_A_MAPPING_MESSAGE };
  }
  return { kind: "ok", body, data: parsed as FrontMatterData };
}

/** Flattens a value to one display line: arrays as "a, b", objects as "k: v, k2: v2". */
export function formatValue(value: FrontMatterValue | undefined): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  return Object.entries(value)
    .map(([key, v]) => `${key}: ${formatValue(v)}`)
    .join(", ");
}

/** `author` may be a single name or a list of names; a list is joined with "、". */
export function formatAuthor(value: FrontMatterValue | undefined): string {
  if (Array.isArray(value)) return value.map(formatValue).filter((s) => s !== "").join("、");
  return formatValue(value);
}

/** Splits front matter into the prominent fields (title / author / date) and everything else (spec.md 12.3). */
export function toFrontMatterView(data: FrontMatterData): FrontMatterView {
  const title = formatValue(data.title);
  const author = formatAuthor(data.author);
  const date = formatValue(data.date);
  const others = Object.entries(data)
    .filter(([key]) => key !== "title" && key !== "author" && key !== "date")
    .map(([key, value]): [string, string] => [key, formatValue(value)]);
  return {
    title: title === "" ? null : title,
    byline: [author, date].filter((s) => s !== ""),
    others,
  };
}
