import { useEffect, useId, useRef, useState } from "react";
import mermaid from "mermaid";
import { useOsTheme } from "../hooks/useOsTheme";

interface MermaidBlockProps {
  code: string;
}

export function MermaidBlock({ code }: MermaidBlockProps) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const theme = useOsTheme();

  useEffect(() => {
    let cancelled = false;
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      suppressErrorRendering: true,
      theme: theme === "dark" ? "dark" : "default",
    });
    setError(null);

    mermaid
      .render(`mermaid-${id}`, code)
      .then(({ svg }) => {
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [id, code, theme]);

  if (error) {
    return (
      <div className="mermaid-block mermaid-block--error">
        <p>Mermaid記法エラー:</p>
        <pre>{error}</pre>
      </div>
    );
  }

  return <div className="mermaid-block" ref={containerRef} />;
}
