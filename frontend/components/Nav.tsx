"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/api";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/live", label: "Live" },
  { href: "/alerts", label: "Alerts" },
  { href: "/events", label: "Events" },
  { href: "/search", label: "Search" },
  { href: "/analytics", label: "Analytics" },
  { href: "/plates", label: "Plates" },
  { href: "/faces", label: "Faces" },
  { href: "/track", label: "Track" },
];

export default function Nav({ role, username }: { role: string; username: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const links = [...LINKS];
  if (role === "admin" || role === "manager") {
    links.push({ href: "/import", label: "Import" });
    links.push({ href: "/settings", label: "Settings" });
  }
  if (role === "admin") links.push({ href: "/admin", label: "Admin" });

  function onLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <nav className="nav">
      <div className="brand">🎥 SmartCam</div>
      <div className="links">
        {links.map((l) => (
          <Link key={l.href} href={l.href} className={pathname === l.href ? "active" : ""}>
            {l.label}
          </Link>
        ))}
      </div>
      <div className="right">
        <span className="muted">{username ? username + " (" + role + ")" : ""}</span>
        <button className="secondary" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </nav>
  );
}
