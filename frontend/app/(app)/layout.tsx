"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, me } from "@/lib/api";
import Nav from "@/components/Nav";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    me()
      .then((u) => setUser({ username: u.username, role: u.role }))
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!user) {
    return <div className="muted" style={{ padding: "2rem" }}>Loading…</div>;
  }

  return (
    <>
      <Nav role={user.role} username={user.username} />
      {children}
    </>
  );
}
