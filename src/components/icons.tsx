const sharedProps = {
  viewBox: "0 0 24 24",
  className: "toolbar-icon",
  "aria-hidden": true,
} as const;

export function FolderIcon() {
  return (
    <svg {...sharedProps}>
      <path d="M3 6.5A1.8 1.8 0 0 1 4.8 4.7h4.1l1.7 2.1h8.6a1.8 1.8 0 0 1 1.8 1.8v9A1.8 1.8 0 0 1 19.2 19.4H4.8A1.8 1.8 0 0 1 3 17.6z" />
    </svg>
  );
}

export function HistoryIcon() {
  return (
    <svg {...sharedProps}>
      <circle cx="12" cy="12.5" r="8" />
      <path d="M12 8v4.5l3.2 1.8" />
      <path d="M7 4.2 4.6 5.8" />
    </svg>
  );
}

export function PencilIcon() {
  return (
    <svg {...sharedProps}>
      <path d="M4 20l0.9-4 11-11 3.1 3.1-11 11z" />
      <path d="M13.6 6.3l3.1 3.1" />
      <path d="M4.9 16l3.1 3.1" />
    </svg>
  );
}
