"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { logout } from "@/lib/api";

type Item = { href: string; label: string; ico: string };
type Group = { title: string; items: Item[] };

/** The frame every signed-in page sits in: sidebar, topbar, mobile tab bar. */
export default function AppShell({
  role,
  username,
  children,
}: {
  role: string;
  username: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  // Close the drawer whenever we navigate.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const groups: Group[] = [
    {
      title: "Monitor",
      items: [
        { href: "/dashboard", label: "Dashboard", ico: "▦" },
        { href: "/live", label: "Live view", ico: "◉" },
        { href: "/alerts", label: "Alerts", ico: "⚠" },
      ],
    },
    {
      title: "Investigate",
      items: [
        { href: "/events", label: "Events", ico: "≡" },
        { href: "/search", label: "Search", ico: "⌕" },
        { href: "/track", label: "Track", ico: "◎" },
        { href: "/plates", label: "Plates", ico: "▭" },
        { href: "/faces", label: "Faces", ico: "☺" },
      ],
    },
    { title: "Insights", items: [{ href: "/analytics", label: "Analytics", ico: "◔" }] },
  ];

  if (role === "admin" || role === "manager") {
    const manage: Item[] = [
      { href: "/import", label: "Import", ico: "↑" },
      { href: "/settings", label: "Settings", ico: "⚙" },
    ];
    if (role === "admin") manage.push({ href: "/admin", label: "Admin", ico: "★" });
    groups.push({ title: "Manage", items: manage });
  }

  const tabs: Item[] = [
    { href: "/dashboard", label: "Home", ico: "▦" },
    { href: "/live", label: "Live", ico: "◉" },
    { href: "/alerts", label: "Alerts", ico: "⚠" },
    { href: "/events", label: "Events", ico: "≡" },
    { href: "/analytics", label: "Stats", ico: "◔" },
  ];

  const current = groups.flatMap((g) => g.items).find((i) => i.href === pathname);

  function onLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <div className="shell">
      <aside className={"sidebar" + (open ? " open" : "")}>
        <div className="sidebar-brand">
          <span className="mark">◉</span>
          <span>SmartCam</span>
        </div>
        <nav className="sidebar-nav">
          {groups.map((g) => (
            <div className="nav-group" key={g.title}>
              <div className="nav-group-title">{g.title}</div>
              {g.items.map((it) => (
                <Link
                  key={it.href}
                  href={it.href}
                  className={"nav-item" + (pathname === it.href ? " active" : "")}
                >
                  <span className="ico">{it.ico}</span>
                  <span>{it.label}</span>
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="live-dot" />
          <span className="muted">Connected</span>
        </div>
      </aside>

      <div className={"mobile-scrim" + (open ? " show" : "")} onClick={() => setOpen(false)} />

      <div className="shell-main">
        <header className="topbar">
          <button className="icon-btn" onClick={() => setOpen((v) => !v)} aria-label="Toggle navigation">
            ☰
          </button>
          <div className="topbar-title">{current ? current.label : "SmartCam"}</div>
          <div className="topbar-right">
            <span className="who muted">
              {username} · {role}
            </span>
            <button className="secondary btn-sm" onClick={onLogout}>
              Sign out
            </button>
          </div>
        </header>

        <div className="content">{children}</div>

        <nav className="tabbar">
          {tabs.map((t) => (
            <Link key={t.href} href={t.href} className={pathname === t.href ? "active" : ""}>
              <span className="ico">{t.ico}</span>
              {t.label}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}
