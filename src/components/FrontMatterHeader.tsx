import { useMemo } from "react";
import { toFrontMatterView, type ParsedDocument } from "../lib/frontMatter";

interface FrontMatterHeaderProps {
  parsed: ParsedDocument;
}

/**
 * Shows the document's front matter above the rendered Markdown (requirements.md 3.12,
 * spec.md 12.4). Rendered inside `.markdown-body`, so content zoom and in-page search cover it.
 *
 * The title deliberately isn't an `<h1>`: useHeadings collects every h1-h6 in the container
 * for the TOC, and the front matter title must stay out of it.
 */
export function FrontMatterHeader({ parsed }: FrontMatterHeaderProps) {
  const view = useMemo(() => (parsed.kind === "ok" ? toFrontMatterView(parsed.data) : null), [parsed]);

  if (parsed.kind === "error") {
    return (
      <div className="front-matter front-matter--error">
        {/* yaml's message is "<summary> at line N, column M:" followed by a code excerpt; the raw block below already shows the source. */}
        <p>フロントマターを解釈できませんでした: {parsed.message.split("\n")[0].replace(/:$/, "")}</p>
        <pre>{parsed.raw}</pre>
      </div>
    );
  }

  if (!view || (view.title === null && view.byline.length === 0 && view.others.length === 0)) return null;

  return (
    <header className="front-matter">
      {view.title !== null && <div className="front-matter__title">{view.title}</div>}
      {view.byline.length > 0 && <div className="front-matter__byline">{view.byline.join(" ・ ")}</div>}
      {view.others.length > 0 && (
        <dl className="front-matter__fields">
          {view.others.map(([key, value]) => (
            <div key={key} className="front-matter__field">
              <dt>{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </header>
  );
}
