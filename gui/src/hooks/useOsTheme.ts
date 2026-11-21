import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

function getSystemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Tracks the OS light/dark setting live; used where CSS media queries alone can't reach (e.g. Mermaid's baked-in SVG colors). */
export function useOsTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(getSystemTheme);

  useEffect(() => {
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => setTheme(mql.matches ? "dark" : "light");
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  return theme;
}
