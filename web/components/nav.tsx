"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Ask" },
  { href: "/report", label: "Report Builder" },
  { href: "/eval", label: "Evaluation" },
  { href: "/library", label: "Documents" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <span className="text-base font-bold">PEReport</span>
        <nav aria-label="Main" className="flex flex-wrap gap-1">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={path === l.href ? "page" : undefined}
              className={cn(
                "flex min-h-11 items-center rounded-lg px-3 text-sm font-medium hover:bg-accent-soft",
                path === l.href && "bg-accent-soft text-accent",
              )}
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
