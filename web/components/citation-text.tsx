"use client";

import { motion, useReducedMotion } from "framer-motion";
import { FileText } from "lucide-react";
import type { Source } from "@/lib/api";

const CITATION = /\[([^\[\],]+),\s*p\.?\s*(\d+)\]/g;

type Part =
  | { kind: "text"; value: string }
  | { kind: "cite"; doc: string; page: number; key: string; sentence: string };

export function splitCitations(text: string): Part[] {
  const parts: Part[] = [];
  let last = 0;
  for (const m of text.matchAll(CITATION)) {
    const idx = m.index ?? 0;
    if (idx > last) parts.push({ kind: "text", value: text.slice(last, idx) });
    // the text since the previous chip is the sentence this chip supports
    const sentence = text.slice(last, idx).trim().replace(/^[.\s]+/, "");
    parts.push({ kind: "cite", doc: m[1].trim(), page: Number(m[2]), key: `${idx}`, sentence });
    last = idx + m[0].length;
  }
  if (last < text.length) parts.push({ kind: "text", value: text.slice(last) });
  return parts;
}

export function CitationText({
  text,
  sources,
  onOpen,
  animate = true,
}: {
  text: string;
  sources: Source[];
  onOpen: (s: Source, sentence: string) => void;
  animate?: boolean;
}) {
  const reduce = useReducedMotion();
  let n = 0;
  return (
    <p className="leading-relaxed">
      {splitCitations(text).map((p) => {
        if (p.kind === "text") return <span key={`t${p.value}`}>{p.value}</span>;
        const src = sources.find((s) => s.doc === p.doc && s.page === p.page);
        const delay = animate && !reduce ? 0.08 * n++ : 0;
        return (
          <motion.button
            key={p.key}
            type="button"
            disabled={!src}
            onClick={() => src && onOpen(src, p.sentence)}
            aria-label={`Open source: ${p.doc}, p.${p.page}`}
            initial={animate && !reduce ? { opacity: 0, scale: 0.8 } : false}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay, duration: 0.2 }}
            className="mx-1 inline-flex min-h-7 items-center gap-1 rounded-md border border-accent/40 bg-accent-soft px-2 align-baseline text-xs font-semibold text-accent hover:border-accent disabled:opacity-60"
          >
            <FileText aria-hidden className="size-3" />
            {p.doc}, p.{p.page}
          </motion.button>
        );
      })}
    </p>
  );
}
