import { useEffect, useRef } from "react";

interface SearchBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  matchCount: number;
  currentIndex: number;
  onNext: () => void;
  onPrev: () => void;
  onClose: () => void;
}

export function SearchBar({
  query,
  onQueryChange,
  matchCount,
  currentIndex,
  onNext,
  onPrev,
  onClose,
}: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <div className="search-bar">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            if (e.shiftKey) onPrev();
            else onNext();
          }
        }}
        placeholder="本文を検索"
        className="search-bar__input"
      />
      <span className="search-bar__count">
        {matchCount > 0 ? `${currentIndex + 1} / ${matchCount}` : query ? "0 / 0" : ""}
      </span>
      <button type="button" onClick={onPrev} disabled={matchCount === 0} aria-label="前へ">
        ▲
      </button>
      <button type="button" onClick={onNext} disabled={matchCount === 0} aria-label="次へ">
        ▼
      </button>
      <button type="button" onClick={onClose} aria-label="閉じる">
        ×
      </button>
    </div>
  );
}
