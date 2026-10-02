"use client";

import { useEffect, useState } from "react";
import { fetchThumbBlob } from "@/lib/api";

export default function EventThumb({ eventId, width = 96 }: { eventId: number; width?: number }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    let made: string | null = null;
    fetchThumbBlob(eventId)
      .then((blob) => {
        if (!alive) return;
        made = URL.createObjectURL(blob);
        setUrl(made);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [eventId]);

  if (failed) {
    return (
      <div
        style={{
          width,
          height: (width * 9) / 16,
          borderRadius: 6,
          background: "var(--surface-2)",
          border: "1px solid var(--border)",
          display: "grid",
          placeItems: "center",
          color: "var(--text-dim)",
          fontSize: ".7rem",
        }}
      >
        no image
      </div>
    );
  }

  if (!url) {
    return <div className="skeleton" style={{ width, height: (width * 9) / 16 }} />;
  }

  return (
    <img
      src={url}
      alt=""
      style={{ width, height: (width * 9) / 16, objectFit: "cover", borderRadius: 6, display: "block" }}
    />
  );
}
