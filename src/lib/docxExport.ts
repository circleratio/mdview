import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { toPng } from "html-to-image";
import {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  HeadingLevel,
  ImageRun,
  LevelFormat,
  LineRuleType,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
  type FileChild,
  type ParagraphChild,
} from "docx";
import { hasUriScheme } from "./paths";
import { resolveAssetSrc } from "./assetSrc";
import { formatAuthor, parseFrontMatter, toFrontMatterView, type FrontMatterView } from "./frontMatter";

/**
 * Loosely-typed mdast node covering only the fields this converter reads. Using the real
 * `mdast`/`mdast-util-math` type packages here would require threading two separate node-type
 * unions (core mdast + math extension) through every helper for no real safety gain, since the
 * whole tree is walked generically by `node.type` anyway.
 */
interface MdNode {
  type: string;
  value?: string;
  url?: string;
  alt?: string | null;
  depth?: number;
  ordered?: boolean | null;
  checked?: boolean | null;
  align?: (string | null)[];
  lang?: string | null;
  children?: MdNode[];
}

interface BlockContext {
  listLevel: number;
  quoteDepth: number;
}

interface Marks {
  bold?: boolean;
  italics?: boolean;
  strike?: boolean;
  link?: boolean;
  font?: string;
  size?: number;
  color?: string;
}

/**
 * DOM elements pre-collected from the active tab's container, consumed in document order as the
 * AST walk reaches the matching Mermaid/math node (see spec.md 6.1). Also carries `titleConsumed`,
 * a one-shot flag: the first `depth === 1` heading encountered during the walk becomes the
 * document title, and any later `depth === 1` heading falls back to regular heading formatting.
 */
interface RasterResources {
  dir: string | null;
  mermaidEls: HTMLElement[];
  mermaidIndex: number;
  katexEls: HTMLElement[];
  katexIndex: number;
  titleConsumed: boolean;
}

const MONO_FONT = "Consolas";
const CODE_SHADING = "F2F2F2";
const QUOTE_BORDER_COLOR = "AAAAAA";
const HYPERLINK_COLOR = "0563C1";
// Fixed font assignment (requirements.md 3.10, spec.md 6.1). "游ゴシック Medium" is its own font
// family name on Windows (not a bold variant of 游ゴシック), so it's set via `font`, not `bold`.
// docx sizes are in half-points: 18pt -> 36, 14pt -> 28, 10.5pt -> 21. Title/heading color is
// pinned to black at the run level because Word's default Title/Heading styles can carry a
// theme color (not plain black) that direct font/size formatting alone wouldn't override.
const HEADING_FONT = "游ゴシック Medium";
const TITLE_SIZE = 36;
const HEADING_SIZE = 28;
const BODY_FONT = "游明朝";
const BODY_SIZE = 21;
const BLACK_COLOR = "000000";
const TITLE_MARKS: Marks = { font: HEADING_FONT, size: TITLE_SIZE, color: BLACK_COLOR };
const HEADING_MARKS: Marks = { font: HEADING_FONT, size: HEADING_SIZE, color: BLACK_COLOR };
const BODY_MARKS: Marks = { font: BODY_FONT, size: BODY_SIZE };

/**
 * Line spacing (requirements.md 3.10, spec.md 6.1): "1.5 line spacing" is defined as the gap
 * between lines being 0.5x the font size, i.e. line height = 1.5x the font size. Word's own
 * "multiple" line rule (`lineRule: AUTO`) instead multiplies the font's built-in default line
 * height (usually taller than its point size), which reads as too much extra gap. So `line` is
 * computed directly from the font size in twips (pt * 20) rather than left to Word's multiplier.
 * `atLeast` (not `exact`) lets a line grow past this height for an inline KaTeX image taller than
 * the surrounding text, instead of clipping it; for plain text lines the result matches `exact`.
 */
function textSpacing(sizeHalfPoints: number) {
  return { line: sizeHalfPoints * 15, lineRule: LineRuleType.AT_LEAST, after: 120 };
}
const TITLE_SPACING = textSpacing(TITLE_SIZE);
const HEADING_SPACING = textSpacing(HEADING_SIZE);
const BODY_SPACING = textSpacing(BODY_SIZE);
/** For paragraphs holding only a rasterized image (Mermaid/KaTeX block): the image height has no
 * relation to any font size, so only the 6pt space-after is set and Word sizes the line to the image. */
const IMAGE_ONLY_SPACING = { after: 120 };
const MAX_IMAGE_WIDTH_PX = 600;
const BULLET_REF = "mdview-bullet";
const NUMBER_REF = "mdview-number";
const MAX_LIST_LEVEL = 4;

const numberingConfig = {
  config: [
    {
      reference: BULLET_REF,
      levels: Array.from({ length: MAX_LIST_LEVEL + 1 }, (_, level) => ({
        level,
        format: LevelFormat.BULLET,
        text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360 + level * 360, hanging: 360 } } },
      })),
    },
    {
      reference: NUMBER_REF,
      levels: Array.from({ length: MAX_LIST_LEVEL + 1 }, (_, level) => ({
        level,
        format: LevelFormat.DECIMAL,
        text: `%${level + 1}.`,
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360 + level * 360, hanging: 360 } } },
      })),
    },
  ],
};

export interface DocxExportInput {
  content: string;
  dir: string | null;
  /** The active tab's rendered container, used to source Mermaid/KaTeX images. Pass null to skip those (they fall back to plain text/code). */
  container: HTMLElement | null;
}

/** Converts Markdown source into a `.docx` file's raw bytes (requirements.md 3.10 / spec.md 6). */
export async function convertMarkdownToDocx({ content, dir, container }: DocxExportInput): Promise<Uint8Array> {
  // Front matter never reaches the Markdown parser; only title/author/date are carried over (spec.md 12.5).
  const parsed = parseFrontMatter(content);
  const frontMatter = parsed.kind === "ok" ? toFrontMatterView(parsed.data) : null;
  const processor = unified().use(remarkParse).use(remarkGfm).use(remarkMath);
  const tree = processor.runSync(processor.parse(parsed.body)) as unknown as MdNode;

  const res: RasterResources = {
    dir,
    mermaidEls: container ? Array.from(container.querySelectorAll<HTMLElement>(".mermaid-block")) : [],
    mermaidIndex: 0,
    katexEls: container ? Array.from(container.querySelectorAll<HTMLElement>(".katex")) : [],
    katexIndex: 0,
    // A front matter title takes the document-title slot, so every `#` heading in the body
    // gets regular heading formatting.
    titleConsumed: frontMatter?.title != null,
  };

  const children = [
    ...buildFrontMatterParagraphs(frontMatter),
    ...(await convertBlocks(tree.children ?? [], { listLevel: 0, quoteDepth: 0 }, res)),
  ];

  const author = parsed.kind === "ok" ? formatAuthor(parsed.data.author) : "";
  const doc = new Document({
    ...(frontMatter?.title != null && { title: frontMatter.title }),
    ...(author !== "" && { creator: author }),
    numbering: numberingConfig,
    sections: [{ children: children.length > 0 ? children : [new Paragraph({ spacing: BODY_SPACING })] }],
  });

  const blob = await Packer.toBlob(doc);
  return new Uint8Array(await blob.arrayBuffer());
}

/** Title (document-title formatting) and an author/date line, mirroring the on-screen header. Other fields are not exported. */
function buildFrontMatterParagraphs(view: FrontMatterView | null): Paragraph[] {
  if (!view) return [];
  const out: Paragraph[] = [];
  if (view.title !== null) {
    out.push(
      new Paragraph({
        heading: HeadingLevel.TITLE,
        spacing: TITLE_SPACING,
        children: [buildTextRun(view.title, TITLE_MARKS)],
      }),
    );
  }
  if (view.byline.length > 0) {
    out.push(new Paragraph({ spacing: BODY_SPACING, children: [buildTextRun(view.byline.join(" ・ "), BODY_MARKS)] }));
  }
  return out;
}

async function convertBlocks(nodes: MdNode[], ctx: BlockContext, res: RasterResources): Promise<FileChild[]> {
  const out: FileChild[] = [];
  for (const node of nodes) {
    out.push(...(await convertBlock(node, ctx, res)));
  }
  return out;
}

async function convertBlock(node: MdNode, ctx: BlockContext, res: RasterResources): Promise<FileChild[]> {
  switch (node.type) {
    case "heading": {
      const isTitle = node.depth === 1 && !res.titleConsumed;
      if (isTitle) res.titleConsumed = true;
      const runs = await convertInline(node.children ?? [], isTitle ? TITLE_MARKS : HEADING_MARKS, res);
      const heading = isTitle ? HeadingLevel.TITLE : headingLevelFor(node.depth ?? 1);
      return [new Paragraph({ heading, spacing: isTitle ? TITLE_SPACING : HEADING_SPACING, children: runs })];
    }
    case "paragraph": {
      const runs = await convertInline(node.children ?? [], BODY_MARKS, res);
      if (ctx.quoteDepth === 0) {
        return [new Paragraph({ spacing: BODY_SPACING, children: runs })];
      }
      return [
        new Paragraph({
          children: runs,
          spacing: BODY_SPACING,
          indent: { left: 360 * ctx.quoteDepth },
          border: { left: { style: BorderStyle.SINGLE, size: 12, color: QUOTE_BORDER_COLOR, space: 8 } },
        }),
      ];
    }
    case "blockquote":
      return convertBlocks(node.children ?? [], { ...ctx, quoteDepth: ctx.quoteDepth + 1 }, res);
    case "list": {
      const items: FileChild[] = [];
      for (const item of node.children ?? []) {
        items.push(...(await convertListItem(item, node.ordered === true, ctx, res)));
      }
      return items;
    }
    case "code":
      if (node.lang === "mermaid") {
        return convertMermaidBlock(node, res);
      }
      return convertCodeBlock(node);
    case "math": {
      const run = await buildMathImageRun(res);
      if (run) return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: IMAGE_ONLY_SPACING, children: [run] })];
      return convertCodeBlock(node);
    }
    case "table":
      return [await convertTable(node, res)];
    case "thematicBreak":
      return [
        new Paragraph({
          spacing: BODY_SPACING,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: QUOTE_BORDER_COLOR } },
        }),
      ];
    case "html":
      // Raw HTML block: no HTML-to-docx conversion is attempted, so keep the source visible as plain text
      // rather than silently dropping the content.
      return node.value
        ? [new Paragraph({ spacing: BODY_SPACING, children: [buildTextRun(node.value, BODY_MARKS)] })]
        : [];
    default:
      return node.children ? convertBlocks(node.children, ctx, res) : [];
  }
}

async function convertListItem(
  item: MdNode,
  ordered: boolean,
  ctx: BlockContext,
  res: RasterResources,
): Promise<FileChild[]> {
  const level = Math.min(ctx.listLevel, MAX_LIST_LEVEL);
  const isTask = typeof item.checked === "boolean";
  const out: FileChild[] = [];
  let firstParagraphDone = false;

  for (const child of item.children ?? []) {
    if (child.type === "paragraph") {
      const runs = await convertInline(child.children ?? [], BODY_MARKS, res);
      if (isTask && !firstParagraphDone) {
        runs.unshift(buildTextRun(item.checked ? "☑ " : "☐ ", BODY_MARKS));
      }
      out.push(
        new Paragraph(
          isTask
            ? { children: runs, spacing: BODY_SPACING, indent: { left: 360 + level * 360 } }
            : {
                children: runs,
                spacing: BODY_SPACING,
                numbering: { reference: ordered ? NUMBER_REF : BULLET_REF, level },
              },
        ),
      );
      firstParagraphDone = true;
    } else if (child.type === "list") {
      out.push(...(await convertBlock(child, { ...ctx, listLevel: level + 1 }, res)));
    } else {
      out.push(...(await convertBlock(child, ctx, res)));
    }
  }
  return out;
}

async function convertTable(node: MdNode, res: RasterResources): Promise<Table> {
  const align = node.align ?? [];
  const rows: TableRow[] = [];
  const rowNodes = node.children ?? [];

  for (let r = 0; r < rowNodes.length; r++) {
    const isHeader = r === 0;
    const cellNodes = rowNodes[r].children ?? [];
    const cells: TableCell[] = [];
    for (let c = 0; c < cellNodes.length; c++) {
      const runs = await convertInline(cellNodes[c].children ?? [], { ...BODY_MARKS, bold: isHeader }, res);
      cells.push(
        new TableCell({
          children: [
            new Paragraph({ children: runs, spacing: BODY_SPACING, alignment: alignmentFor(align[c]) }),
          ],
          width: { size: Math.floor(100 / Math.max(1, cellNodes.length)), type: WidthType.PERCENTAGE },
        }),
      );
    }
    rows.push(new TableRow({ children: cells }));
  }
  return new Table({ rows, width: { size: 100, type: WidthType.PERCENTAGE } });
}

function convertCodeBlock(node: MdNode): Paragraph[] {
  const lines = (node.value ?? "").split("\n");
  return lines.map(
    (line) =>
      new Paragraph({
        shading: { type: ShadingType.CLEAR, fill: CODE_SHADING },
        spacing: { before: 0, after: 0 },
        children: [new TextRun({ text: line, font: MONO_FONT })],
      }),
  );
}

async function convertMermaidBlock(node: MdNode, res: RasterResources): Promise<FileChild[]> {
  const el = res.mermaidEls[res.mermaidIndex++];
  if (el && !el.classList.contains("mermaid-block--error")) {
    const run = await rasterizeElementToImageRun(el);
    if (run) return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: IMAGE_ONLY_SPACING, children: [run] })];
  }
  // Rendering failed, or rasterization failed: fall back to the raw Mermaid source as code text.
  return convertCodeBlock(node);
}

async function convertInline(nodes: MdNode[], marks: Marks, res: RasterResources): Promise<ParagraphChild[]> {
  const out: ParagraphChild[] = [];
  for (const node of nodes) {
    switch (node.type) {
      case "text":
        out.push(buildTextRun(node.value ?? "", marks));
        break;
      case "strong":
        out.push(...(await convertInline(node.children ?? [], { ...marks, bold: true }, res)));
        break;
      case "emphasis":
        out.push(...(await convertInline(node.children ?? [], { ...marks, italics: true }, res)));
        break;
      case "delete":
        out.push(...(await convertInline(node.children ?? [], { ...marks, strike: true }, res)));
        break;
      case "inlineCode":
        // Spread order matters: the heading/body font inherited via `marks` must not win over
        // the fixed monospace code font, so `font` is set after the spread, not before it.
        out.push(new TextRun({ ...marksToRunOptions(marks), text: node.value ?? "", font: MONO_FONT }));
        break;
      case "break":
        out.push(new TextRun({ text: "", break: 1 }));
        break;
      case "link": {
        // Convert children exactly once: this subtree may contain images/math that consume
        // res.mermaidIndex/katexIndex, and a second pass would desync every later correlation.
        const isExternal = !!node.url && hasUriScheme(node.url);
        const runs = await convertInline(node.children ?? [], isExternal ? { ...marks, link: true } : marks, res);
        if (isExternal) {
          out.push(new ExternalHyperlink({ link: node.url as string, children: runs }));
        } else {
          // Relative Markdown links / same-document anchors have no meaningful target once
          // exported to a standalone Word file, so only the visible text is kept (requirements.md 3.10).
          out.push(...runs);
        }
        break;
      }
      case "image": {
        const run = node.url ? await buildImageRun(node.url, res) : null;
        out.push(run ?? buildTextRun(node.alt || node.url || "", marks));
        break;
      }
      case "inlineMath": {
        const run = await buildMathImageRun(res);
        out.push(run ?? buildTextRun(node.value ?? "", { ...marks }));
        break;
      }
      default:
        if (node.children) out.push(...(await convertInline(node.children, marks, res)));
    }
  }
  return out;
}

function marksToRunOptions(marks: Marks) {
  return {
    bold: marks.bold,
    italics: marks.italics,
    strike: marks.strike,
    font: marks.font,
    size: marks.size,
    color: marks.color,
    // A link inside a title/heading still reads as a link, so its color wins over the
    // inherited title/heading black.
    ...(marks.link ? { color: HYPERLINK_COLOR, underline: {} } : {}),
  };
}

function buildTextRun(text: string, marks: Marks): TextRun {
  return new TextRun({ text, ...marksToRunOptions(marks) });
}

async function buildMathImageRun(res: RasterResources): Promise<ImageRun | null> {
  const el = res.katexEls[res.katexIndex++];
  if (!el) return null;
  return rasterizeElementToImageRun(el);
}

async function buildImageRun(url: string, res: RasterResources): Promise<ImageRun | null> {
  try {
    const resolvedUrl = resolveAssetSrc(url, res.dir);
    const response = await fetch(resolvedUrl);
    if (!response.ok) return null;
    const contentType = response.headers.get("content-type");
    const type = guessImageType(url, contentType);
    if (!type) return null;
    const buffer = await response.arrayBuffer();
    const dims = await loadImageDimensions(buffer, contentType ?? undefined);
    if (!dims || dims.width === 0 || dims.height === 0) return null;
    const { width, height } = scaleToMaxWidth(dims.width, dims.height, MAX_IMAGE_WIDTH_PX);
    return new ImageRun({ type, data: new Uint8Array(buffer), transformation: { width, height } });
  } catch {
    // Missing/unreadable/unsupported-format image: caller falls back to the alt text.
    return null;
  }
}

/** Rasterizes a rendered DOM element (Mermaid SVG container or a KaTeX span) to a PNG at its on-screen size (requirements.md 3.10: no upscaling). */
async function rasterizeElementToImageRun(el: HTMLElement): Promise<ImageRun | null> {
  try {
    const rect = el.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    const dataUrl = await toPng(el, { pixelRatio: 1, backgroundColor: "#ffffff" });
    const scaled = scaleToMaxWidth(width, height, MAX_IMAGE_WIDTH_PX);
    return new ImageRun({ type: "png", data: dataUrlToBytes(dataUrl), transformation: scaled });
  } catch {
    return null;
  }
}

function dataUrlToBytes(dataUrl: string): Uint8Array {
  const base64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function loadImageDimensions(
  buffer: ArrayBuffer,
  mime = "image/png",
): Promise<{ width: number; height: number } | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(new Blob([buffer], { type: mime }));
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    img.src = url;
  });
}

function scaleToMaxWidth(width: number, height: number, maxWidth: number): { width: number; height: number } {
  if (width <= maxWidth || width === 0) return { width, height };
  const ratio = maxWidth / width;
  return { width: maxWidth, height: Math.max(1, Math.round(height * ratio)) };
}

function guessImageType(source: string, contentType: string | null): "png" | "jpg" | "gif" | "bmp" | null {
  const ct = contentType?.toLowerCase() ?? "";
  if (ct.includes("png")) return "png";
  if (ct.includes("jpeg") || ct.includes("jpg")) return "jpg";
  if (ct.includes("gif")) return "gif";
  if (ct.includes("bmp")) return "bmp";

  const ext = source.split(/[?#]/)[0].split(".").pop()?.toLowerCase();
  if (ext === "png") return "png";
  if (ext === "jpg" || ext === "jpeg") return "jpg";
  if (ext === "gif") return "gif";
  if (ext === "bmp") return "bmp";
  return null;
}

function headingLevelFor(depth: number): (typeof HeadingLevel)[keyof typeof HeadingLevel] {
  switch (depth) {
    case 1:
      return HeadingLevel.HEADING_1;
    case 2:
      return HeadingLevel.HEADING_2;
    case 3:
      return HeadingLevel.HEADING_3;
    case 4:
      return HeadingLevel.HEADING_4;
    case 5:
      return HeadingLevel.HEADING_5;
    default:
      return HeadingLevel.HEADING_6;
  }
}

function alignmentFor(align: string | null | undefined): (typeof AlignmentType)[keyof typeof AlignmentType] | undefined {
  if (align === "center") return AlignmentType.CENTER;
  if (align === "right") return AlignmentType.RIGHT;
  if (align === "left") return AlignmentType.LEFT;
  return undefined;
}
