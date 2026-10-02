export type IconName =
  | "dashboard"
  | "live"
  | "alerts"
  | "events"
  | "search"
  | "track"
  | "plates"
  | "faces"
  | "analytics"
  | "import"
  | "settings"
  | "admin";

const PATHS: Record<IconName, React.ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7.5" height="7.5" rx="1.6" />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6" />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6" />
    </>
  ),
  live: (
    <>
      <rect x="2.5" y="6" width="13" height="12" rx="2.5" />
      <path d="M15.5 10.5l6-3.5v10l-6-3.5" />
    </>
  ),
  alerts: (
    <>
      <path d="M12 3.5l9.5 17H2.5z" />
      <path d="M12 9.5v4.5" />
      <path d="M12 17.6h.01" />
    </>
  ),
  events: (
    <>
      <path d="M4 6.5h16M4 12h16M4 17.5h10" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M15.8 15.8L20.5 20.5" />
    </>
  ),
  track: (
    <>
      <circle cx="12" cy="12" r="6.5" />
      <circle cx="12" cy="12" r="2" />
      <path d="M12 2v3.5M12 18.5V22M2 12h3.5M18.5 12H22" />
    </>
  ),
  plates: (
    <>
      <rect x="2" y="7" width="20" height="10" rx="2.5" />
      <path d="M6.5 10.5v3M10.2 10.5v3M13.8 10.5v3M17.5 10.5v3" />
    </>
  ),
  faces: (
    <>
      <circle cx="12" cy="8.5" r="4" />
      <path d="M4.5 20.5c0-3.9 3.4-6.2 7.5-6.2s7.5 2.3 7.5 6.2" />
    </>
  ),
  analytics: (
    <>
      <path d="M3 20.5h18" />
      <path d="M6.5 20.5v-6M11.5 20.5V4.5M16.5 20.5v-9" />
    </>
  ),
  import: (
    <>
      <path d="M12 3.5v11.5" />
      <path d="M7.5 10.5L12 15l4.5-4.5" />
      <path d="M4 20.5h16" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h16M4 17h16" />
      <circle cx="9" cy="7" r="2.4" />
      <circle cx="15" cy="17" r="2.4" />
    </>
  ),
  admin: (
    <>
      <path d="M12 21.5s7.5-3.6 7.5-9.5V5.5L12 2.5 4.5 5.5V12c0 5.9 7.5 9.5 7.5 9.5z" />
      <path d="M9.2 11.8l2 2 3.6-3.8" />
    </>
  ),
};

export default function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}
