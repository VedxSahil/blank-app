"use client";

import { useEffect, useState } from "react";

/** Notice strip shown on every screen when the API reports a banner (sample or fixture data). */
export function Banner() {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((h) => setText(h.banner ?? null))
      .catch(() => setText(null));
  }, []);
  if (!text) return null;
  return (
    <div
      role="note"
      data-testid="banner"
      className="border-b border-warn-border bg-warn-bg px-4 py-2 text-center text-sm font-medium text-warn-fg"
    >
      {text}
    </div>
  );
}
