"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { logout } from "@/lib/api";
import Icon, { type IconName } from "@/components/Icon";

type Item = { href: string; label: string; icon: IconName };
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
        { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
        { href: "/live", label: "Live view", icon: "live" },
        { href: "/alerts", label: "Alerts", icon: "alerts" },
      ],
    },
    {
      title: "Investigate",
      items: [
        { href: "/events", label: "Events", icon: "events" },
        { href: "/search", label: "Search", icon: "search" },
        { href: "/track", label: "Track", icon: "track" },
        { href: "/plates", label: "Plates", icon: "plates" },
        { href: "/faces", label: "Faces", icon: "faces" },
      ],
    },
    { title: "Insights", items: [{ href: "/analytics", label: "Analytics", icon: "analytics" }] },
  ];

  if (role === "admin" || role === "manager") {
    const manage: Item[] = [
      { href: "/import", label: "Import", icon: "import" },
      { href: "/settings", label: "Settings", icon: "settings" },
    ];
    if (role === "admin") manage.push({ href: "/admin", label: "Admin", icon: "admin" });
    groups.push({ title: "Manage", items: manage });
  }

  const tabs: Item[] = [
    { href: "/dashboard", label: "Home", icon: "dashboard" },
    { href: "/live", label: "Live", icon: "live" },
    { href: "/alerts", label: "Alerts", icon: "alerts" },
    { href: "/events", label: "Events", icon: "events" },
    { href: "/analytics", label: "Stats", icon: "analytics" },
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
                  <span className="ico">
                    <Icon name={it.icon} />
                  </span>
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
          {/* Desktop shows the active item in the sidebar, so repeating it here would
              just duplicate the page heading. On mobile the sidebar is hidden. */}
          <div className="topbar-title">{current ? current.label : "SmartCam"}</div>
          <div className="topbar-right">
            <span className="who muted">{username}</span>
            {role && role !== username ? <span className="badge">{role}</span> : null}
            <button className="secondary btn-sm" onClick={onLogout}>
              Sign out
            </button>
          </div>
        </header>

        <div className="content">{children}</div>

        <nav className="tabbar">
          {tabs.map((t) => (
            <Link key={t.href} href={t.href} className={pathname === t.href ? "active" : ""}>
              <span className="ico">
                <Icon name={t.icon} size={20} />
              </span>
              {t.label}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}
